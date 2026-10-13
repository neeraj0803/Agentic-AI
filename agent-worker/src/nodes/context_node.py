import copy
import json
import logging
from pathlib import Path
from typing import Any, Callable

from ..config import ROOT_DIR, get_mock_input_path

logger = logging.getLogger(__name__)


def create_context_node(
    node_def: dict[str, Any], workflow_spec: dict[str, Any]
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Factory to create a dynamic context retriever node."""
    node_id = node_def.get("id") or node_def.get("node_id") or "context_retriever"
    custom_path_str = node_def.get("mock_input_path") or node_def.get("context_file")
    default_mock_input = get_mock_input_path()
    custom_path = Path(custom_path_str) if custom_path_str else default_mock_input
    context_key = node_def.get("context_key", "input_context")
    selected_index = int(node_def.get("selected_index", 0))
    target_story_id = node_def.get("story_id")

    def context_retriever_node(state: dict[str, Any]) -> dict[str, Any]:
        state["status"] = "running"
        state["current_node"] = node_id

        # 1. Resolve context: from state if pre-populated, else load from file
        retrieved_context = state.get(context_key)
        source_description = "state"

        if not retrieved_context:
            target_file = custom_path if custom_path.is_absolute() else ROOT_DIR / custom_path
            if target_file.exists():
                try:
                    with target_file.open("r", encoding="utf-8") as f:
                        retrieved_context = json.load(f)
                    source_description = str(target_file.name)
                except Exception as exc:
                    logger.error("Failed to read context file %s: %s", target_file, exc)
                    retrieved_context = []
                    source_description = f"error: {exc}"
            else:
                logger.warning("Context file not found at %s", target_file)
                retrieved_context = []
                source_description = "not_found"

        # 2. Persist retrieved context into state
        state[context_key] = retrieved_context
        state["input_context"] = retrieved_context
        state["context_data"] = retrieved_context

        # 3. Determine active inputs for downstream consumers
        active_inputs: dict[str, Any] = {}
        if isinstance(retrieved_context, list) and retrieved_context:
            if target_story_id:
                # Find matching story
                matching = next(
                    (item for item in retrieved_context if isinstance(item, dict) and item.get("jira_story_or_epic_id") == target_story_id),
                    None,
                )
                if matching:
                    active_inputs = copy.deepcopy(matching)
                else:
                    active_inputs = copy.deepcopy(retrieved_context[0])
                    active_inputs["jira_story_or_epic_id"] = target_story_id
            elif 0 <= selected_index < len(retrieved_context):
                active_inputs = copy.deepcopy(retrieved_context[selected_index])
            else:
                active_inputs = copy.deepcopy(retrieved_context[0])
        elif isinstance(retrieved_context, dict):
            active_inputs = copy.deepcopy(retrieved_context)
            if target_story_id:
                active_inputs["jira_story_or_epic_id"] = target_story_id

        state["validated_inputs"] = active_inputs

        output: dict[str, Any] = {
            "status": "completed",
            "node_id": node_id,
            "source": source_description,
            "total_items": len(retrieved_context) if isinstance(retrieved_context, list) else (1 if retrieved_context else 0),
            "active_story_id": active_inputs.get("jira_story_or_epic_id", "N/A"),
            "context": retrieved_context,
        }

        state[f"{node_id}_output"] = output

        if "nodes" not in state or not isinstance(state["nodes"], list):
            state["nodes"] = []

        found = False
        for item in state.get("nodes", []):
            if item.get("node_id") == node_id or item.get("id") == node_id:
                item["output"] = output
                item["status"] = "completed"
                found = True
                break
        if not found:
            state["nodes"].append({
                "id": node_id,
                "node_id": node_id,
                "node_name": str(node_id).replace("_", " ").title(),
                "node_type": "agent",
                "output": output,
                "status": "completed",
            })

        return state


    return context_retriever_node

