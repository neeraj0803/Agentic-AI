from fastapi import APIRouter

from ..schemas.prd_request import PRDGenerateRequest, PRDGenerateResponse
from ..services.prd_service import PRDGeneratorService

router = APIRouter()


@router.post("/generate", response_model=PRDGenerateResponse)
def generate_prd(payload: PRDGenerateRequest):
    document = PRDGeneratorService().generate(payload.context)
    return PRDGenerateResponse(
        title="Product Requirements Document",
        document=document,
    )
