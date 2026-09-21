from pathlib import Path

from fastapi import APIRouter
from fastapi import UploadFile
from fastapi import File

from ..services.document_extractor_service import (
    DocumentExtractorService
)

from ..schemas.context_response import (
    ContextAnalyzerResponse
)

from ..constants import DOCUMENT_UPLOAD_PATH

from ..services.context_service import (
    ContextAnalyzerService
)

context_analyzer_service = ContextAnalyzerService()

router = APIRouter()


@router.post(
    "/upload",
    response_model=ContextAnalyzerResponse
)
async def upload_document(
    file: UploadFile = File(...)
):

    Path(DOCUMENT_UPLOAD_PATH).mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = (
        f"{DOCUMENT_UPLOAD_PATH}/{file.filename}"
    )

    with open(
        file_path,
        "wb"
    ) as buffer:

        buffer.write(
            await file.read()
        )

    extracted_text = (
        DocumentExtractorService
        .extract_text(file_path)
    )

    result = context_analyzer_service.analyze(
        document_name=file.filename,
        extracted_text=extracted_text
    )

    return result