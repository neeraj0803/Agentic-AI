from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status

from ..models.run_models import PreflightRequest, PreflightResponse
from ..services.preflight_service import preflight_service

router = APIRouter(prefix="/preflight", tags=["Preflight Validation Gate"])


@router.post("", response_model=PreflightResponse)
async def validate_preflight(req: PreflightRequest):
    """
    Executes the 18-point preflight validation gate before creating a durable run.
    Validates input contracts, permissions, token budgets, and dependencies.
    """
    try:
        response = preflight_service.validate_preflight(req)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Preflight validation failed with internal error: {str(e)}"
        )

