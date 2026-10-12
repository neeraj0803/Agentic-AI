from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class WorkflowRunStatus(str, Enum):
    # 17 Canonical Enterprise States
    RUN_CREATED = "run_created"
    QUEUED = "queued"
    RUNNING = "running"
    STEP_RUNNING = "step_running"
    PAUSED_FOR_VALIDATION = "paused_for_validation"
    AWAITING_APPROVAL = "awaiting_approval"
    REWORK_REQUESTED = "rework_requested"
    APPROVED_TO_WRITE = "approved_to_write"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"
    DISPATCH_FAILED = "dispatch_failed"
    WRITE_FAILED = "write_failed"
    RESUMING = "resuming"

    # Compatibility Aliases for Legacy Worker / Tests
    LEGACY_QUEUED = "QUEUED"
    LEGACY_RUNNING = "RUNNING"
    LEGACY_WAITING_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    LEGACY_WAITING_APPROVAL = "WAITING_FOR_APPROVAL"
    LEGACY_COMPLETED = "COMPLETED"
    LEGACY_FAILED = "FAILED"
    LEGACY_CANCELLED = "CANCELLED"


class SessionState(str, Enum):
    SESSION_CREATED = "session_created"
    ACTIVE_INTAKE = "active_intake"
    INTENT_RESOLVED = "intent_resolved"
    PREFLIGHT_READY = "preflight_ready"
    RUN_DISPATCHED = "run_dispatched"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


# -------------------------------------------------------------------
# Conversational Intake & Session Models
# -------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    team_id: str = Field(default="team-checkout-qe", description="Team workspace identifier")
    user_id: str = Field(default="usr-architect-01", description="Initiating user ID")
    requested_agent_id: Optional[str] = Field(default=None, description="Explicit agent requested if known")
    intake_channel: str = Field(default="WEB_PORTAL", description="Channel: WEB_PORTAL, SLACK, JIRA, CLI")
    session_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata or context tags")


class SessionResponse(BaseModel):
    session_id: str
    tenant_id: str = "default-tenant"
    team_id: str
    user_id: str
    requested_agent_id: Optional[str] = None
    session_state: str
    intake_channel: str
    trace_id: str
    session_metadata: Dict[str, Any] = Field(default_factory=dict)
    expires_at: str
    created_at: str
    updated_at: str


class SessionMessageRequest(BaseModel):
    user_id: str = Field(default="usr-architect-01", description="User posting the message")
    message: str = Field(..., description="Conversational text or requirement prompt")
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Attached documents or files")
    current_inputs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Accumulated input fields")


class SessionMessageResponse(BaseModel):
    session_id: str
    message_id: str
    assistant_reply: str
    resolved_agent_id: Optional[str] = None
    confidence_score: float = 0.0
    accumulated_inputs: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    is_preflight_ready: bool = False
    preflight_check: Optional[Dict[str, Any]] = None


# -------------------------------------------------------------------
# Preflight Validation Models
# -------------------------------------------------------------------

class PreflightRequest(BaseModel):
    agent_id: Optional[str] = Field(default=None, description="Target Agent Workflow ID (e.g. AG-101, AG-201)")
    agent_identifier: Optional[str] = Field(default=None, description="Target Agent Workflow ID alias")
    team_id: str = Field(default="team-checkout-qe", description="Team workspace ID")
    user_id: str = Field(default="usr-architect-01", description="Requesting user ID")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Draft inputs to validate")
    estimated_tokens: Optional[int] = Field(default=None, description="Estimated token count")
    session_id: Optional[str] = Field(default=None, description="Linked session ID")


class PreflightCheckResult(BaseModel):
    rule_id: str
    rule_name: str
    status: Literal["PASS", "FAIL", "WARN", "SKIPPED"]
    severity: Literal["BLOCKER", "WARNING", "INFO"]
    error_code: Optional[str] = None
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class PreflightResponse(BaseModel):
    valid: bool
    agent_id: str
    team_id: str
    rule_results: List[PreflightCheckResult]
    error_codes: List[str]
    blockers_count: int
    warnings_count: int
    missing_required_fields: List[str] = Field(default_factory=list)
    resolved_context_summary: Dict[str, Any] = Field(default_factory=dict)
    resolved_skills_summary: List[str] = Field(default_factory=list)


