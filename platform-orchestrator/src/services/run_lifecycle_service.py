import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

from ..config import settings
from ..models.run_models import (
    ApprovalRequest,
    ClarificationRequest,
    CreateRunRequest,
    PreflightRequest,
    ResumeRequest,
    ReworkRequest,
    WorkflowRunStatus
)
from ..storage.orchestrator_storage import OrchestratorStorage
from ..streaming.sse_broadcaster import sse_broadcaster
from ..telemetry import logger, metrics_registry, trace_span
from .checkpoint_service import checkpoint_service
from .mock_context_engine import mock_context_engine
from .mock_skills_engine import mock_skills_engine
from .preflight_service import preflight_service
from .queue_service import queue_service
from .snapshot_service import snapshot_service
from .worker_client import worker_client
from .workflow_registry import workflow_registry


class RunLifecycleService:
    """
    Platform Orchestrator Run Lifecycle Service.
    Owns the authoritative end-to-end lifecycle of agent workflow executions:
    - Performs 18-point preflight validation gate.
    - Compiles published YAML into immutable SHA256 snapshot (rwf_*).
    - Materializes Context Packs and dynamic Skills Overlays.
    - Queues and dispatches execution tasks to Agent Workers.
    - Manages 17 canonical macro states and durable HITL checkpoints (CP-01, CP-05, CP-FINAL).
    - Enforces bounded loops: validation cycles <= 3, human rework cycles <= 3.
    - Broadcasts live status updates and events via SSE with Last-Event-ID replay.
    """

    MAX_VALIDATION_ATTEMPTS = 3
    MAX_REWORK_CYCLES = 3

    def __init__(self, storage: Optional[OrchestratorStorage] = None):
        self.storage = storage or OrchestratorStorage()

    async def create_and_dispatch_run(self, req: CreateRunRequest) -> Dict[str, Any]:
        """Validates preflight, compiles snapshot, creates run, and initiates dispatch."""
        with trace_span("orchestrator.create_and_dispatch_run") as span:
            policy_ver = req.policy_version or settings.default_policy_version
            timeout_s = req.timeout_seconds or settings.default_timeout_seconds
            run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
            span.run_id = run_id

            # 1. Preflight Validation Gate
            if not req.skip_preflight:
                preflight_req = PreflightRequest(
                    agent_id=req.agent_name,
                    team_id=req.team_id,
                    user_id=req.user_id,
                    inputs=req.input_data,
                    session_id=req.session_id
                )
                preflight_res = preflight_service.validate_preflight(preflight_req)
                if not preflight_res.valid:
                    blocker_codes = [r.error_code for r in preflight_res.rule_results if r.status == "FAIL"]
                    raise ValueError(f"Preflight validation failed with blockers: {', '.join(filter(None, blocker_codes))}")

            # 2. Compile Immutable Snapshot (rwf_*)
            snapshot = snapshot_service.compile_snapshot(
                workflow_id=req.agent_name,
                team_id=req.team_id,
                policy_version=policy_ver
            )
            resolved_wf_id = snapshot["resolved_workflow_id"]

            # 3. Create run record in authoritative storage
            run = self.storage.create_run(
                run_id=run_id,
                agent_name=req.agent_name,
                agent_version=req.agent_version,
                team_id=req.team_id,
                policy_version=policy_ver,
                input_data=req.input_data,
                timeout_seconds=timeout_s,
                session_id=req.session_id,
                user_id=req.user_id,
                resolved_workflow_id=resolved_wf_id,
                idempotency_key=req.idempotency_key,
                trace_id=span.trace_id
            )

            # 4. Save compiled snapshot record
            self.storage.save_resolved_workflow(
                resolved_workflow_id=resolved_wf_id,
                run_id=run_id,
                workflow_id=req.agent_name,
                sha256_hash=snapshot["sha256_hash"],
                workflow_yaml=snapshot["workflow_yaml"],
                policy_snapshot=snapshot["policy_snapshot"],
                team_config_snapshot=snapshot["team_config_snapshot"],
                step_bindings_map=snapshot["step_bindings_map"]
            )

            # 5. Build and attach Context & Skills Overlays
            try:
                context_pack = mock_context_engine.build_context_package(
                    team_id=req.team_id,
                    application_name=req.input_data.get("application_name", "Default App"),
                    required_capabilities=workflow_registry.extract_required_context(req.agent_name)
                )
                self.storage.save_overlay(run_id, "CONTEXT", context_pack["package_id"], context_pack)

                skills_overlay = mock_skills_engine.bind_skills_for_workflow(
                    agent_id=req.agent_name,
                    team_id=req.team_id,
                    requested_skills=workflow_registry.extract_skill_shortlist(req.agent_name)
                )
                self.storage.save_overlay(run_id, "SKILL", f"skills_{req.agent_name}", skills_overlay)
            except Exception as e:
                logger.warning(f"Could not build mock context/skills overlay: {e}", run_id=run_id)

            # 6. Update session state if session linked
            if req.session_id:
                self.storage.update_session_state(
                    session_id=req.session_id,
                    session_state="run_dispatched",
                    metadata_update={"active_run_id": run_id}
                )

            metrics_registry.record_run_created(req.agent_name, req.team_id)
            logger.info(
                f"Created workflow run {run_id} [Agent: {req.agent_name}:{req.agent_version}, Resolved: {resolved_wf_id}]",
                run_id=run_id
            )

            # Broadcast QUEUED event
            sse_broadcaster.broadcast(
                run_id=run_id,
                event_name="run_status_changed",
                payload={"status": "queued", "run": run},
                session_id=req.session_id,
                state="queued"
            )

            # 7. Asynchronously transition to RUNNING & dispatch worker
            asyncio.create_task(self._execute_dispatch_flow(run_id, req, span.get_w3c_traceparent()))

            return run

    async def _execute_dispatch_flow(
        self,
        run_id: str,
        req: CreateRunRequest,
        traceparent: Optional[str] = None
    ) -> None:
        start_t = time.perf_counter()
        try:
            # Transition to running
            self.storage.update_run_status(run_id, status="running")
            sse_broadcaster.broadcast(
                run_id=run_id,
                event_name="run_status_changed",
                payload={"status": "running"},
                session_id=req.session_id,
                state="running"
            )

            # Dispatch with platform retry and timeout policies
            worker_res = await queue_service.dispatch_with_retry(
                run_id=run_id,
                action_name="DISPATCH_WORKFLOW",
                dispatch_coro_fn=lambda: worker_client.dispatch_workflow(
                    run_id=run_id,
                    agent_name=req.agent_name,
                    agent_version=req.agent_version,
                    team_id=req.team_id,
                    input_data=req.input_data,
                    traceparent=traceparent
                ),
                timeout_seconds=req.timeout_seconds
            )

            # Process worker response & record checkpoints
            await self._process_worker_response(run_id, worker_res, start_t, session_id=req.session_id)

        except Exception as e:
            duration = time.perf_counter() - start_t
            logger.error(f"Workflow run {run_id} failed: {e}", run_id=run_id)
            self.storage.update_run_status(run_id, status="failed", error_message=str(e))
            metrics_registry.record_run_transition("failed", duration)
            sse_broadcaster.broadcast(
                run_id=run_id,
                event_name="run_failed",
                payload={"error": str(e), "status": "failed"},
                session_id=req.session_id,
                state="failed"
            )

    async def handle_clarification(
        self,
        run_id: str,
        req: ClarificationRequest
    ) -> Dict[str, Any]:
        """Provides missing inputs for a run paused at CP-01 (paused_for_validation / WAITING_FOR_CLARIFICATION) and resumes."""
        run = self.storage.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found.")

        # In-flight grace period: Wait up to 3s if worker is currently processing towards boundary
        if run["status"].lower() in ["queued", "running", "step_running"]:
            for _ in range(30):
                await asyncio.sleep(0.1)
                run = self.storage.get_run(run_id)
                if run["status"].lower() not in ["queued", "running", "step_running"]:
                    break

        status_lower = run["status"].lower()
        if status_lower not in ["paused_for_validation", "waiting_for_clarification"]:
            raise ValueError(f"Run {run_id} is in status '{run['status']}', not 'paused_for_validation'.")

        # Enforce Bounded Validation Loop (<= 3 attempts)
        current_attempts = run.get("validation_attempt_count", 0)
        if current_attempts >= self.MAX_VALIDATION_ATTEMPTS:
            self.storage.update_run_status(
                run_id=run_id,
                status="dead_lettered",
                error_message=f"Validation loop exceeded max threshold ({self.MAX_VALIDATION_ATTEMPTS} attempts)."
            )
            sse_broadcaster.broadcast(run_id, "run_dead_lettered", {"error": "Exceeded max validation attempts"})
            raise ValueError(f"Run {run_id} exceeded maximum validation attempts ({self.MAX_VALIDATION_ATTEMPTS}). Run moved to dead_lettered.")

        self.storage.update_run_status(run_id, status="resuming", increment_validation=True)
        logger.info(f"Received clarification inputs for {run_id} (Attempt {current_attempts + 1}/{self.MAX_VALIDATION_ATTEMPTS}). Resuming from CP-01.", run_id=run_id)
        
        resume_payload = {
            "clarification_inputs": req.clarification_inputs,
            "notes": req.notes,
            "agent_name": run.get("agent_name"),
            "workflow_name": run.get("workflow_name")
        }
        return await self.resume_from_checkpoint(run_id, checkpoint_id="CP-01", payload=resume_payload)

    async def handle_approval(
        self,
        run_id: str,
        req: ApprovalRequest
    ) -> Dict[str, Any]:
        """Processes human review decision for a run paused at CP-05 (awaiting_approval) and resumes or completes."""
        run = self.storage.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found.")

        # In-flight grace period: Wait up to 3s if worker is currently processing towards boundary
        if run["status"].lower() in ["queued", "running", "step_running"]:
            for _ in range(30):
                await asyncio.sleep(0.1)
                run = self.storage.get_run(run_id)
                if run["status"].lower() not in ["queued", "running", "step_running"]:
                    break

        status_lower = run["status"].lower()
        if status_lower not in ["awaiting_approval", "waiting_for_approval"]:
            raise ValueError(f"Run {run_id} is in status '{run['status']}', not 'awaiting_approval'.")

        decision_val = req.decision.lower()

        # Handle Rejection
        if decision_val == "reject":
            self.storage.update_run_status(
                run_id=run_id,
                status="rejected",
                error_message=f"Human reviewer rejected package: {req.comments or 'No reason provided'}"
            )
            sse_broadcaster.broadcast(run_id, "run_rejected", {"comments": req.comments})
            return self.storage.get_run(run_id)

        # Handle Request Changes (Rework)
        if decision_val == "request_changes":
            current_rework = run.get("rework_cycle_count", 0)
            if current_rework >= self.MAX_REWORK_CYCLES:
                self.storage.update_run_status(
                    run_id=run_id,
                    status="rejected",
                    error_message=f"Human review rework cycles exceeded max threshold ({self.MAX_REWORK_CYCLES} cycles)."
                )
                sse_broadcaster.broadcast(run_id, "run_rejected", {"error": "Exceeded max rework cycles"})
                raise ValueError(f"Run {run_id} exceeded maximum human rework cycles ({self.MAX_REWORK_CYCLES}). Run rejected.")

            self.storage.update_run_status(run_id, status="rework_requested", increment_rework=True)
            resume_payload = {
                "decision": "request_changes",
                "reviewer_name": req.reviewer_name,
                "comments": req.comments,
                "agent_name": run.get("agent_name"),
                "rework_cycle": current_rework + 1
            }
            return await self.resume_from_checkpoint(run_id, checkpoint_id="CP-05", payload=resume_payload)

        # Handle Approval (Approve -> approved_to_write / writing)
        logger.info(f"Received human approval for {run_id}. Proceeding to writeback.", run_id=run_id)
        self.storage.update_run_status(run_id, status="approved_to_write")
        resume_payload = {
            "decision": "approve",
            "reviewer_name": req.reviewer_name,
            "comments": req.comments,
            "agent_name": run.get("agent_name"),
            "is_prd": run.get("agent_name") in ["product_prd_or_context_brief_agent", "prd_generation_agent", "write_prd_or_context_brief", "AG-101"]
        }
        return await self.resume_from_checkpoint(run_id, checkpoint_id="CP-05", payload=resume_payload)

    async def handle_rework_feedback(
        self,
        run_id: str,
        req: ReworkRequest
    ) -> Dict[str, Any]:
        """Provides structured feedback and target reversion step for rework cycle."""
        approval_req = ApprovalRequest(
            decision="request_changes",
            reviewer_name=req.reviewer_name,
            comments=req.feedback_text
        )
        return await self.handle_approval(run_id, approval_req)

    async def resume_from_checkpoint(
        self,
        run_id: str,
        checkpoint_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resumes a workflow run from any valid checkpoint."""
        with trace_span("orchestrator.resume_from_checkpoint", run_id=run_id) as span:
            start_t = time.perf_counter()
            self.storage.update_run_status(run_id, status="running")
            sse_broadcaster.broadcast(
                run_id=run_id,
                event_name="run_status_changed",
                payload={"status": "running", "resumed_from": checkpoint_id},
                state="running"
            )

            try:
                worker_res = await queue_service.dispatch_with_retry(
                    run_id=run_id,
                    action_name=f"RESUME_{checkpoint_id}",
                    dispatch_coro_fn=lambda: worker_client.resume_workflow(
                        run_id=run_id,
                        checkpoint_id=checkpoint_id,
                        resume_payload=payload,
                        traceparent=span.get_w3c_traceparent()
                    )
                )

                await self._process_worker_response(run_id, worker_res, start_t)
                return self.storage.get_run(run_id)

            except Exception as e:
                duration = time.perf_counter() - start_t
                logger.error(f"Resumption of run {run_id} from {checkpoint_id} failed: {e}", run_id=run_id)
                self.storage.update_run_status(run_id, status="failed", error_message=str(e))
                metrics_registry.record_run_transition("failed", duration)
                sse_broadcaster.broadcast(run_id=run_id, event_name="run_failed", payload={"error": str(e)}, state="failed")
                raise

    async def _process_worker_response(
        self,
        run_id: str,
        worker_res: Dict[str, Any],
        start_time: float,
        session_id: Optional[str] = None
    ) -> None:
        """Evaluates worker outcome, saves checkpoints, and transitions macro status."""
        raw_status = worker_res.get("status", "COMPLETED")
        checkpoint_data = worker_res.get("checkpoint")
        output_data = worker_res.get("output_data")
        duration = time.perf_counter() - start_time

        # Map legacy worker status strings to canonical states
        status_map = {
            "COMPLETED": "completed",
            "WAITING_FOR_CLARIFICATION": "paused_for_validation",
            "WAITING_FOR_APPROVAL": "awaiting_approval",
            "FAILED": "failed",
            "CANCELLED": "cancelled"
        }
        canonical_status = status_map.get(raw_status, raw_status.lower())

        # If worker halted at a durable checkpoint
        current_cp_id = None
        if checkpoint_data:
            saved_cp = checkpoint_service.record_checkpoint(run_id, checkpoint_data)
            current_cp_id = saved_cp["checkpoint_id"]
            sse_broadcaster.broadcast(
                run_id=run_id,
                event_name="checkpoint_recorded",
                payload=saved_cp,
                session_id=session_id,
                state=canonical_status
            )

        # Update run record
        updated_run = self.storage.update_run_status(
            run_id=run_id,
            status=canonical_status,
            current_checkpoint_id=current_cp_id,
            output_data=output_data
        )

        metrics_registry.record_run_transition(canonical_status, duration)
        logger.info(f"Workflow run {run_id} transitioned to {canonical_status} (in {round(duration, 2)}s)", run_id=run_id)

        # Broadcast specific SSE events for UI dashboard
        if canonical_status in ["paused_for_validation", "waiting_for_clarification"]:
            sse_broadcaster.broadcast(
                run_id=run_id,
                event_name="waiting_for_clarification",
                payload={
                    "checkpoint_id": current_cp_id,
                    "details": checkpoint_data.get("state_snapshot") if checkpoint_data else {}
                },
                session_id=session_id,
                state="paused_for_validation"
            )
        elif canonical_status in ["awaiting_approval", "waiting_for_approval"]:
            sse_broadcaster.broadcast(
                run_id=run_id,
                event_name="waiting_for_approval",
                payload={
                    "checkpoint_id": current_cp_id,
                    "review_package": checkpoint_data.get("state_snapshot", {}).get("review_package") if checkpoint_data else {}
                },
                session_id=session_id,
                state="awaiting_approval"
            )
        elif canonical_status == "completed":
            if session_id:
                self.storage.update_session_state(session_id=session_id, session_state="completed")
            sse_broadcaster.broadcast(
                run_id=run_id,
                event_name="run_completed",
                payload={
                    "run_id": run_id,
                    "output_data": output_data
                },
                session_id=session_id,
                state="completed"
            )

    async def cancel_run(self, run_id: str, reason: str = "User cancelled") -> Dict[str, Any]:
        """Cancels an active or paused workflow run."""
        run = self.storage.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found.")

        if run["status"].lower() in ["completed", "failed", "cancelled", "rejected", "dead_lettered"]:
            return run

        self.storage.update_run_status(run_id, status="cancelled", error_message=f"Cancelled: {reason}")
        metrics_registry.record_run_transition("cancelled")
        logger.info(f"Workflow run {run_id} cancelled. Reason: {reason}", run_id=run_id)
        sse_broadcaster.broadcast(run_id=run_id, event_name="run_cancelled", payload={"reason": reason}, state="cancelled")

        return self.storage.get_run(run_id)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_run(run_id)

    def list_runs(
        self,
        team_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        return self.storage.list_runs(team_id=team_id, status=status, limit=limit)


run_lifecycle_service = RunLifecycleService()
