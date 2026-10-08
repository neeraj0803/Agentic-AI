from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentWorkerState(BaseModel):
    run_id: str
    jira_story_id: str
    application_name: str
    team_id: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    target_format: str = "xray_bdd"
    notes: Optional[str] = None
    candidate_tests: List[Dict[str, Any]] = Field(default_factory=list)
    coverage_matrix: Dict[str, Any] = Field(default_factory=dict)
    review_package: Optional[Dict[str, Any]] = None
    publish_receipt: Optional[Dict[str, Any]] = None
