import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.config import get_session_dir
from src.main import app


class TestWorkflowOrchestrator(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.session_dir = get_session_dir()
        self.session_dir.mkdir(exist_ok=True, parents=True)


    def test_health_check_orchestrator(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "UP")
        self.assertEqual(data.get("orchestrator"), "ok")

    def test_workflow_run_invalid_yaml(self):
        res = self.client.post(
            "/workflow/run",
            content=": : invalid yaml",
            headers={"Content-Type": "application/x-yaml"}
        )
        self.assertEqual(res.status_code, 400)

    def test_workflow_run_empty_nodes(self):
        payload = {
            "workflow_session_id": "test-session-empty",
            "type": "Agent",
            "nodes": []
        }
        res = self.client.post(
            "/workflow/run",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 400)

    def test_workflow_run_passthrough_node(self):
        payload = {
            "workflow_session_id": "test-session-passthrough",
            "type": "Agent",
            "nodes": [
                {
                    "node_id": "step_1",
                    "node_name": "First Step",
                    "node_type": "passthrough",
                    "next_node": "end"
                }
            ]
        }
        res = self.client.post(
            "/workflow/run",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.headers.get("content-type", ""))
        content = res.text
        self.assertIn("node_start", content)
        self.assertIn("node_complete", content)
        self.assertIn("workflow_complete", content)

    @patch("src.nodes.agent_node.call_llm", return_value="Simulated LLM Output Content")
    def test_workflow_run_agent_node(self, mock_llm):
        payload = {
            "workflow_session_id": "test-session-agent",
            "type": "Agent",
            "nodes": [
                {
                    "node_id": "agent_1",
                    "node_name": "Researcher Agent",
                    "node_type": "agent",
                    "variables": {
                        "system_message": "You are a test assistant.",
                        "user_prompt": "Analyze {{workflow_session_id}}"
                    },
                    "next_node": "end"
                }
            ]
        }
        res = self.client.post(
            "/workflow/run",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.headers.get("content-type", ""))
        content = res.text
        self.assertIn("node_start", content)
        self.assertIn("node_complete", content)
        self.assertIn("workflow_complete", content)

    def test_workflow_run_and_hitl_decision(self):
        session_id = "test-session-hitl-flow"
        payload = {
            "workflow_session_id": session_id,
            "type": "Agent",
            "nodes": [
                {
                    "node_id": "passthrough_1",
                    "node_name": "Initial Prep",
                    "node_type": "passthrough",
                    "next_node": "approval_gate"
                },
                {
                    "node_id": "approval_gate",
                    "node_name": "Human Review",
                    "node_type": "hitl",
                    "variables": {
                        "message": "Please approve or reject this test workflow"
                    },
                    "next_node": "final_step"
                },
                {
                    "node_id": "final_step",
                    "node_name": "Post Approval Execution",
                    "node_type": "passthrough",
                    "next_node": "end"
                }
            ]
        }
        # Run workflow up to HITL interrupt
        res1 = self.client.post(
            "/workflow/run",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(res1.status_code, 200)
        self.assertIn("human_input_required", res1.text)

        # Submit approve decision
        decision_payload = {
            "workflow_session_id": session_id,
            "decision": "approve",
            "feedback": "LGTM",
            "reviewed_by": "TestReviewer"
        }
        res2 = self.client.post(
            "/workflow/human-decision",
            json=decision_payload
        )
        self.assertEqual(res2.status_code, 200)
        self.assertIn("workflow_complete", res2.text)


if __name__ == "__main__":
    unittest.main()
