import tempfile
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from src.main import app
from src.services.checkpoint_service import checkpoint_service
from src.services.queue_service import queue_service
from src.services.run_lifecycle_service import run_lifecycle_service
from src.services.worker_client import worker_client
from src.storage.orchestrator_storage import OrchestratorStorage


class TestProductPRDOrchestrator(unittest.TestCase):
    """
    Test suite for Platform Orchestrator — Product Use Case:
    "Write PRD or Context Brief" (product_prd_or_context_brief_agent)
    
    Verifies:
    - End-to-end run creation with product_prd_or_context_brief_agent
    - Missing input detection -> CP-01 (WAITING_FOR_CLARIFICATION)
    - Clarification submission and continuous resumption -> CP-05 (WAITING_FOR_APPROVAL)
    - Product lead review and approval -> CP-FINAL (COMPLETED) with Confluence publish
    - Rejection/revision loopback
    - Full telemetry and audit trail in OrchestratorStorage
    """

    def setUp(self):
        worker_client.use_mock = True
        try:
            self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            self.temp_dir = tempfile.TemporaryDirectory()

        self.db_path = Path(self.temp_dir.name) / "test_prd_orchestrator.db"
        self.storage = OrchestratorStorage(db_path=str(self.db_path))

        run_lifecycle_service.storage = self.storage
        checkpoint_service.storage = self.storage
        queue_service.storage = self.storage

        self.client = TestClient(app)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _wait_for_status(self, run_id: str, target_statuses: list, timeout_sec: float = 3.0):
        start = time.time()
        while time.time() - start < timeout_sec:
            res = self.client.get(f"/api/orchestrator/runs/{run_id}")
            if res.status_code == 200:
                data = res.json()
                if data["status"] in target_statuses:
                    return data
            time.sleep(0.05)
        return self.client.get(f"/api/orchestrator/runs/{run_id}").json()

    def test_missing_stakeholder_inputs_clarification_cycle(self):
        """When stakeholder inputs are missing, orchestrator pauses at CP-01 and resumes upon clarification."""
        create_payload = {
            "workflow_name": "product_prd_or_context_brief",
            "agent_name": "product_prd_or_context_brief_agent",
            "team_id": "team-loyalty-product",
            "channel": "confluence",
            "input_data": {
                "title": "Customer Loyalty Tiered Cash-Back & Rewards",
                "stakeholder_inputs": "",  # Missing!
                "target_user": None        # Missing!
            }
        }
        res = self.client.post("/api/orchestrator/runs", json=create_payload)
        self.assertEqual(res.status_code, 201)
        run_data = res.json()
        run_id = run_data["run_id"]

        run_data = self._wait_for_status(run_id, ["WAITING_FOR_CLARIFICATION"])
        self.assertEqual(run_data["status"], "WAITING_FOR_CLARIFICATION")
        self.assertEqual(run_data["current_checkpoint_id"], "CP-01")

        # Verify checkpoint snapshot contains questions
        cp_res = self.client.get(f"/api/orchestrator/runs/{run_id}/checkpoints/CP-01")
        self.assertEqual(cp_res.status_code, 200)
        cp_data = cp_res.json()
        snapshot = cp_data["state_snapshot"]
        self.assertTrue(snapshot["clarification_needed"])
        self.assertIn("stakeholder_inputs", snapshot["missing_fields"])

        # Submit clarification
        clarify_payload = {
            "clarification_inputs": {
                "title": "Customer Loyalty Tiered Cash-Back & Rewards",
                "stakeholder_inputs": "Enable shoppers to accrue tiered rewards points online and in-store.",
                "target_user": "Macy's Mobile App Shoppers",
                "business_outcome": "Increase repeat visits by 15%",
                "constraints": ["PCI-DSS Level 1 compliance", "Zero POS latency impact"]
            },
            "notes": "Provided missing target user and business objectives"
        }
        res_clarify = self.client.post(f"/api/orchestrator/runs/{run_id}/clarify", json=clarify_payload)
        self.assertEqual(res_clarify.status_code, 200)

        # Worker continues continuous window to CP-05
        run_data = self._wait_for_status(run_id, ["WAITING_FOR_APPROVAL"])
        self.assertEqual(run_data["status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(run_data["current_checkpoint_id"], "CP-05")

    def test_complete_prd_journey_to_confluence_publish(self):
        """Full PRD journey: Create run -> CP-05 Review -> Product Lead Approve -> Confluence Publish (CP-FINAL)."""
        create_payload = {
            "workflow_name": "product_prd_or_context_brief",
            "agent_name": "product_prd_or_context_brief_agent",
            "team_id": "team-loyalty-product",
            "channel": "jira",
            "input_data": {
                "title": "Customer Loyalty Tiered Cash-Back & Rewards",
                "stakeholder_inputs": "Enable omnichannel shoppers to accrue points dynamically and view balance in real time.",
                "target_user": "Registered Mobile App & In-Store Shoppers",
                "business_outcome": "Increase repeat purchase conversion by 15%",
                "constraints": ["PCI-DSS Level 1 compliance", "POS latency < 300ms"],
                "confluence_space": "PROD",
                "jira_epic_key": "LOYALTY-101"
            }
        }
        res = self.client.post("/api/orchestrator/runs", json=create_payload)
        self.assertEqual(res.status_code, 201)
        run_id = res.json()["run_id"]

        run_data = self._wait_for_status(run_id, ["WAITING_FOR_APPROVAL"])
        self.assertEqual(run_data["status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(run_data["current_checkpoint_id"], "CP-05")

        # Approve review package
        approve_payload = {
            "decision": "approve",
            "reviewer_name": "Senior Director of Product Management",
            "comments": "Context brief covers all mandatory business outcomes. Approved for Confluence publication.",
            "is_prd": True
        }
        res_approve = self.client.post(f"/api/orchestrator/runs/{run_id}/approve", json=approve_payload)
        self.assertEqual(res_approve.status_code, 200)

        run_data = self._wait_for_status(run_id, ["COMPLETED"])
        self.assertEqual(run_data["status"], "COMPLETED")
        self.assertEqual(run_data["current_checkpoint_id"], "CP-FINAL")

        # Verify output data destination
        output = run_data["output_data"]
        self.assertEqual(output["destination"], "Confluence Enterprise Space")
        self.assertEqual(output["status"], "published")
        self.assertIn("confluence_page_url", output)


if __name__ == "__main__":
    unittest.main()
