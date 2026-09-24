from typing import Any, TypedDict


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