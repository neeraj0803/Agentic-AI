from pydantic import BaseModel
from typing import Optional


class ContextAnalyzerRequest(BaseModel):
    document_name: Optional[str] = None
    document_text: str