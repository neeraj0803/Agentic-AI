import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.context_service import ContextAnalyzerService
from src.services.confluence_context_service import ConfluenceContextService
from src.services.document_extractor_service import DocumentExtractorService
from src.services.prd_service import PRDGeneratorService


class TestDocumentExtractor(unittest.TestCase):
    def test_extracts_text_from_txt_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "sample.txt"
            file_path.write_text(
                "Problem: support teams cannot find trusted documents.\nGoal: reduce repeat answers.",
                encoding="utf-8",
            )

            extracted = DocumentExtractorService.extract_text(str(file_path))

            self.assertIn("Problem:", extracted)
            self.assertIn("reduce repeat answers", extracted.lower())

    def test_extracts_text_from_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "sample.md"
            file_path.write_text(
                "# Context\n\n## Problem\nEmployees struggle to find the right documentation.\n",
                encoding="utf-8",
            )

            extracted = DocumentExtractorService.extract_text(str(file_path))

            self.assertIn("Employees struggle", extracted)
            self.assertIn("## Problem", extracted)


class TestContextAnalyzer(unittest.TestCase):
    def test_analyzes_extracted_document_into_business_context(self):
        mock_response = json.dumps(
            {
                "problem_statement": "Employees cannot find trusted enterprise documents quickly.",
                "business_goal": "Reduce time to find documents and lower repeat support work.",
                "evidence": [
                    "Employees spend 8 minutes searching for knowledge.",
                    "Support teams answer duplicate questions daily.",
                ],
                "users": ["Employees", "Support Engineers", "Operations Teams"],
                "assumptions": ["Documents already exist in approved repositories."],
                "constraints": ["No additional licensing costs.", "Delivery within 8 weeks."],
            }
        )

        with mock.patch("src.graph.nodes.context_analyzer_node.LLMService.generate", return_value=mock_response):
            result = ContextAnalyzerService().analyze(
                document_name="requirements.txt",
                extracted_text="Employees struggle to find the right enterprise documentation. Support teams answer repeat questions daily.",
            )

        self.assertEqual(result["problem_statement"], "Employees cannot find trusted enterprise documents quickly.")
        self.assertEqual(result["business_goal"], "Reduce time to find documents and lower repeat support work.")
        self.assertIn("Employees", result["users"])
        self.assertIn("Delivery within 8 weeks.", result["constraints"])


class TestConfluenceContextService(unittest.TestCase):
    def test_fetches_and_normalizes_mock_confluence_page(self):
        page = ConfluenceContextService().fetch_page("requirements-demo")

        self.assertEqual(page["page_id"], "requirements-demo")
        self.assertIn("problem_statement", page)
        self.assertIn("supporting_evidence", page)
        self.assertIn("business_goal", page)
        self.assertIn("users", page)
        self.assertTrue(page["problem_statement"])
        self.assertTrue(page["supporting_evidence"])
        self.assertTrue(page["business_goal"])


class TestPRDGenerator(unittest.TestCase):
    def test_generates_prd_from_valid_context(self):
        payload = {
            "problem": "Employees cannot find trusted enterprise documents quickly.",
            "users": ["Employees", "Support Engineers"],
            "needs": ["Find approved knowledge quickly", "Reduce repeat support inquiries"],
            "expected_impact": ["Search time reduced by 50%", "Support productivity improved"],
            "scope": {
                "in_scope": ["Knowledge search", "Search optimization"],
                "out_of_scope": ["Workflow automation outside knowledge retrieval"],
            },
            "assumptions": ["Documents already exist in approved repositories."],
            "constraints": ["No additional licensing costs.", "Delivery within 8 weeks."],
        }

        llm_response = json.dumps(
            {
                "problem": payload["problem"],
                "users": payload["users"],
                "needs": payload["needs"],
                "expected_impact": payload["expected_impact"],
                "scope": payload["scope"],
                "assumptions": payload["assumptions"],
                "constraints": payload["constraints"],
            }
        )

        with mock.patch.object(PRDGeneratorService, "_llm_available", return_value=True), \
             mock.patch.object(PRDGeneratorService, "_preferred_provider", return_value="gemini"), \
             mock.patch("src.services.prd_service.LLMService.generate", return_value=llm_response):
            prd = PRDGeneratorService().generate(payload)

        self.assertIn("# Product Requirements Document", prd)
        self.assertIn("## Problem", prd)
        self.assertIn("Employees cannot find trusted enterprise documents quickly.", prd)
        self.assertIn("## Users", prd)
        self.assertIn("## Needs", prd)
        self.assertIn("## Scope", prd)
        self.assertTrue((ROOT / "prd_output.md").exists())

    def test_rejects_context_missing_problem_statement(self):
        with self.assertRaises(ValueError):
            PRDGeneratorService().generate({
                "users": ["Employees"],
                "needs": ["Find documents faster"],
            })


if __name__ == "__main__":
    unittest.main()
