from fastapi import APIRouter, HTTPException

from ..schemas.confluence_context_schema import ConfluencePageRequest, ConfluencePageResponse
from ..services.confluence_context_service import ConfluenceContextService

router = APIRouter()

_confluence_service = ConfluenceContextService()


@router.get("/page/{page_id}", response_model=ConfluencePageResponse)
def get_confluence_page(page_id: str, space_key: str | None = None):
    try:
        page = _confluence_service.fetch_page(page_id=page_id, space_key=space_key)
        return ConfluencePageResponse(**page)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/page", response_model=ConfluencePageResponse)
def get_confluence_page_from_payload(payload: ConfluencePageRequest):
    try:
        page = _confluence_service.fetch_page(page_id=payload.page_id, space_key=payload.space_key)
        return ConfluencePageResponse(**page)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/requirement/{page_id}", response_model=dict)
def get_requirement_payload(page_id: str, space_key: str | None = None):
    try:
        return _confluence_service.to_requirement_context(page_id=page_id, space_key=space_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
