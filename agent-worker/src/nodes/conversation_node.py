import json
from pathlib import Path
from typing import Any

from ..config import get_session_dir
from .agent_node import call_llm

SESSION_DIR = get_session_dir()


def load_workflow_session(workflow_session_id: str) -> dict[str, Any]:
    if not workflow_session_id or Path(workflow_session_id).name != workflow_session_id:
        raise ValueError("workflow_session_id must be a non-empty session identifier.")

    session_dir = get_session_dir()
    matching_workflows: list[dict[str, Any]] = []
    if not session_dir.exists():
        raise FileNotFoundError(f"No workflow found for session {workflow_session_id}.")


    for file_path in session_dir.glob("*.json"):
        if not file_path.name.startswith(f"{workflow_session_id}-"):
            continue

        with file_path.open("r", encoding="utf-8") as file:
            workflow = json.load(file)
        if (
            isinstance(workflow, dict)
            and workflow.get("workflow_session_id") == workflow_session_id
        ):
            matching_workflows.append(workflow)

    if not matching_workflows:
        raise FileNotFoundError(f"No workflow found for session {workflow_session_id}.")
    if len(matching_workflows) > 1:
        raise ValueError(f"Multiple workflows found for session {workflow_session_id}.")

    return matching_workflows[0]


def conversation_node(workflow_session_id: str, user_query: str) -> str:
    workflow = load_workflow_session(workflow_session_id)
    system_message = (
        "Answer the user's question using only the supplied workflow JSON as context. "
        "If the workflow does not contain enough information, say so clearly."
    )
    user_prompt = (
        f"Workflow JSON:\n{json.dumps(workflow, ensure_ascii=False, indent=2)}\n\n"
        f"User query:\n{user_query}"
    )
    return call_llm(system_message, user_prompt)
