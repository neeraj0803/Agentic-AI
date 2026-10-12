import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ..models.run_models import (
    CreateRunRequest,
    CreateSessionRequest,
    PreflightCheckResult,
    PreflightRequest,
    PreflightResponse,
    RunStatusResponse,
    SessionMessageRequest,
    SessionMessageResponse,
    SessionResponse
)
from ..services.intent_resolver import intent_resolver
from ..services.preflight_service import preflight_service
from ..services.run_lifecycle_service import run_lifecycle_service
from ..services.workflow_registry import workflow_registry
from ..storage.orchestrator_storage import OrchestratorStorage
from ..streaming.sse_broadcaster import sse_broadcaster

router = APIRouter(prefix="/sessions", tags=["Conversational Intake & Sessions"])
storage = OrchestratorStorage()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(req: CreateSessionRequest):
    """
    Creates a new conversational intake session for requirements gathering,
    intent routing, and preflight preparation.
    """
    session = storage.create_session(
        team_id=req.team_id,
        user_id=req.user_id,
        requested_agent_id=req.requested_agent_id,
        intake_channel=req.intake_channel,
        session_metadata=req.session_metadata
    )
    return session


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    team_id: Optional[str] = Query(None, description="Filter sessions by team ID"),
    user_id: Optional[str] = Query(None, description="Filter sessions by user ID"),
    limit: int = Query(50, ge=1, le=100)
):
    """Lists conversational intake sessions."""
    return storage.list_sessions(team_id=team_id, user_id=user_id, limit=limit)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Retrieves session details, current intake state, and metadata."""
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


@router.post("/{session_id}/messages", response_model=SessionMessageResponse)
async def post_session_message(session_id: str, req: SessionMessageRequest):
    """
    Ingests user chat message or requirement document, resolves intent,
    accumulates input parameters, identifies missing fields, and checks preflight readiness.
    """
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    # 1. Resolve agent intent if not locked
    agent_id = session.get("requested_agent_id")
    intent_res = intent_resolver.resolve_intent(req.message)
    if not agent_id and intent_res["top_agent_id"]:
        agent_id = intent_res["top_agent_id"]
        storage.update_session_state(
            session_id=session_id,
            session_state="intent_resolved",
            requested_agent_id=agent_id
        )

    # 2. Accumulate inputs
    current_inputs = req.current_inputs or {}
    if intent_res.get("extracted_parameters"):
        current_inputs.update(intent_res["extracted_parameters"])

    # 3. Check workflow inputs
    missing_fields = []
    is_preflight_ready = False
    preflight_summary = None

    if agent_id:
        missing_fields = workflow_registry.validate_input_payload(agent_id, current_inputs)
        
        # Run preflight check
        preflight_res = preflight_service.validate_preflight(
            PreflightRequest(
                agent_id=agent_id,
                team_id=session["team_id"],
                user_id=req.user_id,
                inputs=current_inputs,
                session_id=session_id
            )
        )
        is_preflight_ready = preflight_res.valid
        preflight_summary = preflight_res.model_dump()

        if is_preflight_ready:
            storage.update_session_state(
                session_id=session_id,
                session_state="preflight_ready",
                metadata_update={"accumulated_inputs": current_inputs}
            )

    msg_id = f"MSG-{uuid.uuid4().hex[:8].upper()}"
    reply = f"Understood. Matched workflow '{agent_id or 'General Assistant'}'. Confidence: {intent_res['confidence_score']:.2f}."
    if missing_fields:
        reply += f" Missing required fields to proceed: {', '.join(missing_fields)}."
    elif is_preflight_ready:
        reply += " All preflight checks passed! You may now dispatch execution."

    return SessionMessageResponse(
        session_id=session_id,
        message_id=msg_id,
        assistant_reply=reply,
        resolved_agent_id=agent_id,
        confidence_score=intent_res["confidence_score"],
        accumulated_inputs=current_inputs,
        missing_fields=missing_fields,
        is_preflight_ready=is_preflight_ready,
        preflight_check=preflight_summary
    )


@router.post("/{session_id}/preflight", response_model=PreflightResponse)
async def run_session_preflight(session_id: str, inputs: Dict[str, Any]):
    """
    Executes 18-point enterprise preflight check against accumulated session inputs.
    """
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    agent_id = session.get("requested_agent_id") or "AG-201"
    req = PreflightRequest(
        agent_id=agent_id,
        team_id=session["team_id"],
        user_id=session["user_id"],
        inputs=inputs,
        session_id=session_id
    )
    return preflight_service.validate_preflight(req)


@router.post("/{session_id}/dispatch", response_model=RunStatusResponse, status_code=status.HTTP_201_CREATED)
async def dispatch_run_from_session(session_id: str, req: CreateRunRequest):
    """
    Creates and dispatches a workflow execution run linked to the active intake session.
    """
    req.session_id = session_id
    try:
        run = await run_lifecycle_service.create_and_dispatch_run(req)
        return run
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}/events")
async def stream_session_events(
    session_id: str,
    last_event_id: Optional[int] = Query(None, description="Last event ID for replay")
):
    """Streams live Server-Sent Events (SSE) for a specific session."""
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    return StreamingResponse(
        sse_broadcaster.stream_for_session(session_id=session_id, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

