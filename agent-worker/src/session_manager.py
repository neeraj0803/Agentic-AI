import copy
import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any
import uuid
import yaml

from .config import ROOT_DIR, get_session_dir

logger = logging.getLogger(__name__)

BASE_DIR = ROOT_DIR
SESSION_DIR = get_session_dir()


def get_session_file_path(conversation_id: str | None, workflow_session_id: str | None) -> Path:
    """Returns the standardized YAML file path in temp dir for a given session."""
    session_dir = get_session_dir()
    session_dir.mkdir(exist_ok=True, parents=True)
    safe_conv = re.sub(r"[^\w\-]", "_", conversation_id or "default-conversation")
    safe_sess = re.sub(r"[^\w\-]", "_", workflow_session_id or "session")
    return session_dir / f"{safe_conv}_{safe_sess}.yaml"


def capture_workflow_snapshot(
    state: dict[str, Any],
    current_node: str | None = None,
    next_node: str | None = None,
    status: str | None = None,
) -> Path:
    """
    Captures the complete workflow execution state and saves it to temp dir as a YAML file.
    Preserves all workflow metadata, node outputs, review history, and execution statuses.
    """
    snapshot = copy.deepcopy(state)

    # Core Identifiers
    conversation_id = snapshot.get("conversation_id")
    session_id = snapshot.get("workflow_session_id") or str(uuid.uuid4())
    snapshot["conversation_id"] = conversation_id
    snapshot["workflow_session_id"] = session_id
    snapshot.setdefault("workflow_id")
    snapshot.setdefault("version", "1.0.0")
    snapshot.setdefault("type", "Agent")

    # Status & Node pointers
    if status is not None:
        snapshot["status"] = status
    else:
        snapshot.setdefault("status", "running")

    if current_node is not None:
        snapshot["current_node"] = current_node
    else:
        snapshot.setdefault("current_node", "")

    if next_node is not None:
        snapshot["next_node"] = next_node
    else:
        snapshot.setdefault("next_node", "")

    snapshot.setdefault("agent", {})
    snapshot.setdefault("actors", {})
    snapshot.setdefault("channels", {})
    snapshot.setdefault("run_modes", {})
    snapshot.setdefault("inputs", [])
    snapshot.setdefault("validated_inputs", {})
    snapshot.setdefault("intake", {})
    snapshot.setdefault("context", {})
    snapshot.setdefault("context_data", {})
    snapshot.setdefault("skills", {})
    snapshot.setdefault("context_brief", {})
    snapshot.setdefault("model_policy_ref", "azure_standard_test_generation")
    snapshot.setdefault("artifacts", {})
    snapshot.setdefault("rework_count", 0)
    snapshot.setdefault("rework_feedback", "")
    snapshot.setdefault("review_history", [])
    snapshot.setdefault("publish_result", {})

    # Preserve or initialize node array
    # Preserve or initialize node array
    existing_nodes = snapshot.get("nodes", [])
    if existing_nodes and isinstance(existing_nodes, list):
        snapshot["nodes"] = [dict(n) for n in existing_nodes]
    else:
        graph_nodes = snapshot.get("graph", {}).get("nodes", [])
        nodes_state = []
        for node in graph_nodes:
            node_id = node.get("id") or node.get("node_id")
            node_copy = dict(node)
            node_copy.setdefault("node_id", node_id)
            node_copy.setdefault("id", node_id)
            node_copy.setdefault("node_name", node.get("name") or str(node_id).replace("_", " ").title())
            node_copy.setdefault("node_type", node.get("type") or node.get("node_type", "agent"))
            node_copy.setdefault("status", "pending")
            node_copy.setdefault("output", None)
            nodes_state.append(node_copy)
        snapshot["nodes"] = nodes_state

    # Graph edges: ensure edges are preserved or generated from next_node
    edges = snapshot.get("graph", {}).get("edges", []) or snapshot.get("edges", [])
    if not edges:
        edges = []
        for n in snapshot.get("nodes", []):
            src = n.get("id") or n.get("node_id")
            dst = n.get("next_node")
            if src and dst:
                edges.append({"from": src, "to": dst})
    snapshot["edges"] = edges

    snapshot.setdefault("outputs", {})
    snapshot.setdefault("failure_policy", {})
    snapshot.setdefault("errors", [])

    # UTC Timestamp
    snapshot["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Write out to YAML file in temp dir
    file_path = get_session_file_path(conversation_id, session_id)
    with file_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(snapshot, f, sort_keys=False, allow_unicode=True)

    return file_path


def init_workflow_session(workflow_data: dict[str, Any]) -> dict[str, Any]:
    """
    Initializes a new workflow session file in temp dir from dynamic workflow data.
    """
    if not workflow_data or not isinstance(workflow_data, dict):
        raise ValueError("got no workflow")

    merged = copy.deepcopy(workflow_data)

    session_id = merged.get("workflow_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        merged["workflow_session_id"] = session_id

    conversation_id = merged.get("conversation_id") or f"workflow-conv-{session_id}"
    merged["conversation_id"] = conversation_id

    file_path = capture_workflow_snapshot(merged, status="not_started")
    with file_path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded if isinstance(loaded, dict) else merged



def load_workflow_session_yaml(
    conversation_id: str | None = None,
    workflow_session_id: str | None = None,
) -> dict[str, Any]:
    """
    Finds and loads the saved session YAML file from temp dir by conversation_id or workflow_session_id.
    """
    if not conversation_id and not workflow_session_id:
        raise ValueError("Must provide conversation_id or workflow_session_id.")

    session_dir = get_session_dir()
    if not session_dir.exists():
        raise FileNotFoundError("Session directory does not exist.")

    matching_files: list[Path] = []

    # 1. Match by filename pattern: {conversation_id}_{session_id}.yaml
    for f in list(session_dir.glob("*.yaml")) + list(session_dir.glob("*.yml")):
        fname = f.name
        if conversation_id and fname.startswith(f"{conversation_id}_"):
            matching_files.append(f)
        elif workflow_session_id and workflow_session_id in fname:
            matching_files.append(f)

    # 2. Match by file content inspection if filename didn't match
    if not matching_files:
        for f in list(session_dir.glob("*.yaml")) + list(session_dir.glob("*.yml")):
            try:
                with f.open("r", encoding="utf-8") as yf:
                    data = yaml.safe_load(yf)
                if isinstance(data, dict):
                    if conversation_id and data.get("conversation_id") == conversation_id:
                        matching_files.append(f)
                    elif workflow_session_id and data.get("workflow_session_id") == workflow_session_id:
                        matching_files.append(f)
            except Exception:
                continue

    # 3. Fallback to existing json files if present
    if not matching_files:
        for f in session_dir.glob("*.json"):
            if workflow_session_id and workflow_session_id in f.name:
                matching_files.append(f)

    if not matching_files:
        raise FileNotFoundError(
            f"No session found for conversation_id='{conversation_id}' or workflow_session_id='{workflow_session_id}'."
        )

    matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    target_file = matching_files[0]

    with target_file.open("r", encoding="utf-8") as f:
        if target_file.suffix.lower() in {".yaml", ".yml"}:
            loaded = yaml.safe_load(f)
        else:
            loaded = json.load(f)

    if not isinstance(loaded, dict):
        raise ValueError(f"Session data in {target_file} is not a valid dictionary.")
    return loaded


def record_feedback_to_session(
    session_state: dict[str, Any],
    feedback: str,
    action: str,
    target_node: str,
    reasoning: str = "",
) -> None:
    """Helper function to record a human feedback iteration in session review history."""
    rework_count = session_state.get("rework_count", 0)
    if action in {"restart", "rework_current"}:
        rework_count += 1
        session_state["rework_count"] = rework_count

    session_state["rework_feedback"] = feedback
    session_state["status"] = "running"
    session_state.setdefault("review_history", []).append({
        "iteration": rework_count,
        "action": action,
        "target_node": target_node,
        "feedback": feedback,
        "reasoning": reasoning,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })


def save_session_file(workflow: dict[str, Any]) -> Path:
    """Convenience alias for capture_workflow_snapshot."""
    return capture_workflow_snapshot(workflow)


def load_workflow_session(identifier: str) -> dict[str, Any]:
    """Finds and loads a workflow session by session_id, conversation_id, or filename substring."""
    if not identifier:
        raise ValueError("identifier must be a non-empty string.")

    try:
        return load_workflow_session_yaml(conversation_id=identifier)
    except FileNotFoundError:
        pass

    try:
        return load_workflow_session_yaml(workflow_session_id=identifier)
    except FileNotFoundError:
        pass

    session_dir = get_session_dir()
    if not session_dir.exists():
        raise FileNotFoundError(f"No workflow found for identifier {identifier}.")

    matching_workflows: list[dict[str, Any]] = []
    for file_path in list(session_dir.glob("*.yaml")) + list(session_dir.glob("*.yml")) + list(session_dir.glob("*.json")):
        try:
            with file_path.open("r", encoding="utf-8") as file:
                if file_path.suffix.lower() in {".yaml", ".yml"}:
                    workflow = yaml.safe_load(file)
                else:
                    workflow = json.load(file)
            if isinstance(workflow, dict):
                if (
                    workflow.get("workflow_session_id") == identifier
                    or workflow.get("conversation_id") == identifier
                    or identifier in file_path.name
                ):
                    workflow["_file_mtime"] = file_path.stat().st_mtime
                    matching_workflows.append(workflow)
        except Exception:
            continue

    if not matching_workflows:
        raise FileNotFoundError(f"No workflow found for identifier {identifier}.")

    if len(matching_workflows) > 1:
        matching_workflows.sort(
            key=lambda w: (w.get("updated_at", ""), w.get("_file_mtime", 0)),
            reverse=True,
        )

    res = matching_workflows[0]
    res.pop("_file_mtime", None)
    return res

