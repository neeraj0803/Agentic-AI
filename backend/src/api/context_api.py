from fastapi import APIRouter

from ..schemas.context_request import (
    ContextAnalyzerRequest
)

from ..services.context_service import (
    ContextAnalyzerService
)

router = APIRouter()

context_service = ContextAnalyzerService()


@router.post("/analyze")
async def analyze_context(
    request: ContextAnalyzerRequest
):

    result = context_service.analyze(
        document_name=request.document_name,
        extracted_text=request.document_text
    )

    return result