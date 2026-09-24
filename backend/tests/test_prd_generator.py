import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.prd_service import PRDGeneratorService
from src.services.confluence_context_service import MockConfluenceContextService


class TestPRDGenerator(unittest.TestCase):
    def test_generates_complete_prd_with_required_sections(self):
        context = {
            "problem_statement": "Employees struggle to find relevant enterprise documents and support teams repeatedly answer the same questions.",
            "business_goal": "Improve enterprise knowledge discovery using semantic search and retrieval.",
            "evidence": [
                "70% of surveyed employees struggle to find documents.",
                "Average search time is 8 minutes.",
                "Current search success rate is 45%."
            ],
            "users": ["Employees", "Support Engineers", "Operations Teams"],
            "assumptions": ["Documents already exist in approved repositories."],
            "constraints": ["Delivery within 8 weeks.", "No additional licensing costs."],
            "expected_users": 500,
            "requests_per_day": 20,
            "documents_per_day": 40,
            "growth_expectations": "high"
        }

        prd = PRDGeneratorService().generate(context)

        self.assertIn("1. EXECUTIVE SUMMARY", prd)
        self.assertIn("PROBLEM STATEMENT", prd)
        self.assertIn("SYSTEM OVERVIEW", prd)
        self.assertIn("AGENT IDENTIFICATION", prd)
        self.assertIn("MCP INTEGRATION DESIGN", prd)
        self.assertIn("MERMAID", prd)
        self.assertIn("Implementation Order", prd)


class TestMockConfluenceContextService(unittest.TestCase):
    def test_fetches_mock_confluence_page_fields(self):
        page = MockConfluenceContextService().fetch_page("requirements-demo")

        self.assertIn("problem_statement", page)
        self.assertIn("supporting_evidence", page)
        self.assertIn("business_goal", page)
        self.assertIn("application_indicator", page)
        self.assertIn("assumptions", page)
        self.assertIn("constraints", page)

        self.assertTrue(page["problem_statement"])
        self.assertTrue(page["supporting_evidence"])
        self.assertTrue(page["business_goal"])
        self.assertIn("new", page["application_indicator"].lower())


if __name__ == "__main__":
    unittest.main()
