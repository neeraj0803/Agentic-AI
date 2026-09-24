import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from nodes.agent_node import create_agent_node
from state import WorkflowState

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "temp dir"

app = FastAPI(title="Dynamic Workflow Orchestrator", version="1.0.0")


class WorkflowPayload(BaseModel):
    workflow_session_id: str
    type: str = "Agent"
    status: str = "not_started"
    current_node: str = ""
    input_documents: list[dict[str, Any]] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)


def session_file_path(workflow_session_id: str, workflow_type: str) -> Path:
    SESSION_DIR.mkdir(exist_ok=True, parents=True)
    return SESSION_DIR / f"{workflow_session_id}-{workflow_type}.json"


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
                "status": "completed"
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
        if next_node and next_node != "end":
            graph.add_edge(node_id, next_node)
        else:
            graph.add_edge(node_id, END)

    first_node = workflow.get("nodes", [{}])[0].get("node_id")
    if first_node:
        graph.set_entry_point(first_node)

    return graph


@app.post("/workflow/run")
async def run_workflow(payload: WorkflowPayload):
    workflow = load_or_create_session_file(payload.model_dump())

    if not workflow.get("nodes"):
        raise HTTPException(status_code=400, detail="Workflow must contain at least one node.")

    graph = build_workflow_orchestration(workflow)
    compiled_graph = graph.compile()

    initial_state: WorkflowState = {
        "workflow_session_id": workflow.get("workflow_session_id"),
        "type": workflow.get("type", "Agent"),
        "status": workflow.get("status", "not_started"),
        "current_node": workflow.get("current_node", ""),
        "input_documents": workflow.get("input_documents", []),
        "nodes": workflow.get("nodes", []),
        "errors": [],
    }

    final_state = compiled_graph.invoke(initial_state)

    final_state["status"] = "completed"
    final_state["current_node"] = ""
    save_session_file(final_state)

    return {"message": "workflow has been completed"}


@app.get("/health")
async def health():
    return {"status": "ok"}