from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ConfluencePageRequest(BaseModel):
    page_id: str = Field(..., description="Confluence page identifier or mock page key")
    space_key: Optional[str] = Field(default=None, description="Optional Confluence space key")


class ConfluencePageResponse(BaseModel):
    page_id: Optional[str] = None
    space_key: Optional[str] = None
    title: Optional[str] = None
    problem_statement: str = ""
    supporting_evidence: List[str] = Field(default_factory=list)
    business_goal: str = ""
    expected_outcome: str = ""
    application_indicator: str = "Unknown"
    assumptions: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    users: List[str] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)
    raw_notes: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"
