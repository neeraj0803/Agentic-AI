import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.config import ROOT_DIR, SESSION_DIR
from src.main import app
from src.session_manager import load_workflow_session_yaml, save_session_file


class TestWorkflowE2E(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data.get("status"), ["ok", "UP"])
        self.assertEqual(data.get("agent"), "QE-201-draft-test-cases-from-jira")

    def test_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "online")

    def test_workflow_run_no_workflow_error(self):
        response = self.client.post(
            "/workflow/run",
            content=b"",
            headers={"Content-Type": "application/x-yaml"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("detail"), "got no workflow")

    def test_workflow_run_dynamic_workflow(self):
        input_yaml_path = ROOT_DIR / "Input.yaml"
        self.assertTrue(input_yaml_path.exists())
        yaml_bytes = input_yaml_path.read_bytes()

        response = self.client.post(
            "/workflow/run",
            content=yaml_bytes,
            headers={"Content-Type": "application/x-yaml"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        text = response.text

        # First node should start and complete
        self.assertIn("node_start", text)
        self.assertIn("context_retriever", text)
        self.assertIn("node_complete", text)

        # Artifact generation and workflow completion
        self.assertIn("prepare_test_package_artifacts", text)
        self.assertIn("workflow_complete", text)

    def test_workflow_conversation_and_session(self):
        # Create a mock session file
        session_id = "test-session-conv-e2e"
        conv_id = "test-conv-e2e"
        mock_state = {
            "conversation_id": conv_id,
            "workflow_session_id": session_id,
            "workflow_id": "QE-201-draft-test-cases-from-jira",
            "status": "completed",
            "validated_inputs": {"jira_story_or_epic_id": "AIDLC-102"},
            "nodes": [
                {"id": "context_retriever", "output": {"issue_key": "AIDLC-102"}},
                {"id": "skill_retriever", "output": {"skills": ["context_brief_generator"]}},
            ],
            "context_brief": {"story_key": "AIDLC-102", "risk_factors": ["Security"]},
            "drafted_tests": {
                "manual_test_cases": [
                    {"test_id": "TC-01", "title": "Test Auth", "type": "Functional", "priority": "High"}
                ]
            },
        }
        save_session_file(mock_state)

        # GET session
        get_res = self.client.get(f"/workflow/session/{session_id}")
        self.assertEqual(get_res.status_code, 200)
        sess_data = get_res.json()
        self.assertEqual(sess_data["workflow_session_id"], session_id)

        # POST conversation
        conv_res = self.client.post(
            "/workflow/conversation",
            json={
                "workflow_session_id": session_id,
                "user_query": "Please show test cases",
            },
        )
        self.assertEqual(conv_res.status_code, 200)
        conv_data = conv_res.json()
        self.assertEqual(conv_data["workflow_session_id"], session_id)
        self.assertIn("TC-01", conv_data["answer"])



if __name__ == "__main__":
    unittest.main()
