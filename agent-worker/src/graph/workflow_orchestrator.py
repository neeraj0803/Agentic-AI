import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from ..config import get_session_dir
from ..nodes.agent_node import create_agent_node
from ..nodes.hitl_node import create_hitl_node
from .state import WorkflowState

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SESSION_DIR = get_session_dir()
CHECKPOINTER = MemorySaver()


def session_file_path(workflow_session_id: str, workflow_type: str) -> Path:
    session_dir = get_session_dir()
    session_dir.mkdir(exist_ok=True, parents=True)
    return session_dir / f"{workflow_session_id}-{workflow_type}.json"



def save_session_file(workflow: dict[str, Any]) -> None:
    session_id = workflow.get("workflow_session_id", "session")
    workflow_type = workflow.get("type", "Agent")
    file_path = session_file_path(session_id, workflow_type)

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(workflow, file, indent=2, ensure_ascii=False)
        file.write("\n")


def load_or_create_session_file(workflow: dict[str, Any]) -> dict[str, Any]:
    session_id = workflow.get("workflow_session_id")
    workflow_type = workflow.get("type", "Agent")
    file_path = session_file_path(session_id, workflow_type)

    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as file:
            existing_workflow = json.load(file)
        if isinstance(existing_workflow, dict):
            return existing_workflow

    workflow_copy = deepcopy(workflow)
    workflow_copy.setdefault("status", "not_started")
    workflow_copy.setdefault("current_node", "")

    for node in workflow_copy.get("nodes", []):
        node.setdefault("output", None)

    save_session_file(workflow_copy)
    return workflow_copy


def passthrough_node(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    node_id = node.get("node_id", "unknown-node")
    state["status"] = "running"
    state["current_node"] = node_id

    for item in state.get("nodes", []):
        if item.get("node_id") == node_id:
            item["output"] = {
                "node_name": node.get("node_name"),
                "node_type": node.get("node_type"),
                "status": "completed",
            }
            break

    save_session_file(state)
    return state


def build_workflow_orchestration(workflow: dict[str, Any]) -> StateGraph:
    graph = StateGraph(WorkflowState)

    for node in workflow.get("nodes", []):
        node_id = node.get("node_id")
        if not node_id:
            continue

        node_type = (node.get("node_type") or "").lower()

        if node_type == "agent":
            graph.add_node(node_id, create_agent_node(node))
        elif node_type in {"hitl", "human", "approval"}:
            graph.add_node(node_id, create_hitl_node(node))
        else:
            graph.add_node(
                node_id,
                lambda state, current_node=node: passthrough_node(state, current_node),
            )

    for node in workflow.get("nodes", []):
        node_id = node.get("node_id")
        if not node_id:
            continue

        next_node = node.get("next_node")
        destination = next_node if next_node and next_node != "end" else END
        node_type = (node.get("node_type") or "").lower()
        if node_type in {"hitl", "human", "approval"}:
            graph.add_conditional_edges(
                node_id,
                lambda state, current_node_id=node_id: (
                    "approved"
                    if any(
                        item.get("node_id") == current_node_id
                        and isinstance(item.get("output"), dict)
                        and item["output"].get("approved") is True
                        for item in state.get("nodes", [])
                    )
                    else "rejected"
                ),
                {"approved": destination, "rejected": END},
            )
        elif destination != END:
            graph.add_edge(node_id, destination)
        else:
            graph.add_edge(node_id, END)

    first_node = workflow.get("nodes", [{}])[0].get("node_id")
    if first_node:
        graph.set_entry_point(first_node)

    return graph


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def stream_workflow(
    compiled_graph: Any,
    initial_state: WorkflowState | Command,
    config: dict[str, Any],
):
    final_state: dict[str, Any] = {}
    active_node = ""

    try:
        for mode, chunk in compiled_graph.stream(
            initial_state,
            config=config,
            stream_mode=["debug", "values"],
        ):
            if mode == "values":
                final_state = chunk
                continue

            event_type = chunk.get("type")
            payload = chunk.get("payload", {})
            node_id = payload.get("name", "unknown-node")

            if event_type == "task":
                active_node = node_id
                yield sse("node_start", {"node_id": node_id})
            elif event_type == "task_result":
                if payload.get("interrupts"):
                    continue

                error = payload.get("error")
                if error:
                    yield sse("node_error", {"node_id": node_id, "error": str(error)})
                    return

                result = payload.get("result", {})
                node_outputs = result.get("nodes", []) if isinstance(result, dict) else []
                node_output = next(
                    (
                        node.get("output")
                        for node in node_outputs
                        if isinstance(node, dict) and node.get("node_id") == node_id
                    ),
                    None,
                )
                yield sse("node_complete", {"node_id": node_id, "output": node_output})
                active_node = ""

        snapshot = compiled_graph.get_state(config)
        interrupts = [
            pending_interrupt.value
            for task in snapshot.tasks
            for pending_interrupt in task.interrupts
        ]
        if interrupts:
            final_state = dict(snapshot.values)
            interrupt_data = interrupts[0]
            final_state["status"] = "waiting_for_human"
            final_state["current_node"] = interrupt_data.get("node_id", active_node)
            save_session_file(final_state)
            yield sse("human_input_required", interrupt_data)
            return

        if final_state.get("status") == "rejected":
            final_state["current_node"] = ""
            save_session_file(final_state)
            yield sse("workflow_rejected", {"status": "rejected"})
            return

        final_state["status"] = "completed"
        final_state["current_node"] = ""
        save_session_file(final_state)
        yield sse("workflow_complete", {"status": "completed"})
    except Exception as exc:
        yield sse("node_error", {"node_id": active_node or "unknown-node", "error": str(exc)})
