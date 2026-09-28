import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Literal, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..services.workflow_service import WorkflowOrchestratorService

router = APIRouter(prefix="/api/workflow", tags=["Agent Workflow"])

orchestrator = WorkflowOrchestratorService()


class HITLReviewRequest(BaseModel):
    session_id: str
    decision: Literal["approve", "request_changes"]
    reviewer_name: str = "Lead Product Owner"
    comments: Optional[str] = None
    target_publish_platform: Literal["jira", "confluence", "both"] = "both"


class PublishPRDRequest(BaseModel):
    session_id: str
    target_platform: Literal["jira", "confluence", "both"] = "both"
    space_key: str = "CHECKOUT"
    jira_project_key: str = "CHK"


@router.post("/upload-and-run")
async def upload_and_run_workflow(
    file: UploadFile = File(...),
    active_team_id: str = Form("team-checkout-product"),
    query_override: Optional[str] = Form(None),
    auto_approve_hitl: bool = Form(True),
    reviewer_comments: Optional[str] = Form(None),
    target_publish_platform: Literal["jira", "confluence", "both"] = Form("both")
):
    """
    End-to-End Workflow endpoint:
    1. Uploads document (.docx, .pdf, .txt, .md)
    2. Runs Doc Extractor
    3. Runs Context Analyzer (MCP Skill Discovery + MCP Context Retrieval)
    4. Runs Gap Analyzer & checks evidence sufficiency
    5. Runs PRD Generator
    6. Runs PRD Reviewer
    7. Runs HITL Review (or auto-approves)
    8. Publishes final PRD to Jira/Confluence
    """
    suffix = Path(file.filename or "doc.txt").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        result = orchestrator.run_workflow_from_file(
            file_path=tmp_path,
            active_team_id=active_team_id,
            query_override=query_override,
            auto_approve_hitl=auto_approve_hitl,
            reviewer_comments=reviewer_comments,
            target_publish_platform=target_publish_platform
        )
        return result
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


@router.post("/hitl/review")
async def submit_hitl_review(payload: HITLReviewRequest):
    """
    Submits Human-In-The-Loop review for a paused workflow session.
    """
    session = orchestrator.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {payload.session_id} not found.")

    if payload.decision == "approve":
        prd_content = session.get("draft_prd") or session.get("final_prd")
        context_data = session.get("context_analysis", {})

        hitl_record = orchestrator.hitl_service.process_review(
            prd_content=prd_content,
            decision="approve",
            reviewer_name=payload.reviewer_name,
            comments=payload.comments or "Approved by Product Owner."
        )

        publish_receipt = orchestrator.publish_service.publish_prd(
            prd_markdown=prd_content,
            context_data=context_data,
            target_platform=payload.target_publish_platform
        )

        session["status"] = "completed"
        session["hitl_review"] = hitl_record
        session["publish_receipt"] = publish_receipt

        return {
            "session_id": payload.session_id,
            "status": "completed",
            "hitl_review": hitl_record,
            "publish_receipt": publish_receipt
        }
    else:
        context_data = session.get("context_analysis", {})
        revised_prd = orchestrator.prd_service.generate(
            context=context_data,
            reviewer_feedback=payload.comments
        )
        review_result = orchestrator.reviewer_service.review(revised_prd, context_data)
        session["draft_prd"] = revised_prd
        session["review_result"] = review_result

        return {
            "session_id": payload.session_id,
            "status": "changes_applied_awaiting_reapproval",
            "revised_prd": revised_prd,
            "review_result": review_result
        }


@router.get("/sessions/{session_id}")
async def get_session_status(session_id: str):
    """
    Retrieves full execution trajectory and artifacts for a session.
    """
    session = orchestrator.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return session

