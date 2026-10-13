import copy
import json
import logging
from typing import Any, Literal
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import yaml

from ..graph.state import WorkflowNode, WorkflowState
from ..graph.workflow_orchestrator import (
    CHECKPOINTER,
    build_workflow_orchestration,
    get_checkpoint_nodes,
    interpret_human_feedback,
    normalize_workflow_state,
    sse,
    stream_workflow,
)
from ..session_manager import (
    init_workflow_session,
    load_workflow_session,
    load_workflow_session_yaml,
    record_feedback_to_session,
    save_session_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Dynamic Workflow Orchestrator"])


class WorkflowPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    conversation_id: str = "default_conversation"
    workflow_session_id: str | None = None
    workflow_id: str = "default_workflow"
    version: str = "1.0.0"
    status: str = "not_started"
    current_node: str = ""
    next_node: str = ""
    agent: dict[str, Any] = Field(default_factory=dict)
    actors: dict[str, Any] = Field(default_factory=dict)
    channels: dict[str, Any] = Field(default_factory=dict)
    run_modes: dict[str, Any] = Field(default_factory=dict)
    inputs: Any = Field(default_factory=list)
    intake: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    skills: dict[str, Any] = Field(default_factory=dict)
    model_policy_ref: str = "azure_standard_test_generation"
    graph: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    failure_policy: dict[str, Any] = Field(default_factory=dict)


class HumanFeedbackRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    feedback: str = Field(min_length=1)
    workflow_session_id: str | None = None


class HumanDecisionRequest(BaseModel):
    workflow_session_id: str = Field(min_length=1)
    decision: Literal["approve", "reject", "rework"]
    feedback: str = ""
    reviewed_by: str | None = None


@router.post("/workflow/run")
async def run_workflow(request: Request):
    body_bytes = await request.body()

    if not body_bytes or body_bytes.strip() in (b"", b"{}", b"null"):
        raise HTTPException(status_code=400, detail="got no workflow")

    try:
        workflow_data = yaml.safe_load(body_bytes)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc

    if not isinstance(workflow_data, dict) or not workflow_data:
        raise HTTPException(status_code=400, detail="got no workflow")

    raw_nodes = workflow_data.get("graph", {}).get("nodes", []) or workflow_data.get("nodes", [])
    if not raw_nodes:
        raise HTTPException(status_code=400, detail="got no workflow")

    for idx, node in enumerate(raw_nodes):
        if not isinstance(node, dict) or not (node.get("id") or node.get("node_id")):
            raise HTTPException(
                status_code=400,
                detail=f"Node at index {idx} is missing required 'node_id' or 'id'.",
            )

    try:
        workflow_payload = WorkflowPayload.model_validate(workflow_data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    workflow = init_workflow_session(workflow_payload.model_dump())

    raw_nodes = workflow.get("graph", {}).get("nodes", []) or workflow.get("nodes", [])
    if not raw_nodes:
        raise HTTPException(status_code=400, detail="got no workflow")

    checkpoint_nodes = get_checkpoint_nodes(raw_nodes)
    graph = build_workflow_orchestration(workflow)
    compiled_graph = graph.compile(
        checkpointer=CHECKPOINTER,
        interrupt_after=checkpoint_nodes,
    )

    conv_id = workflow.get("conversation_id")
    sess_id = workflow.get("workflow_session_id")
    config = {
        "configurable": {
            "thread_id": f"{conv_id}:{sess_id}"
        }
    }

    initial_state = normalize_workflow_state(workflow)

    return StreamingResponse(
        stream_workflow(compiled_graph, initial_state, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/workflow/feedback")
@router.post("/workflow/feedback/run")
async def submit_workflow_feedback(request: HumanFeedbackRequest):
    """Processes human feedback, interprets intent with LLM, and resumes workflow execution."""
    try:
        session_state = load_workflow_session_yaml(
            conversation_id=request.conversation_id,
            workflow_session_id=request.workflow_session_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw_nodes = (
        session_state.get("graph", {}).get("nodes", [])
        or session_state.get("nodes", [])
    )
    if not raw_nodes:
        raise HTTPException(status_code=400, detail="No nodes defined in workflow state.")

    node_ids = [n.get("id") or n.get("node_id") for n in raw_nodes if (n.get("id") or n.get("node_id"))]
    current_node = session_state.get("current_node", "")
    default_next_node = session_state.get("next_node")

    if not default_next_node and current_node in node_ids:
        curr_idx = node_ids.index(current_node)
        if curr_idx + 1 < len(node_ids):
            default_next_node = node_ids[curr_idx + 1]

    # Interpret human feedback using Azure OpenAI
    decision = interpret_human_feedback(
        feedback=request.feedback,
        current_node=current_node,
        raw_nodes=raw_nodes,
        next_node=default_next_node,
    )
    action = decision.get("action", "proceed")
    target_node = decision.get("target_node") or default_next_node or node_ids[0]
    reasoning = decision.get("reasoning", "")

    if target_node not in node_ids:
        target_node = default_next_node or node_ids[0]

    record_feedback_to_session(
        session_state=session_state,
        feedback=request.feedback,
        action=action,
        target_node=target_node,
        reasoning=reasoning,
    )

    if action == "restart":
        target_node = node_ids[0]
        for node in session_state.get("nodes", []):
            node["status"] = "pending"
            node["output"] = None

    save_session_file(session_state)

    # Compile graph with entry point set dynamically to target_node
    graph = build_workflow_orchestration(session_state, entry_node=target_node)
    checkpoint_nodes = get_checkpoint_nodes(raw_nodes)
    compiled_graph = graph.compile(
        checkpointer=CHECKPOINTER,
        interrupt_after=checkpoint_nodes,
    )

    conv_id = session_state.get("conversation_id", request.conversation_id)
    sess_id = session_state.get("workflow_session_id")
    config = {
        "configurable": {
            "thread_id": f"{conv_id}:{sess_id}:{uuid.uuid4()}"
        }
    }

    initial_workflow_state = normalize_workflow_state(session_state)

    async def stream_with_acknowledgement():
        yield sse(
            "feedback_acknowledged",
            {
                "conversation_id": conv_id,
                "workflow_session_id": sess_id,
                "action": action,
                "target_node": target_node,
                "reasoning": reasoning,
                "feedback": request.feedback,
            },
        )
        for event in stream_workflow(compiled_graph, initial_workflow_state, config):
            yield event

    return StreamingResponse(
        stream_with_acknowledgement(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/workflow/human-decision")
def submit_human_decision(request: HumanDecisionRequest):
    """Backwards compatibility endpoint for explicit HITL approval nodes."""
    try:
        workflow = load_workflow_session(request.workflow_session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw_nodes = workflow.get("graph", {}).get("nodes", []) or workflow.get("nodes", [])
    checkpoint_nodes = get_checkpoint_nodes(raw_nodes)

    graph = build_workflow_orchestration(workflow)
    compiled_graph = graph.compile(checkpointer=CHECKPOINTER, interrupt_after=checkpoint_nodes)
    config = {
        "configurable": {
            "thread_id": f"{workflow.get('conversation_id', 'QE-201')}:{request.workflow_session_id}"
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


@router.get("/workflow/session/{identifier}")
def get_workflow_session(identifier: str):
    try:
        workflow = load_workflow_session(identifier)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(content=workflow)


@router.get("/health")
async def health():
    return {
        "status": "UP",
        "orchestrator": "ok",
        "framework": "LangGraph + FastAPI SSE",
    }
