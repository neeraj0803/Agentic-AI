from typing import Any, Dict, Optional
import httpx

from ..config import settings
from ..telemetry import logger, trace_span


class AgentWorkerClient:
    """
    HTTP / REST client for dispatching workflows and checkpoint resumptions
    to the Agent Worker service (running in agent-worker/).
    Includes in-process dummy/mock fallback for isolated local testing.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        use_mock: bool = False,
        app: Optional[Any] = None
    ):
        self.base_url = base_url or settings.worker_service_url
        self.timeout = settings.worker_timeout_seconds
        self.use_mock = use_mock
        self.app = app

    async def dispatch_workflow(
        self,
        run_id: str,
        agent_name: str,
        agent_version: str,
        team_id: str,
        input_data: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dispatches an initial workflow execution window to the Agent Worker."""
        if self.use_mock or not self.base_url or self.base_url.lower() == "mock":
            return self._mock_worker_dispatch(run_id, agent_name, input_data)

        headers = {"Content-Type": "application/json"}
        if traceparent:
            headers["traceparent"] = traceparent

        payload = {
            "run_id": run_id,
            "agent_name": agent_name,
            "agent_version": agent_version,
            "team_id": team_id,
            "input_data": input_data
        }

        try:
            if self.app is not None:
                async with httpx.AsyncClient(app=self.app, base_url="http://testserver", timeout=self.timeout) as client:
                    res = await client.post("/worker/dispatch", json=payload, headers=headers)
                    if res.status_code == 200:
                        return res.json()
            else:
                timeout_cfg = httpx.Timeout(self.timeout, connect=5.0)
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    res = await client.post(f"{self.base_url}/worker/dispatch", json=payload, headers=headers)
                    if res.status_code == 200:
                        return res.json()
        except Exception as e:
            logger.warning(
                f"Agent Worker service unreachable at {self.base_url}/worker/dispatch: {e}. Utilizing local mock worker fallback.",
                run_id=run_id
            )

        # In-process dummy/mock worker simulation for local development & standalone testing
        return self._mock_worker_dispatch(run_id, agent_name, input_data)

    async def resume_workflow(
        self,
        run_id: str,
        checkpoint_id: str,
        resume_payload: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dispatches a resumption command from a durable checkpoint to the Agent Worker."""
        if self.use_mock or not self.base_url or self.base_url.lower() == "mock":
            return self._mock_worker_resume(run_id, checkpoint_id, resume_payload)

        headers = {"Content-Type": "application/json"}
        if traceparent:
            headers["traceparent"] = traceparent

        payload = {
            "run_id": run_id,
            "checkpoint_id": checkpoint_id,
            "resume_payload": resume_payload
        }

        try:
            if self.app is not None:
                async with httpx.AsyncClient(app=self.app, base_url="http://testserver", timeout=self.timeout) as client:
                    res = await client.post("/worker/resume", json=payload, headers=headers)
                    if res.status_code == 200:
                        return res.json()
            else:
                timeout_cfg = httpx.Timeout(self.timeout, connect=5.0)
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    res = await client.post(f"{self.base_url}/worker/resume", json=payload, headers=headers)
                    if res.status_code == 200:
                        return res.json()
        except Exception as e:
            logger.warning(
                f"Agent Worker service unreachable at {self.base_url}/worker/resume: {e}. Utilizing local mock worker fallback.",
                run_id=run_id
            )

        # In-process dummy/mock worker simulation
        return self._mock_worker_resume(run_id, checkpoint_id, resume_payload)

    def _mock_worker_dispatch(
        self,
        run_id: str,
        agent_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulates worker execution until a durable boundary (clarification or approval)."""
        # Product Use Case: Write PRD or Context Brief
        if agent_name in [
            "product_prd_or_context_brief_agent",
            "prd_generation_agent",
            "write_prd_or_context_brief"
        ]:
            title = input_data.get("title") or input_data.get("feature_name", "Untitled Product Feature")
            raw_inputs = input_data.get("stakeholder_inputs") or input_data.get("requirements_text") or ""
            target_user = input_data.get("target_user")

            if not raw_inputs or not target_user:
                missing = []
                if not raw_inputs:
                    missing.append("stakeholder_inputs")
                if not target_user:
                    missing.append("target_user")

                return {
                    "run_id": run_id,
                    "status": "WAITING_FOR_CLARIFICATION",
                    "checkpoint": {
                        "checkpoint_id": "CP-01",
                        "step_name": "Step 1: Understand Stakeholder Inputs",
                        "node_name": "understand_inputs",
                        "checkpoint_type": "CLARIFICATION",
                        "state_snapshot": {
                            "title": title,
                            "clarification_needed": True,
                            "missing_fields": missing,
                            "questions": [
                                "What are the core stakeholder problem statements and business objectives?",
                                "Who is the primary target persona or customer demographic?"
                            ]
                        },
                        "metadata": {"reason": "Missing mandatory stakeholder inputs"}
                    }
                }

            review_package = {
                "title": title,
                "target_personas": [target_user],
                "business_outcome": input_data.get("business_outcome", "Increase repeat visits by 15%"),
                "high_level_requirements": [
                    {
                        "id": "REQ-01",
                        "title": "Tiered Points Accrual",
                        "acceptance_criteria": ["Accrue points on purchase settlement"]
                    }
                ],
                "completeness_score": 96.0,
                "destination": "Confluence Enterprise Space"
            }

            return {
                "run_id": run_id,
                "status": "WAITING_FOR_APPROVAL",
                "checkpoint": {
                    "checkpoint_id": "CP-05",
                    "step_name": "Step 4: Prepare PRD / Context Brief Review Package",
                    "node_name": "prepare_review_package",
                    "checkpoint_type": "APPROVAL",
                    "state_snapshot": {
                        "title": title,
                        "review_package": review_package
                    },
                    "metadata": {"completeness_score": 96.0}
                }
            }

        # QE Use Case: Write Test Cases from Requirements
        ac_list = input_data.get("acceptance_criteria") or []
        jira_id = input_data.get("jira_story_id", "QE-MOCK")

        if not ac_list:
            # Reached Durable Boundary 1: Missing Clarification
            return {
                "run_id": run_id,
                "status": "WAITING_FOR_CLARIFICATION",
                "checkpoint": {
                    "checkpoint_id": "CP-01",
                    "step_name": "Step 1: Understand Request",
                    "node_name": "validate_inputs",
                    "checkpoint_type": "CLARIFICATION",
                    "state_snapshot": {
                        "jira_story_id": jira_id,
                        "clarification_needed": True,
                        "missing_fields": ["acceptance_criteria"],
                        "questions": [
                            "What are the specific Acceptance Criteria for this payment scenario?",
                            "What is the maximum retry limit on network timeouts?"
                        ]
                    },
                    "metadata": {"reason": "Missing mandatory acceptance criteria"}
                }
            }

        # Generates candidate test scenarios and pauses at Durable Boundary 2: Human Approval
        candidate_scenarios = [
            {
                "id": f"{jira_id}-TC-01",
                "type": "Positive",
                "title": f"Happy path payment processing with idempotency",
                "steps": ["Given user initiates checkout", "When payment succeeds", "Then confirmation 200 returned"]
            },
            {
                "id": f"{jira_id}-TC-02",
                "type": "Negative",
                "title": "Card declined handling (HTTP 402)",
                "steps": ["Given card is expired", "When payment attempted", "Then 402 returned without retry"]
            },
            {
                "id": f"{jira_id}-TC-03",
                "type": "Boundary",
                "title": "Transient 503 retry limit exhaustion",
                "steps": ["Given gateway responds 503", "When retried 3 times", "Then transaction marked failed"]
            }
        ]

        review_package = {
            "jira_story_id": jira_id,
            "total_scenarios": len(candidate_scenarios),
            "scenarios": candidate_scenarios,
            "coverage_score": 96.5,
            "format": input_data.get("target_output_format", "xray_bdd")
        }

        return {
            "run_id": run_id,
            "status": "WAITING_FOR_APPROVAL",
            "checkpoint": {
                "checkpoint_id": "CP-05",
                "step_name": "Step 4: Prepare Review Package",
                "node_name": "prepare_review_package",
                "checkpoint_type": "APPROVAL",
                "state_snapshot": {
                    "jira_story_id": jira_id,
                    "review_package": review_package
                },
                "metadata": {"total_scenarios": len(candidate_scenarios)}
            }
        }

    def _mock_worker_resume(
        self,
        run_id: str,
        checkpoint_id: str,
        resume_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulates worker resumption from CP-01 or CP-05."""
        if checkpoint_id == "CP-01":
            clarification = resume_payload.get("clarification_inputs", {})
            if "stakeholder_inputs" in clarification or "target_user" in clarification:
                return self._mock_worker_dispatch(
                    run_id,
                    "product_prd_or_context_brief_agent",
                    {
                        "title": clarification.get("title", "Loyalty Tiered Rewards"),
                        "stakeholder_inputs": clarification.get("stakeholder_inputs", "Implement loyalty cashback"),
                        "target_user": clarification.get("target_user", "Mobile Shoppers"),
                        "business_outcome": clarification.get("business_outcome", "Increase repeat visits by 15%"),
                        "constraints": clarification.get("constraints", ["PCI Level 1"])
                    }
                )
            else:
                ac = clarification.get("acceptance_criteria", ["Retry up to 3 times on 503"])
                mock_input = {
                    "jira_story_id": clarification.get("jira_story_id", "QE-RESUMED"),
                    "acceptance_criteria": ac
                }
                return self._mock_worker_dispatch(run_id, "qe_test_case_generation_agent", mock_input)

        elif checkpoint_id == "CP-05":
            decision = resume_payload.get("decision", "approve").lower()
            if decision == "approve":
                # Check whether PRD or QE
                is_prd = resume_payload.get("is_prd", False) or "confluence" in resume_payload.get("comments", "").lower() or "prd" in resume_payload.get("comments", "").lower()
                destination = "Confluence Enterprise Space" if is_prd else "Xray Test Management"
                return {
                    "run_id": run_id,
                    "status": "COMPLETED",
                    "checkpoint": {
                        "checkpoint_id": "CP-FINAL",
                        "step_name": "Step 5: Publish Output",
                        "node_name": "publish_output",
                        "checkpoint_type": "COMPLETED",
                        "state_snapshot": {"published": True},
                        "metadata": {"destination": destination}
                    },
                    "output_data": {
                        "destination": destination,
                        "confluence_page_url": "https://confluence.macys.com/pages/PROD/Customer-Loyalty-Rewards" if is_prd else None,
                        "published_keys": ["CONF-89104"] if is_prd else ["XRAY-8801", "XRAY-8802", "XRAY-8803"],
                        "status": "published",
                        "approver": resume_payload.get("reviewer_name", "Lead Reviewer")
                    }
                }
            else:
                # Requested changes -> loop back to WAITING_FOR_APPROVAL
                return {
                    "run_id": run_id,
                    "status": "WAITING_FOR_APPROVAL",
                    "checkpoint": {
                        "checkpoint_id": "CP-05",
                        "step_name": "Step 4: Prepare Review Package (Revision)",
                        "node_name": "prepare_review_package",
                        "checkpoint_type": "APPROVAL",
                        "state_snapshot": {
                            "revised": True,
                            "reviewer_comments": resume_payload.get("comments")
                        },
                        "metadata": {"revision": True}
                    }
                }

        return {
            "run_id": run_id,
            "status": "COMPLETED",
            "output_data": {"message": f"Resumed from generic checkpoint {checkpoint_id}"}
        }


worker_client = AgentWorkerClient()
