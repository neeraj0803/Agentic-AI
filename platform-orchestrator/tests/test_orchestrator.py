import asyncio
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

# Add platform-orchestrator root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import app
from src.models.run_models import CreateRunRequest, ClarificationRequest, ApprovalRequest
from src.services.checkpoint_service import checkpoint_service
from src.services.queue_service import queue_service
from src.services.run_lifecycle_service import run_lifecycle_service
from src.services.worker_client import worker_client
from src.storage.orchestrator_storage import OrchestratorStorage
from src.telemetry.metrics import metrics_registry


class TestPlatformOrchestrator(unittest.TestCase):
    """
    Test suite for Platform Orchestrator Service:
    - Run creation, version locking, and lifecycle transitions
    - Checkpoint persistence and durable boundary handling (CP-01, CP-05)
    - Clarification and Human-in-the-Loop approval resumption
    - Cancellation policy enforcement
    - OpenTelemetry metrics and health probes
    """

    def setUp(self):
        worker_client.use_mock = True
        try:
            self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            self.temp_dir = tempfile.TemporaryDirectory()

        self.db_path = Path(self.temp_dir.name) / "test_orchestrator.db"
        self.storage = OrchestratorStorage(db_path=str(self.db_path))

        # Direct service singletons to test storage
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

    def test_health_and_metrics_endpoints(self):
        """Verifies health and OpenTelemetry metrics endpoints."""
        health_res = self.client.get("/health")
        self.assertEqual(health_res.status_code, 200)
        self.assertEqual(health_res.json()["status"], "UP")

        metrics_res = self.client.get("/api/orchestrator/metrics")
        self.assertEqual(metrics_res.status_code, 200)
        data = metrics_res.json()
        self.assertIn("telemetry_metrics", data)
        self.assertIn("runs_created", data["telemetry_metrics"])

    def test_preflight_endpoint(self):
        """Validates standalone preflight verification endpoint."""
        payload = {
            "agent_identifier": "AG-201",
            "team_id": "team-checkout-qe",
            "user_id": "usr-architect-01",
            "inputs": {
                "jira_story_id": "CHK-5501",
                "acceptance_criteria": ["Support idempotency header"]
            }
        }
        res = self.client.post("/api/orchestrator/preflight", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["valid"])
        self.assertEqual(data["agent_id"], "AG-201")
        self.assertEqual(data["blockers_count"], 0)

    def test_run_creation_and_version_locking(self):
        """Validates run ID generation, version locking, and initial queuing."""
        payload = {
            "agent_name": "qe_test_case_generation_agent",
            "agent_version": "v1.0",
            "team_id": "team-checkout-qe",
            "policy_version": "2026.Q3",
            "skip_preflight": True,
            "input_data": {
                "jira_story_id": "CHK-5501",
                "application_name": "Checkout Payment Gateway",
                "acceptance_criteria": ["Support idempotency header", "Retry 3 times on 503"]
            }
        }
        res = self.client.post("/api/orchestrator/runs", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertTrue(data["run_id"].startswith("RUN-"))
        self.assertEqual(data["agent_name"], "qe_test_case_generation_agent")
        self.assertEqual(data["agent_version"], "v1.0")
        self.assertEqual(data["policy_version"], "2026.Q3")
        self.assertEqual(data["team_id"], "team-checkout-qe")

    def test_missing_input_clarification_cycle(self):
        """
        When input is missing mandatory acceptance criteria, the workflow must:
        1. Halt at CP-01 (WAITING_FOR_CLARIFICATION)
        2. Accept clarification inputs
        3. Resume to CP-05 (WAITING_FOR_APPROVAL)
        """
        payload = {
            "agent_name": "qe_test_case_generation_agent",
            "agent_version": "v1.0",
            "team_id": "team-checkout-qe",
            "skip_preflight": True,
            "input_data": {
                "jira_story_id": "CHK-EMPTY-AC",
                "acceptance_criteria": []  # Missing!
            }
        }
        create_res = self.client.post("/api/orchestrator/runs", json=payload)
        self.assertEqual(create_res.status_code, 201)
        run_id = create_res.json()["run_id"]

        # Wait until mock worker executes and halts at CP-01
        run_data = self._wait_for_status(run_id, ["WAITING_FOR_CLARIFICATION", "paused_for_validation", "FAILED"])
        self.assertIn(run_data["status"], ["WAITING_FOR_CLARIFICATION", "paused_for_validation"])
        self.assertEqual(run_data["current_checkpoint_id"], "CP-01")

        # 2. Check checkpoint metadata
        cp_res = self.client.get(f"/api/orchestrator/runs/{run_id}/checkpoints")
        self.assertEqual(cp_res.status_code, 200)
        checkpoints = cp_res.json()
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]["checkpoint_id"], "CP-01")

        # 3. Submit clarification
        clarify_payload = {
            "clarification_inputs": {
                "acceptance_criteria": [
                    "Payment retry limit is 3 attempts on HTTP 503",
                    "Do not retry on HTTP 402 card declined"
                ]
            },
            "notes": "Added acceptance criteria as requested."
        }
        clarify_res = self.client.post(f"/api/orchestrator/runs/{run_id}/clarify", json=clarify_payload)
        self.assertEqual(clarify_res.status_code, 200)
        updated_run = clarify_res.json()

        # Should advance to CP-05 (WAITING_FOR_APPROVAL)
        self.assertIn(updated_run["status"], ["WAITING_FOR_APPROVAL", "awaiting_approval"])
        self.assertEqual(updated_run["current_checkpoint_id"], "CP-05")

    def test_human_approval_and_completion_lifecycle(self):
        """
        Full journey test:
        1. Dispatch run with valid criteria -> lands at CP-05 (WAITING_FOR_APPROVAL)
        2. Submit human approval -> publishes to Xray -> transitions to COMPLETED
        """
        payload = {
            "agent_name": "qe_test_case_generation_agent",
            "team_id": "team-payments-pod",
            "skip_preflight": True,
            "input_data": {
                "jira_story_id": "CHK-6002",
                "application_name": "Apple Pay Integration",
                "acceptance_criteria": ["Support Apple Pay cryptographic tokens"]
            }
        }
        res = self.client.post("/api/orchestrator/runs", json=payload)
        run_id = res.json()["run_id"]

        # Wait until mock worker reaches CP-05
        run_data = self._wait_for_status(run_id, ["WAITING_FOR_APPROVAL", "awaiting_approval", "FAILED"])
        self.assertIn(run_data["status"], ["WAITING_FOR_APPROVAL", "awaiting_approval"])
        self.assertEqual(run_data["current_checkpoint_id"], "CP-05")

        # Submit human approval
        approval_payload = {
            "decision": "approve",
            "reviewer_name": "Principal QE Architect",
            "comments": "Coverage looks comprehensive. Approved for publishing."
        }
        appr_res = self.client.post(f"/api/orchestrator/runs/{run_id}/approve", json=approval_payload)
        self.assertEqual(appr_res.status_code, 200)
        final_data = appr_res.json()

        self.assertIn(final_data["status"], ["COMPLETED", "completed"])
        self.assertIsNotNone(final_data["output_data"])
        self.assertEqual(final_data["output_data"]["status"], "published")
        self.assertIn("Xray Test Management", final_data["output_data"]["destination"])

    def test_cancellation_policy(self):
        """Tests that orchestrator can cancel an active run."""
        payload = {
            "agent_name": "qe_test_case_generation_agent",
            "skip_preflight": True,
            "input_data": {"jira_story_id": "CHK-CANCEL", "acceptance_criteria": []}
        }
        res = self.client.post("/api/orchestrator/runs", json=payload)
        run_id = res.json()["run_id"]

        cancel_res = self.client.post(
            f"/api/orchestrator/runs/{run_id}/cancel",
            json={"reason": "User changed requirements"}
        )
        self.assertEqual(cancel_res.status_code, 200)
        self.assertIn(cancel_res.json()["status"], ["CANCELLED", "cancelled"])


if __name__ == "__main__":
    unittest.main()