# -------------------------------------------------------------------
# Intent Resolution Models
# -------------------------------------------------------------------

class ResolveIntentRequest(BaseModel):
    user_prompt: str = Field(..., description="Raw text prompt from user")
    team_id: Optional[str] = Field(default="team-checkout-qe", description="Team ID")
    context_hints: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Context clues")


class ResolveIntentResponse(BaseModel):
    top_agent_id: Optional[str]
    confidence_score: float
    workflow_name: Optional[str]
    extracted_parameters: Dict[str, Any] = Field(default_factory=dict)
    suggested_alternatives: List[Dict[str, Any]] = Field(default_factory=list)


# -------------------------------------------------------------------
# Run Creation & Status Models
# -------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    agent_name: str = Field(default="qe_test_case_generation_agent", description="Canonical workflow agent identifier (e.g. AG-201 or qe_test_case_generation_agent)")
    agent_version: str = Field(default="1.0.0", description="Semantic version of the agent to lock")
    team_id: str = Field(default="team-checkout-qe", description="Team workspace identifier for governance & entitlements")
    user_id: str = Field(default="usr-architect-01", description="Initiating user ID")
    session_id: Optional[str] = Field(default=None, description="Linked intake session ID if applicable")
    policy_version: Optional[str] = Field(default=None, description="Enterprise policy snapshot version")
    idempotency_key: Optional[str] = Field(default=None, description="Client idempotency key")
    input_data: Dict[str, Any] = Field(
        default_factory=lambda: {
            "jira_story_id": "CHK-4091",
            "application_name": "Checkout Payment Service",
            "acceptance_criteria": [
                "Payment transaction must retry up to 3 times on transient network error (HTTP 503)",
                "If card is expired or declined (HTTP 402), do not retry and display user-friendly message",
                "Idempotency key must be preserved across retries to prevent duplicate charges"
            ],
            "target_output_format": "xray_bdd",
            "notes": "Verify retry backoff intervals."
        },
        description="Initial payload passed into the agent workflow"
    )
    timeout_seconds: Optional[int] = Field(default=300, description="Platform timeout policy threshold")
    skip_preflight: bool = Field(default=False, description="Whether to bypass preflight gate (for testing)")


class RunStatusResponse(BaseModel):
    run_id: str
    session_id: Optional[str] = None
    agent_name: str
    agent_version: str
    policy_version: str
    team_id: str
    status: str
    current_checkpoint_id: Optional[str] = None
    resolved_workflow_id: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    rework_cycle_count: int = 0
    validation_attempt_count: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    created_at: str
    updated_at: str


# -------------------------------------------------------------------
# Checkpoint & HITL Approvals / Rework Models
# -------------------------------------------------------------------

class ClarificationRequest(BaseModel):
    clarification_inputs: Dict[str, Any] = Field(
        ...,
        description="Clarification answers or missing documents provided by the user"
    )
    notes: Optional[str] = Field(default=None, description="Optional notes from the user")


class ApprovalRequest(BaseModel):
    decision: Literal["approve", "request_changes", "reject"] = Field(
        default="approve",
        description="Human reviewer decision: approve, request_changes, reject"
    )
    reviewer_name: str = Field(default="Lead Quality Engineer", description="Name/Identity of approver")
    comments: Optional[str] = Field(default=None, description="Review feedback or revision directives")
    reviewed_payload_sha256: Optional[str] = Field(default=None, description="Hash of the payload being reviewed")


class ReworkRequest(BaseModel):
    feedback_text: str = Field(..., description="Actionable revision directives")
    reviewer_name: str = Field(default="Lead Reviewer", description="Name of the reviewer requesting rework")
    resume_target_step_id: Optional[str] = Field(default="step_03", description="Graph node step to revert execution to")


class ResumeRequest(BaseModel):
    checkpoint_id: str = Field(..., description="Checkpoint ID to resume from (e.g. CP-01, CP-05)")
    resume_payload: Dict[str, Any] = Field(default_factory=dict, description="Supplementary payload to inject upon resumption")


class CancelRunRequest(BaseModel):
    reason: Optional[str] = Field(default="User initiated cancellation", description="Reason for run abortion")

