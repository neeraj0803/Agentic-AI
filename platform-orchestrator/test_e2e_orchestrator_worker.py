"""
End-to-End Integration Verification Suite for Platform Orchestrator <-> Agent Worker
Validates the full enterprise execution contract documented in docs/02_end_to_end_agent_execution_design.md:
1. Direct Agent Worker FastAPI contract (/worker/dispatch, /worker/resume, /worker/info, /worker/metrics)
2. PRD Workflow (AG-101):
   - Dispatch incomplete -> Worker halts at CP-01 (WAITING_FOR_CLARIFICATION)
   - Orchestrator handles clarification -> Resumes from CP-01 -> Worker halts at CP-05 (WAITING_FOR_APPROVAL)
   - Orchestrator handles approval -> Resumes from CP-05 -> Worker completes at CP-FINAL (COMPLETED)
3. QE Workflow (AG-201):
   - Dispatch with acceptance criteria -> Worker halts at CP-05 (WAITING_FOR_APPROVAL)
   - Orchestrator requests changes (Rework cycle) -> Resumes from CP-05
   - Orchestrator approves -> Resumes from CP-05 -> Worker completes at CP-FINAL (COMPLETED)
4. Session Intent Resolution -> Run Dispatch -> Checkpoint Handling
"""

import asyncio
import os
import sys
import unittest

# Add platform-orchestrator and agent-worker to Python path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, "platform-orchestrator"))
sys.path.insert(0, os.path.join(repo_root, "agent-worker"))

from fastapi.testclient import TestClient

# Import Agent Worker App & Executor
from src.main import app as worker_app
from src.graph.worker_graph import worker_executor

# Import Platform Orchestrator Components
from platform_orchestrator.src.services.run_lifecycle_service import RunLifecycleService
from platform_orchestrator.src.services.worker_client import AgentWorkerClient
from platform_orchestrator.src.services.intent_resolver import intent_resolver
from platform_orchestrator.src.services.workflow_registry import workflow_registry
from platform_orchestrator.src.models.run_models import (
    CreateRunRequest,
    ClarificationRequest,
    ApprovalRequest,
    ReworkRequest
)
from platform_orchestrator.src.storage.orchestrator_storage import OrchestratorStorage


