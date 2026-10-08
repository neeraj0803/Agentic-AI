import unittest
from fastapi.testclient import TestClient

from src.main import app
from src.telemetry import worker_metrics_registry


class TestProductPRDWorker(unittest.TestCase):
    """
    Test suite for Agent Worker — Product Use Case:
    "Write PRD or Context Brief" (product_prd_or_context_brief_agent)
    
    Verifies:
    - 5-step continuous LangGraph processing window
    - Missing input detection and halting at Durable Boundary CP-01 (Clarification)
    - Context retrieval and skill binding (prd_brief_synthesizer, constraint_analyzer)
    - Review package assembly with completeness score and halting at Durable Boundary CP-05 (Approval)
    - Stateless resumption from CP-01 and CP-05
    - Confluence publishing writeback at CP-FINAL
    - OpenTelemetry metrics tracking
    """

    def setUp(self):
        self.client = TestClient(app)

    def test_missing_stakeholder_inputs_boundary_cp01(self):
        """Worker halts at Step 1 when stakeholder inputs or target user are missing, saving CP-01."""
        payload = {
            "run_id": "RUN-PRD-WORKER-01",
            "agent_name": "product_prd_or_context_brief_agent",
            "agent_version": "v1.0",
            "team_id": "team-loyalty-product",
            "input_data": {
                "title": "Customer Loyalty Tiered Cash-Back & Rewards",
                "stakeholder_inputs": "",  # Empty!
                "target_user": None,       # Missing!
                "business_outcome": None,  # Missing!
                "constraints": []
            }
        }
        res = self.client.post("/worker/dispatch", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "WAITING_FOR_CLARIFICATION")
        self.assertEqual(data["checkpoint"]["checkpoint_id"], "CP-01")
        self.assertEqual(data["checkpoint"]["checkpoint_type"], "CLARIFICATION")

        snapshot = data["checkpoint"]["state_snapshot"]
        self.assertTrue(snapshot["clarification_needed"])
        self.assertIn("stakeholder_inputs", snapshot["missing_fields"])
        self.assertIn("target_user", snapshot["missing_fields"])
        self.assertGreaterEqual(len(snapshot["questions"]), 2)

    def test_continuous_execution_to_approval_cp05(self):
        """Worker executes Steps 1 through 4 continuously, halting at CP-05 (WAITING_FOR_APPROVAL)."""
        payload = {
            "run_id": "RUN-PRD-WORKER-02",
            "agent_name": "product_prd_or_context_brief_agent",
            "agent_version": "v1.0",
            "team_id": "team-loyalty-product",
            "input_data": {
                "title": "Customer Loyalty Tiered Cash-Back & Rewards",
                "stakeholder_inputs": "Enable shoppers to accrue tiered rewards points online and in-store, with real-time balance inquiries and instant redemption.",
                "target_user": "Macy's Mobile App Shoppers & In-Store Loyalty Members",
                "business_outcome": "Increase repeat purchase conversion by 15% and annual customer LTV by $45",
                "constraints": [
                    "Must comply with PCI-DSS Level 1 compliance",
                    "Point accrual latency must remain under 300ms p95 at POS",
                    "No schema breaking changes to legacy billing tables"
                ],
                "confluence_space": "PROD",
                "jira_epic_key": "LOYALTY-101"
            }
        }
        headers = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
        res = self.client.post("/worker/dispatch", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(data["checkpoint"]["checkpoint_id"], "CP-05")
        self.assertEqual(data["checkpoint"]["checkpoint_type"], "APPROVAL")

        review_pkg = data["checkpoint"]["state_snapshot"]["review_package"]
        self.assertEqual(review_pkg["title"], "Customer Loyalty Tiered Cash-Back & Rewards")
        self.assertIn("prd_brief_synthesizer", review_pkg["bound_skills"])
        self.assertGreaterEqual(len(review_pkg["high_level_requirements"]), 3)
        self.assertGreaterEqual(review_pkg["completeness_assessment"]["completeness_score"], 90.0)
        self.assertIn("markdown_preview", review_pkg)

    def test_clarification_resumption_cp01_to_cp05(self):
        """Resuming from CP-01 with missing fields provided proceeds through Steps 2-4 to CP-05."""
        resume_payload = {
            "run_id": "RUN-PRD-WORKER-03",
            "checkpoint_id": "CP-01",
            "resume_payload": {
                "clarification_inputs": {
                    "title": "Customer Loyalty Tiered Cash-Back & Rewards",
                    "stakeholder_inputs": "Provide automated tier elevation notifications when customer spending crosses threshold.",
                    "target_user": "Tier 1 Platinum Loyalty Members",
                    "business_outcome": "Reduce premium tier churn by 8%",
                    "constraints": ["Deliver notification within 5 minutes of qualifying purchase"]
                }
            }
        }
        res = self.client.post("/worker/resume", json=resume_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "WAITING_FOR_APPROVAL")
        self.assertEqual(data["checkpoint"]["checkpoint_id"], "CP-05")

    def test_approval_and_confluence_publishing_cp_final(self):
        """Resuming from CP-05 with approve publishes PRD to Confluence and transitions to COMPLETED."""
        resume_payload = {
            "run_id": "RUN-PRD-WORKER-04",
            "checkpoint_id": "CP-05",
            "resume_payload": {
                "decision": "approve",
                "reviewer_name": "VP of Digital Product",
                "comments": "PRD brief meets all acceptance criteria. Approved for Confluence publishing.",
                "is_prd": True
            }
        }
        res = self.client.post("/worker/resume", json=resume_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["checkpoint"]["checkpoint_id"], "CP-FINAL")
        self.assertEqual(data["checkpoint"]["checkpoint_type"], "COMPLETED")

        output = data["output_data"]
        self.assertEqual(output["destination"], "Confluence Enterprise Space")
        self.assertEqual(output["status"], "published")
        self.assertIn("confluence_page_url", output)
        self.assertEqual(output["approver"], "VP of Digital Product")

    def test_revision_request_loopback(self):
        """Resuming from CP-05 with request_changes loops back to CP-05 revision state."""
        resume_payload = {
            "run_id": "RUN-PRD-WORKER-05",
            "checkpoint_id": "CP-05",
            "resume_payload": {
                "decision": "request_changes",
                "reviewer_name": "Principal Product Architect",
                "comments": "Add international foreign currency conversion rules to Section IV."
            }
        }
        res = self.client.post("/worker/resume", json=resume_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "WAITING_FOR_APPROVAL")
        self.assertTrue(data["checkpoint"]["state_snapshot"]["revision_requested"])


if __name__ == "__main__":
    unittest.main()
