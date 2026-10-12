from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import yaml

from ..graph.state import WorkflowState
from ..graph.workflow_orchestrator import (
    CHECKPOINTER,
    build_workflow_orchestration,
    load_or_create_session_file,
    stream_workflow,
)
from ..nodes.conversation_node import conversation_node, load_workflow_session

router = APIRouter(tags=["Dynamic Workflow Orchestrator"])


class WorkflowPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    workflow_session_id: str
    type: str = "Agent"
    status: str = "not_started"
    current_node: str = ""
    input_documents: list[dict[str, Any]] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)


class ConversationRequest(BaseModel):
    workflow_session_id: str = Field(min_length=1)
    user_query: str = Field(min_length=1)


class HumanDecisionRequest(BaseModel):
    workflow_session_id: str = Field(min_length=1)
    decision: Literal["approve", "reject"]
    feedback: str = ""
    reviewed_by: str | None = None


@router.post("/workflow/run")
async def run_workflow(request: Request):
    try:
        workflow_data = yaml.safe_load(await request.body())
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc

    if not isinstance(workflow_data, dict):
        raise HTTPException(status_code=400, detail="The YAML body must contain a workflow object.")

    try:
        workflow_payload = WorkflowPayload.model_validate(workflow_data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    workflow = load_or_create_session_file(workflow_payload.model_dump())

    if not workflow.get("nodes"):
        raise HTTPException(status_code=400, detail="Workflow must contain at least one node.")

    graph = build_workflow_orchestration(workflow)
    compiled_graph = graph.compile(checkpointer=CHECKPOINTER)
    config = {
        "configurable": {
            "thread_id": f"{workflow.get('workflow_session_id')}:{workflow.get('type', 'Agent')}"
        }
    }

    initial_state: WorkflowState = {
        "workflow_session_id": workflow.get("workflow_session_id"),
        "type": workflow.get("type", "Agent"),
        "status": workflow.get("status", "not_started"),
        "current_node": workflow.get("current_node", ""),
        "input_documents": workflow.get("input_documents", []),
        "nodes": workflow.get("nodes", []),
        "errors": [],
    }

    return StreamingResponse(
        stream_workflow(compiled_graph, initial_state, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/workflow/human-decision")
def submit_human_decision(request: HumanDecisionRequest):
    try:
        workflow = load_workflow_session(request.workflow_session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    graph = build_workflow_orchestration(workflow)
    compiled_graph = graph.compile(checkpointer=CHECKPOINTER)
    config = {
        "configurable": {
            "thread_id": f"{request.workflow_session_id}:{workflow.get('type', 'Agent')}"
        }
    }
    snapshot = compiled_graph.get_state(config)
    if not snapshot.tasks or not any(task.interrupts for task in snapshot.tasks):
        raise HTTPException(
            status_code=409,
            detail="This workflow is not waiting for a human decision in this process.",
        )

    decision = request.model_dump(exclude={"workflow_session_id"})
    return StreamingResponse(
        stream_workflow(
            compiled_graph,
            Command(resume=decision),
            config,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/workflow/conversation")
def workflow_conversation(request: ConversationRequest):
    try:
        answer = conversation_node(request.workflow_session_id, request.user_query)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "workflow_session_id": request.workflow_session_id,
        "answer": answer,
    }

