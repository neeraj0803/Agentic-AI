from fastapi import APIRouter, Depends, HTTPException

from ..schemas.jira_schema import (
    JiraIssueRequest,
    JiraIssueResponse,
    JiraWritebackRequest,
    JiraWritebackResponse,
)
from ..services.jira_service import JiraService, JiraServiceError


router = APIRouter()
jira_service = JiraService()


@router.get(
    "/fetch_jira_issue_by_key",
    response_model=JiraIssueResponse,
)
async def fetch_jira_issue_by_key(
    payload: JiraIssueRequest = Depends(),
) -> JiraIssueResponse:
    try:
        return await jira_service.fetch_issue_by_key(payload.issue_key)
    except JiraServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc


@router.post(
    "/write_back",
    response_model=JiraWritebackResponse,
)
async def write_back_to_jira(
    payload: JiraWritebackRequest,
) -> JiraWritebackResponse:
    try:
        return await jira_service.writeback_issue_tree(payload)
    except JiraServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc
