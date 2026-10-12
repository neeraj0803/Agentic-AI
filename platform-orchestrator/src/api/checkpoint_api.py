from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from ..models.checkpoint_models import CheckpointDetailResponse, CheckpointMetadata
from ..models.run_models import (
    ApprovalRequest,
    ClarificationRequest,
    ResumeRequest,
    RunStatusResponse
)
from ..services.checkpoint_service import checkpoint_service
from ..services.run_lifecycle_service import run_lifecycle_service

router = APIRouter(prefix="/runs", tags=["Human-in-the-Loop & Checkpoints"])


# Guard routes for when $runId is accidentally empty in PowerShell URLs (e.g. /runs//approve)
@router.post("/approve")
@router.post("//approve")
async def missing_run_id_for_approval():
    raise HTTPException(
        status_code=400,
        detail="Missing run_id in URL path. Please provide a valid run ID (e.g. /runs/RUN-XXXX/approve). Ensure your PowerShell $runId variable is set."
    )


@router.post("/clarify")
@router.post("//clarify")
async def missing_run_id_for_clarify():
    raise HTTPException(
        status_code=400,
        detail="Missing run_id in URL path. Please provide a valid run ID (e.g. /runs/RUN-XXXX/clarify). Ensure your PowerShell $runId2 variable is set."
    )


@router.get("/{run_id}/checkpoints", response_model=List[CheckpointMetadata])
async def list_run_checkpoints(run_id: str):
    """Lists all saved checkpoints for a specific workflow run."""
    run = run_lifecycle_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return checkpoint_service.list_checkpoints(run_id)


@router.get("/{run_id}/checkpoints/{checkpoint_id}", response_model=CheckpointDetailResponse)
async def get_checkpoint_detail(run_id: str, checkpoint_id: str):
    """Retrieves full serialized state snapshot for a specific checkpoint."""
    cp = checkpoint_service.get_checkpoint(run_id, checkpoint_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"Checkpoint '{checkpoint_id}' not found for run '{run_id}'.")
    return cp


@router.post("/{run_id}/clarify", response_model=RunStatusResponse)
async def submit_clarification(run_id: str, req: ClarificationRequest):
    """
    Submits missing requirements/acceptance criteria for a run in WAITING_FOR_CLARIFICATION
    and resumes execution from CP-01.
    """
    if not run_id or not run_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Run ID is empty. Ensure your PowerShell variable $runId2 is set."
        )
    try:
        updated = await run_lifecycle_service.handle_clarification(run_id, req)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clarification resumption failed: {str(e)}")


@router.post("/{run_id}/approve", response_model=RunStatusResponse)
async def submit_human_approval(run_id: str, req: ApprovalRequest):
    """
    Submits human reviewer decision (approve, request_changes, or reject) for a run in awaiting_approval (CP-05)
    and resumes execution or marks final status.
    """
    if not run_id or not run_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Run ID is empty. Ensure your PowerShell variable $runId is set."
        )
    try:
        updated = await run_lifecycle_service.handle_approval(run_id, req)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval resumption failed: {str(e)}")


@router.post("/{run_id}/rework", response_model=RunStatusResponse)
async def submit_rework_directives(run_id: str, feedback_text: str, reviewer_name: str = "Lead Reviewer"):
    """
    Submits structured rework directives for a run paused at CP-05,
    incrementing rework cycle count and resuming execution towards designated revision node.
    """
    approval_req = ApprovalRequest(
        decision="request_changes",
        reviewer_name=reviewer_name,
        comments=feedback_text
    )
    try:
        updated = await run_lifecycle_service.handle_approval(run_id, approval_req)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rework resumption failed: {str(e)}")


@router.post("/{run_id}/resume", response_model=RunStatusResponse)
async def resume_run_from_checkpoint(run_id: str, req: ResumeRequest):
    """
    Generic resumption: Resumes workflow run from any valid checkpoint ID.
    """
    try:
        updated = await run_lifecycle_service.resume_from_checkpoint(
            run_id=run_id,
            checkpoint_id=req.checkpoint_id,
            payload=req.resume_payload
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resumption failed: {str(e)}")

