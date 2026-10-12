from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from ..models.run_models import (
    CancelRunRequest,
    CreateRunRequest,
    RunStatusResponse,
    WorkflowRunStatus
)
from ..services.run_lifecycle_service import run_lifecycle_service

router = APIRouter(prefix="/runs", tags=["Run Lifecycle Management"])


@router.post("", response_model=RunStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_and_dispatch_run(req: CreateRunRequest):
    """
    Creates a new workflow run, performs preflight validation,
    compiles immutable snapshot, locks version and policy,
    queues the task, and dispatches to the Agent Worker.
    """
    try:
        run = await run_lifecycle_service.create_and_dispatch_run(req)
        return run
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("", response_model=List[RunStatusResponse])
async def list_runs(
    team_id: Optional[str] = Query(None, description="Filter runs by team ID"),
    status: Optional[str] = Query(None, description="Filter runs by status (QUEUED, RUNNING, etc.)"),
    limit: int = Query(50, ge=1, le=100)
):
    """Lists workflow runs tracked by the Platform Orchestrator."""
    return run_lifecycle_service.list_runs(team_id=team_id, status=status, limit=limit)


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str):
    """Retrieves current run state, status, active checkpoint pointer, and outputs."""
    run = run_lifecycle_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Workflow run '{run_id}' not found.")
    return run


@router.post("/{run_id}/cancel", response_model=RunStatusResponse)
async def cancel_run(run_id: str, req: Optional[CancelRunRequest] = None):
    """Requests graceful cancellation of an active or paused workflow run."""
    reason = req.reason if req else "User requested cancellation"
    try:
        updated = await run_lifecycle_service.cancel_run(run_id, reason=reason)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
