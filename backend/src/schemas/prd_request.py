from pydantic import BaseModel, Field
from typing import Any


class PRDGenerateRequest(BaseModel):
    context: Any = Field(..., description="Business context, raw JSON list, or document-derived summary used to generate the PRD.")


class PRDGenerateResponse(BaseModel):
    title: str = "Product Requirements Document"
    document: str
