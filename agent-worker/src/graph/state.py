from typing import Any, Dict, List, Optional, TypedDict
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


class InputDocument(TypedDict, total=False):
    document_id: str
    name: str
    type: str
    mime_type: str
    file_path: str | None
    content: str | None
    size_bytes: int | None
    uploaded_by: str | None
    uploaded_at: str | None


class WorkflowNode(TypedDict, total=False):
    node_id: str
    node_name: str
    node_type: str
    next_node: str | None
    variables: dict[str, Any]
    output: Any


class WorkflowState(TypedDict, total=False):
    workflow_session_id: str
    type: str
    status: str
    current_node: str
    input_documents: list[InputDocument]
    nodes: list[WorkflowNode]
    errors: list[str]