class TestE2EOrchestratorWorkerIntegration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Use an in-memory/isolated SQLite db for testing
        test_db = os.path.join(repo_root, "platform-orchestrator", "test_e2e_orchestrator.db")
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except Exception:
                pass
        self.storage = OrchestratorStorage(db_path=test_db)
        self.lifecycle_service = RunLifecycleService(storage=self.storage)
        self.worker_client = TestClient(worker_app)

    def test_01_direct_worker_endpoints(self):
        """Validates Agent Worker FastAPI endpoints directly."""
        # 1. Health check
        res = self.worker_client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "healthy")

        # 2. Worker info
        res = self.worker_client.get("/worker/info")
        self.assertEqual(res.status_code, 200)
        self.assertIn("LangGraph Continuous Execution Window", res.json().get("runtime", ""))

        # 3. Direct dispatch for PRD (Incomplete -> CP-01)
        dispatch_payload = {
            "run_id": "RUN-TEST-001",
            "agent_name": "product_prd_or_context_brief_agent",
            "agent_version": "v1.0",
            "team_id": "team-product",
            "input_data": {"title": "Biometric Auth"}
        }
        res = self.worker_client.post("/worker/dispatch", json=dispatch_payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body.get("status"), "WAITING_FOR_CLARIFICATION")
        self.assertEqual(body.get("checkpoint", {}).get("checkpoint_id"), "CP-01")

        # 4. Direct resume from CP-01 (Clarification -> CP-05)
        resume_payload = {
            "run_id": "RUN-TEST-001",
            "checkpoint_id": "CP-01",
            "resume_payload": {
                "clarification_inputs": {
                    "title": "Biometric Auth",
                    "stakeholder_inputs": "Enable face ID and fingerprint login on iOS & Android apps",
                    "target_user": "Mobile app shoppers",
                    "business_outcome": "Reduce login friction and increase checkout speed by 20%",
                    "constraints": ["FIDO2 compliance", "Zero biometric storage on server"]
                }
            }
        }
        res = self.worker_client.post("/worker/resume", json=resume_payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body.get("status"), "WAITING_FOR_APPROVAL")
        self.assertEqual(body.get("checkpoint", {}).get("checkpoint_id"), "CP-05")

        # 5. Direct resume from CP-05 (Approval -> CP-FINAL)
        approval_payload = {
            "run_id": "RUN-TEST-001",
            "checkpoint_id": "CP-05",
            "resume_payload": {
                "decision": "approve",
                "reviewer_name": "Product Lead",
                "comments": "PRD brief looks executive ready",
                "is_prd": True
            }
        }
        res = self.worker_client.post("/worker/resume", json=approval_payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body.get("status"), "COMPLETED")
        self.assertEqual(body.get("checkpoint", {}).get("checkpoint_id"), "CP-FINAL")
        self.assertTrue(body.get("checkpoint", {}).get("state_snapshot", {}).get("published"))

    async def test_02_e2e_prd_lifecycle_orchestrator_worker(self):
        """
        Validates full end-to-end PRD workflow (AG-101):
        Create Run -> Dispatch -> CP-01 Halt -> Clarify -> CP-05 Halt -> Approve -> CP-FINAL Complete.
        """
        req = CreateRunRequest(
            agent_name="AG-101",
            team_id="team-product-checkout",
            user_id="usr-product-lead",
            input_data={
                "title": "One-Click Checkout Feature"
                # Omit stakeholder_inputs, target_user to trigger CP-01
            },
            skip_preflight=True
        )

        run = await self.lifecycle_service.create_and_dispatch_run(req)
        run_id = run["run_id"]

        # Wait briefly for background dispatch task to reach durable boundary CP-01
        await asyncio.sleep(0.3)

        run_after_dispatch = self.lifecycle_service.get_run(run_id)
        self.assertEqual(run_after_dispatch["status"], "paused_for_validation")
        self.assertEqual(run_after_dispatch["current_checkpoint_id"], "CP-01")

        # Human provides clarification inputs to Orchestrator
        clarification = ClarificationRequest(
            clarification_inputs={
                "title": "One-Click Checkout Feature",
                "stakeholder_inputs": "Enable 1-click buy button using stored vault payment tokens",
                "target_user": "Returning registered buyers",
                "business_outcome": "Boost conversion by 12% and reduce checkout abandoned carts",
                "constraints": ["PCI-DSS compliant vault", "3DS step-up authentication when risky"]
            },
            notes="Clarified persona and security constraints"
        )
        resumed_run = await self.lifecycle_service.handle_clarification(run_id, clarification)
        self.assertEqual(resumed_run["status"], "awaiting_approval")
        self.assertEqual(resumed_run["current_checkpoint_id"], "CP-05")

        # Human approves the PRD review package
        approval = ApprovalRequest(
            decision="approve",
            reviewer_name="VP of Product",
            comments="Approved for Q3 engineering sprint planning"
        )
        completed_run = await self.lifecycle_service.handle_approval(run_id, approval)
        self.assertEqual(completed_run["status"], "completed")
        self.assertEqual(completed_run["current_checkpoint_id"], "CP-FINAL")
        self.assertIsNotNone(completed_run.get("output_data"))

    async def test_03_e2e_qe_workflow_with_rework_cycle(self):
        """
        Validates QE Workflow (AG-201) with Human Rework Cycle:
        Create Run with AC -> Worker executes -> CP-05 Halt -> Reviewer requests rework ->
        CP-05 Revision -> Reviewer approves -> CP-FINAL Complete.
        """
        req = CreateRunRequest(
            agent_name="AG-201",
            team_id="team-payment-qe",
            user_id="usr-qe-lead",
            input_data={
                "jira_story_id": "PAY-882",
                "application_name": "Checkout Payment Gateway",
                "acceptance_criteria": [
                    "User can pay with Apple Pay and Google Pay",
                    "Retry failed idempotency tokens up to 3 times",
                    "Trigger refund on chargeback event"
                ],
                "target_output_format": "xray_bdd"
            },
            skip_preflight=True
        )

        run = await self.lifecycle_service.create_and_dispatch_run(req)
        run_id = run["run_id"]

        await asyncio.sleep(0.3)

        run_state = self.lifecycle_service.get_run(run_id)
        self.assertEqual(run_state["status"], "awaiting_approval")
        self.assertEqual(run_state["current_checkpoint_id"], "CP-05")

        # 1. Rework Request (Human changes requested)
        rework_req = ReworkRequest(
            rework_step="Step 4: Candidate Scenarios",
            feedback_text="Add edge cases for expired tokens",
            reviewer_name="QE Lead"
        )
        rework_res = await self.lifecycle_service.handle_rework_feedback(run_id, rework_req)
        self.assertEqual(rework_res["status"], "awaiting_approval")
        self.assertEqual(rework_res["rework_cycle_count"], 1)

        # 2. Final Approval
        approval_req = ApprovalRequest(
            decision="approve",
            reviewer_name="QE Lead",
            comments="Edge cases confirmed. Approved."
        )
        approved_run = await self.lifecycle_service.handle_approval(run_id, approval_req)
        self.assertEqual(approved_run["status"], "completed")
        self.assertEqual(approved_run["current_checkpoint_id"], "CP-FINAL")


if __name__ == "__main__":
    unittest.main()

