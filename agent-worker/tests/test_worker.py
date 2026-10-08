import unittest
from fastapi.testclient import TestClient

from src.main import app
from src.graph.worker_graph import worker_executor
from src.telemetry import worker_metrics_registry


class TestAgentWorker(unittest.TestCase):
    """
    Enterprise Test Suite for Agent Worker:
    - Verifies the 5-step continuous processing window
    - Verifies context retrieval and dynamic skill selection
    - Verifies halts at Durable Boundaries: CP-01 (Clarification) and CP-05 (Human Approval)
    - Verifies resumption from checkpoints across stateless workers (CP-01 -> CP-05, CP-05 -> CP-FINAL)
    - Verifies OpenTelemetry metrics and W3C distributed tracing
    """

    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "UP")

    def test_worker_info_endpoint(self):
        res = self.client.get("/worker/info")
        self.assertEqual(res.status_code, 200)
        info = res.json()
        self.assertEqual(info["service"], "Agent Worker")
        self.assertIn("CP-01 (Clarification)", info["durable_boundaries"])
        self.assertEqual(len(info["nodes"]), 5)

    def test_step1_missing_ac_boundary(self):
        """Worker halts at Step 1 when AC is missing, saving CP-01."""
        payload = {
            "run_id": "RUN-WORKER-01",
            "agent_name": "qe_test_case_generation_agent",
            "agent_version": "v1.0",
            "team_id": "team-qe",
            "input_data": {
                "jira_story_id": "CHK-NO-AC",
                "acceptance_criteria": []
            }
        }
        res = self.client.post("/worker/dispatch", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "WAITING_FOR_CLARIFICATION")
        self.assertEqual(data["checkpoint"]["checkpoint_id"], "CP-01")
        self.assertIn("questions", data["checkpoint"]["state_snapshot"])

    def test_steps1_to_4_continuous_execution_to_approval(self):
        """Worker executes Steps 1 through 4 continuously, halting at CP-05 (WAITING_FOR_APPROVAL)."""
        payload = {
            "run_id": "RUN-WORKER-02",
            "agent_name": "qe_test_case_generation_agent",
            "agent_version": "v1.0",
            "team_id": "team-qe",
            "input_data": {
                "jira_story_id": "CHK-9001",
                "application_name": "Checkout Cart",
                "acceptance_criteria": [
                    "Apply promo discount code",
                    "Do not allow stacking expired coupons",
                    "Display remaining cart total"
                ],
                "target_output_format": "xray_bdd"
            }
        }
        headers = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
        res = self.client.post("/worker/dispatch", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(data["checkpoint"]["checkpoint_id"], "CP-05")
        review_pkg = data["checkpoint"]["state_snapshot"]["review_package"]
        self.assertGreaterEqual(review_pkg["total_scenarios"], 4)
        self.assertIn("bound_skills", review_pkg)
        self.assertIn("coverage_matrix", data["checkpoint"]["state_snapshot"])

    def test_resumption_from_cp01_clarification(self):
        """Resuming from CP-01 with clarified criteria continues through Steps 2-4 to CP-05."""
        resume_payload = {
            "run_id": "RUN-WORKER-01-RESUME",
            "checkpoint_id": "CP-01",
            "resume_payload": {
                "clarification_inputs": {
                    "jira_story_id": "CHK-REFUND-01",
                    "acceptance_criteria": [
                        "Refund amount cannot exceed original charge",
                        "Emit payment.refunded webhook"
                    ]
                }
            }
        }
        res = self.client.post("/worker/resume", json=resume_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(data["checkpoint"]["checkpoint_id"], "CP-05")

    def test_step5_approval_and_writeback(self):
        """Resuming from CP-05 with approve publishes output and transitions to COMPLETED."""
        resume_payload = {
            "run_id": "RUN-WORKER-03",
            "checkpoint_id": "CP-05",
            "resume_payload": {
                "decision": "approve",
                "reviewer_name": "Lead QE Architect"
            }
        }
        res = self.client.post("/worker/resume", json=resume_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["checkpoint"]["checkpoint_id"], "CP-FINAL")
        self.assertIn("output_data", data)
        self.assertEqual(data["output_data"]["status"], "published")
        self.assertIn("published_keys", data["output_data"])

    def test_step5_request_changes_revision(self):
        """Resuming from CP-05 with request_changes loops back to CP-05 revision state."""
        resume_payload = {
            "run_id": "RUN-WORKER-04",
            "checkpoint_id": "CP-05",
            "resume_payload": {
                "decision": "request_changes",
                "reviewer_name": "Senior Product Owner",
                "comments": "Add security test scenario for SQL injection in promo field"
            }
        }
        res = self.client.post("/worker/resume", json=resume_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "WAITING_FOR_APPROVAL")
        self.assertTrue(data["checkpoint"]["state_snapshot"]["revision_requested"])

    def test_worker_telemetry_metrics(self):
        """Verifies that OpenTelemetry metrics capture internal node latencies and skill usage."""
        res = self.client.get("/metrics")
        self.assertEqual(res.status_code, 200)
        metrics = res.json()

        self.assertEqual(metrics["service"], "agent-worker")
        self.assertIn("node_performance", metrics)
        self.assertIn("skills_bound", metrics)
        self.assertIn("checkpoints_emitted", metrics)
        self.assertGreater(metrics["total_test_scenarios_generated"], 0)


if __name__ == "__main__":
    unittest.main()
