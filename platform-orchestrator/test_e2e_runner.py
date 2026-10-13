"""
End-to-End Integration Verification Runner for Platform Orchestrator <-> Agent Worker
"""

import asyncio
import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(current_dir)

# Put platform-orchestrator on sys.path
sys.path.insert(0, current_dir)

from src.models.run_models import (
    ApprovalRequest,
    ClarificationRequest,
    CreateRunRequest,
    ReworkRequest
)
from src.services.intent_resolver import intent_resolver
from src.services.run_lifecycle_service import RunLifecycleService
from src.storage.orchestrator_storage import OrchestratorStorage


from src.services.worker_client import worker_client


class TestE2EOrchestratorWorkerIntegration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        test_db = os.path.join(current_dir, "test_e2e_orchestrator.db")
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except Exception:
                pass
        self.storage = OrchestratorStorage(db_path=test_db)
        self.lifecycle_service = RunLifecycleService(storage=self.storage)
        worker_client.use_mock = True

    async def test_01_intent_resolution_and_preflight(self):
        """Validates intent resolver and workflow catalog integration."""
        prd_intent = intent_resolver.resolve_intent("Generate PRD document for loyalty tier rewards")
        self.assertEqual(prd_intent["top_agent_id"], "AG-101")
        self.assertTrue(prd_intent["confidence_score"] >= 0.5)

        qe_intent = intent_resolver.resolve_intent("Create BDD automated test cases and scenarios for checkout payment")
        self.assertEqual(qe_intent["top_agent_id"], "AG-201")
        self.assertTrue(qe_intent["confidence_score"] >= 0.5)

    async def test_02_e2e_prd_lifecycle_orchestrator_worker(self):
        """
        Validates full end-to-end PRD workflow (AG-101):
        Create Run -> Dispatch -> CP-01 Halt (paused_for_validation) ->
        Clarify -> CP-05 Halt (awaiting_approval) -> Approve -> CP-FINAL Complete.
        """
        req = CreateRunRequest(
            agent_name="AG-101",
            team_id="team-product-checkout",
            user_id="usr-product-lead",
            input_data={
                "title": "One-Click Checkout Feature"
                # Missing stakeholder_inputs to trigger CP-01
            },
            skip_preflight=True
        )

        run = await self.lifecycle_service.create_and_dispatch_run(req)
        run_id = run["run_id"]

        # Wait briefly for background dispatch task to reach durable boundary CP-01
        for _ in range(20):
            await asyncio.sleep(0.05)
            r = self.lifecycle_service.get_run(run_id)
            if r["status"] in ["paused_for_validation", "waiting_for_clarification"]:
                break

        run_after_dispatch = self.lifecycle_service.get_run(run_id)
        self.assertIn(run_after_dispatch["status"].lower(), ["paused_for_validation", "waiting_for_clarification"])
        self.assertEqual(run_after_dispatch["current_checkpoint_id"], "CP-01")

        # 1. Provide Clarification Inputs
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
        self.assertIn(resumed_run["status"].lower(), ["awaiting_approval", "waiting_for_approval"])
        self.assertEqual(resumed_run["current_checkpoint_id"], "CP-05")

        # 2. Provide Human Approval
        approval = ApprovalRequest(
            decision="approve",
            reviewer_name="VP of Product",
            comments="Approved for Q3 engineering sprint planning"
        )
        completed_run = await self.lifecycle_service.handle_approval(run_id, approval)
        self.assertEqual(completed_run["status"].lower(), "completed")
        self.assertEqual(completed_run["current_checkpoint_id"], "CP-FINAL")
        self.assertIsNotNone(completed_run.get("output_data"))

    async def test_03_e2e_qe_workflow_with_rework_cycle(self):
        """
        Validates QE Workflow (AG-201) with Human Rework Cycle:
        Create Run with AC -> Worker executes -> CP-05 Halt (awaiting_approval) ->
        Reviewer requests rework -> CP-05 Revision -> Reviewer approves -> CP-FINAL Complete.
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

        for _ in range(20):
            await asyncio.sleep(0.05)
            r = self.lifecycle_service.get_run(run_id)
            if r["status"].lower() in ["awaiting_approval", "waiting_for_approval"]:
                break

        run_state = self.lifecycle_service.get_run(run_id)
        self.assertIn(run_state["status"].lower(), ["awaiting_approval", "waiting_for_approval"])
        self.assertEqual(run_state["current_checkpoint_id"], "CP-05")

        # 1. Rework Request (Human changes requested)
        rework_req = ReworkRequest(
            rework_step="Step 4: Candidate Scenarios",
            feedback_text="Add edge cases for expired tokens",
            reviewer_name="QE Lead"
        )
        rework_res = await self.lifecycle_service.handle_rework_feedback(run_id, rework_req)
        self.assertIn(rework_res["status"].lower(), ["awaiting_approval", "waiting_for_approval"])
        self.assertEqual(rework_res["rework_cycle_count"], 1)

        # 2. Final Approval
        approval_req = ApprovalRequest(
            decision="approve",
            reviewer_name="QE Lead",
            comments="Edge cases confirmed. Approved."
        )
        approved_run = await self.lifecycle_service.handle_approval(run_id, approval_req)
        self.assertEqual(approved_run["status"].lower(), "completed")
        self.assertEqual(approved_run["current_checkpoint_id"], "CP-FINAL")


if __name__ == "__main__":
    unittest.main()
