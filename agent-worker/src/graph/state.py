from typing import Any, TypedDict


class InputField(TypedDict, total=False):
    id: str
    type: str
    required: bool
    prompt: str
    validation: dict[str, Any]
    allowed_values: list[str]
    default: Any
    value: Any


class InputDocument(TypedDict, total=False):
    doc_id: str
    doc_type: str
    content: str
    metadata: dict[str, Any]


class AgentWorkerState(TypedDict, total=False):
    run_id: str
    agent_name: str
    agent_version: str
    team_id: str
    status: str
    current_node: str
    next_node: str
    inputs: dict[str, Any]
    input_documents: list[InputDocument]
    nodes: list[dict[str, Any]]
    checkpoint_id: str | None
    outputs: dict[str, Any]
    errors: list[str]



class WorkflowNode(TypedDict, total=False):
    id: str
    node_id: str
    node_name: str
    type: str
    node_type: str
    connector_ref: str | None
    skill_ref: str | None
    checkpoint: bool | str | None
    reviewer: str | None
    additional_reviewers: list[str] | None
    max_rework: int | None
    rework_resume_to: str | None
    execute_only_after_approval: bool | None
    variables: dict[str, Any]
    output: Any
    status: str


class WorkflowState(TypedDict, total=False):
    conversation_id: str
    workflow_session_id: str
    workflow_id: str
    version: str
    type: str
    status: str
    current_node: str
    next_node: str
    agent: dict[str, Any]
    actors: dict[str, Any]
    channels: dict[str, Any]
    run_modes: dict[str, Any]
    inputs: Any
    input_context: Any
    validated_inputs: dict[str, Any]
    intake: dict[str, Any]
    context: dict[str, Any]
    context_data: dict[str, Any]
    skills: dict[str, Any]
    context_brief: dict[str, Any]
    model_policy_ref: str
    drafted_tests: dict[str, Any]
    artifacts: dict[str, Any]
    artifact_path: str
    artifact_file: str
    artifact_content: str
    rework_count: int
    rework_feedback: str
    review_history: list[dict[str, Any]]
    publish_result: dict[str, Any]
    graph: dict[str, Any]
    nodes: list[WorkflowNode]
    edges: list[dict[str, str]]
    outputs: dict[str, Any]
    failure_policy: dict[str, Any]
    errors: list[str]
