import os
import unittest
from pathlib import Path

from src.services.workflow_service import WorkflowOrchestratorService
from src.mcp import InProcessMCPClient, MockSkillEngine, MockContextEngine


class TestWorkflowEndToEnd(unittest.TestCase):
    """
    End-to-End integration test suite for the PRD Generator workflow.
    Tests real dynamic connections between Document Extractor, Mock MCP Engines,
    Context Analyzer, Gap Analyzer, PRD Generator, PRD Reviewer, and Publish Service.
    """

    @classmethod
    def setUpClass(cls):
        cls.base_dir = Path(__file__).resolve().parents[1]
        cls.sample_data_dir = cls.base_dir / "sample_data"
        cls.orchestrator = WorkflowOrchestratorService()

    def test_e2e_kyc_workflow(self):
        """
        TC-001 & E2E: Automated KYC & Identity Verification
        Tests complete pipeline from document upload -> MCP skill/context retrieval -> PRD generation -> Review -> Publish
        """
        doc_path = self.sample_data_dir / "user_onboarding_kyc_brd.md"
        self.assertTrue(doc_path.exists(), f"Sample doc not found at {doc_path}")

        result = self.orchestrator.run_workflow_from_file(
            file_path=str(doc_path),
            active_team_id="team-identity-product",
            target_publish_platform="both"
        )

        # 1. Overall Status
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["document_name"], "user_onboarding_kyc_brd.md")

        # 2. Context Analysis & MCP Dynamic Retrieval
        ctx = result["context_analysis"]
        self.assertIsNotNone(ctx["problem_statement"])
        self.assertIsNotNone(ctx["business_goal"])
        self.assertGreaterEqual(ctx["evidence_count"], 1)
        self.assertGreaterEqual(len(ctx["mcp_skills"]), 1)

        # 3. Gap Analysis
        gap = result["gap_analysis"]
        self.assertTrue(gap["is_sufficient"])
        self.assertGreaterEqual(gap["sufficiency_score"], 70)

        # 4. PRD Review Quality
        review = result["review_result"]
        self.assertTrue(review["passed"])
        self.assertGreaterEqual(review["quality_score"], 80)

        # 5. HITL Bypassed
        hitl = result["hitl_review"]
        self.assertEqual(hitl["status"], "bypassed")

        # 6. Publish Receipt
        publish = result["publish_receipt"]
        self.assertEqual(publish["status"], "published")
        self.assertIn("confluence", publish["publications"])
        self.assertIn("jira", publish["publications"])

        # 7. Final PRD Markdown
        prd_md = result["final_prd_markdown"]
        self.assertIn("# ", prd_md)
        self.assertIn("problem statement", prd_md.lower())
        self.assertIn("acceptance criteria", prd_md.lower())

    def test_e2e_order_fulfillment_workflow(self):
        """
        E2E: Real-Time Order Fulfillment & Shipment Tracking
        Validates dynamic domain recognition, milestone event modeling, and publication.
        """
        doc_path = self.sample_data_dir / "order_fulfillment_tracking_brd.md"
        self.assertTrue(doc_path.exists())

        result = self.orchestrator.run_workflow_from_file(
            file_path=str(doc_path),
            active_team_id="team-logistics-product",
            target_publish_platform="both"
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["review_result"]["passed"])
        self.assertGreaterEqual(result["review_result"]["quality_score"], 80)

        # Verify publication details
        pub = result["publish_receipt"]
        self.assertIn("pub-", pub["publication_id"])
        self.assertIn("jira", pub["publications"])
        self.assertIn("confluence", pub["publications"])

    def test_e2e_cloud_cost_optimizer_workflow(self):
        """
        E2E: Automated Cloud Cost Optimizer (FinOps)
        Tests infrastructure rightsizing and FinOps telemetry analysis.
        """
        doc_path = self.sample_data_dir / "cloud_cost_optimizer_brd.md"
        self.assertTrue(doc_path.exists())

        result = self.orchestrator.run_workflow_from_file(
            file_path=str(doc_path),
            active_team_id="team-finops-cloud",
            target_publish_platform="confluence"
        )

        self.assertEqual(result["status"], "completed")
        self.assertIn("confluence", result["publish_receipt"]["publications"])
        self.assertNotIn("jira", result["publish_receipt"]["publications"])

    def test_e2e_conflicting_requirements_detection(self):
        """
        TC-006: Contradictory Inputs & Conflict Handling
        Validates that Gap Analyzer identifies contradictory constraints (manual review vs straight-through).
        """
        doc_path = self.sample_data_dir / "conflicting_requirements_brd.md"
        self.assertTrue(doc_path.exists())

        result = self.orchestrator.run_workflow_from_file(
            file_path=str(doc_path),
            active_team_id="team-transaction-processing"
        )

        self.assertIn("gap_analysis", result)
        gap = result["gap_analysis"]
        # Must detect conflicts or unvalidated assumptions
        self.assertTrue(len(gap.get("detected_conflicts", [])) > 0 or len(gap.get("unvalidated_assumptions", [])) > 0)

    def test_e2e_minimal_input_handling(self):
        """
        TC-003: Minimal Input Generation
        Validates that the orchestrator handles sparse input documents and infers missing context gracefully.
        """
        doc_path = self.sample_data_dir / "minimal_input_brd.md"
        self.assertTrue(doc_path.exists())

        result = self.orchestrator.run_workflow_from_file(
            file_path=str(doc_path),
            active_team_id="team-growth-product"
        )

        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(result["final_prd_markdown"])
        self.assertGreater(len(result["final_prd_markdown"]), 200)

    def test_direct_mcp_client_rpc_connection(self):
        """
        Validates direct programmatic MCP JSON-RPC 2.0 communication.
        """
        client = InProcessMCPClient()

        # 1. Test skill discovery
        skill_res = client.discover_skills(
            capability_need="prd_generation",
            domain="Product & Engineering"
        )
        self.assertEqual(skill_res["request"]["jsonrpc"], "2.0")
        self.assertEqual(skill_res["response"]["jsonrpc"], "2.0")
        self.assertGreaterEqual(len(skill_res["skills"]), 1)
        self.assertEqual(skill_res["skills"][0]["skill_id"], "prd_generator")

        # 2. Test context retrieval
        ctx_res = client.retrieve_context(
            query_text="Create a PRD/context brief for improving biometric authentication in mobile app.",
            active_team_id="team-mobile-auth"
        )
        self.assertEqual(ctx_res["request"]["jsonrpc"], "2.0")
        self.assertEqual(ctx_res["response"]["jsonrpc"], "2.0")
        pkg = ctx_res["context_package"]
        self.assertIn("context_package_id", pkg)
        self.assertGreaterEqual(len(pkg["retrieved_references"]), 3)


if __name__ == "__main__":
    unittest.main()
