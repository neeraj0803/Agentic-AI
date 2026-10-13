import json
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.config import ROOT_DIR, SESSION_DIR
from src.graph.workflow_orchestrator import (
    _heuristic_feedback_interpretation,
    get_checkpoint_nodes,
    interpret_human_feedback,
)
from src.main import app
from src.session_manager import load_workflow_session_yaml, save_session_file


class TestCheckpointAndFeedback(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

    def test_checkpoint_nodes_detection(self):
        raw_nodes = [
            {"id": "node_1", "checkpoint": True},
            {"id": "node_2", "checkpoint": False},
            {"id": "node_3", "checkpoint": "true"},
            {"id": "node_4", "checkpoint": True},  # Last node checkpoint should be ignored
        ]
        cps = get_checkpoint_nodes(raw_nodes)
        self.assertEqual(cps, ["node_1", "node_3"])

    def test_heuristic_feedback_restart(self):
        node_ids = ["n1", "n2", "n3", "n4"]
        decision = _heuristic_feedback_interpretation(
            feedback="we need to run the whole workflow again from start",
            current_node="n3",
            node_ids=node_ids,
            next_node="n4",
        )
        self.assertEqual(decision["action"], "restart")
        self.assertEqual(decision["target_node"], "n1")

    def test_heuristic_feedback_specific_node(self):
        node_ids = ["context_retriever", "skill_retriever", "test_cases_generation", "prepare_test_package_artifacts"]
        decision = _heuristic_feedback_interpretation(
            feedback="please rerun skill_retriever",
            current_node="test_cases_generation",
            node_ids=node_ids,
            next_node="prepare_test_package_artifacts",
        )
        self.assertEqual(decision["action"], "run_from_node")
        self.assertEqual(decision["target_node"], "skill_retriever")

    def test_heuristic_feedback_ordinal_node(self):
        node_ids = ["n1", "n2", "n3", "n4"]
        decision = _heuristic_feedback_interpretation(
            feedback="run from 2nd node",
            current_node="n3",
            node_ids=node_ids,
            next_node="n4",
        )
        self.assertEqual(decision["action"], "run_from_node")
        self.assertEqual(decision["target_node"], "n2")

    def test_heuristic_feedback_rework_current(self):
        node_ids = ["n1", "n2", "n3"]
        decision = _heuristic_feedback_interpretation(
            feedback="rework this node with additional edge cases",
            current_node="n2",
            node_ids=node_ids,
            next_node="n3",
        )
        self.assertEqual(decision["action"], "rework_current")
        self.assertEqual(decision["target_node"], "n2")

    def test_heuristic_feedback_proceed(self):
        node_ids = ["n1", "n2", "n3"]
        decision = _heuristic_feedback_interpretation(
            feedback="looks great, proceed please",
            current_node="n1",
            node_ids=node_ids,
            next_node="n2",
        )
        self.assertEqual(decision["action"], "proceed")
        self.assertEqual(decision["target_node"], "n2")

    def test_feedback_endpoint_not_found(self):
        res = self.client.post(
            "/workflow/feedback",
            json={
                "conversation_id": "non-existent-conv",
                "workflow_session_id": "non-existent-sess",
                "feedback": "proceed",
            },
        )
        self.assertEqual(res.status_code, 404)

    def test_workflow_run_no_workflow_error(self):
        res = self.client.post(
            "/workflow/run",
            content=b"",
            headers={"Content-Type": "application/x-yaml"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("detail"), "got no workflow")

    def test_feedback_resumes_workflow(self):
        # 1. Run dynamic workflow from Input.yaml to hit first checkpoint
        input_yaml_path = ROOT_DIR / "Input.yaml"
        self.assertTrue(input_yaml_path.exists())
        yaml_bytes = input_yaml_path.read_bytes()

        run_res = self.client.post(
            "/workflow/run",
            content=yaml_bytes,
            headers={"Content-Type": "application/x-yaml"},
        )
        self.assertEqual(run_res.status_code, 200)
        self.assertIn("human_input_required", run_res.text)

        # Parse session id from SSE stream
        sess_id = None
        conv_id = None
        for line in run_res.text.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "workflow_session_id" in data:
                    sess_id = data["workflow_session_id"]
                    conv_id = data.get("conversation_id")
                    break

        self.assertIsNotNone(sess_id)

        # 2. Submit feedback to proceed to next node
        fb_res = self.client.post(
            "/workflow/feedback",
            json={
                "conversation_id": conv_id,
                "workflow_session_id": sess_id,
                "feedback": "looks good, proceed",
            },
        )
        self.assertEqual(fb_res.status_code, 200)
        self.assertIn("feedback_acknowledged", fb_res.text)
        self.assertIn("skill_retriever", fb_res.text)


if __name__ == "__main__":
    unittest.main()

