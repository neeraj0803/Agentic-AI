from typing import Any, Dict, Optional
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from ..graph.worker_graph import worker_executor
from ..telemetry import worker_metrics_registry

router = APIRouter(tags=["Agent Worker Execution Engine"])


class WorkerDispatchRequest(BaseModel):
    run_id: str
    agent_name: str
    agent_version: str
    team_id: str
    input_data: Dict[str, Any] = Field(default_factory=dict)


class WorkerResumeRequest(BaseModel):
    run_id: str
    checkpoint_id: str
    resume_payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/worker/dispatch")
async def dispatch_worker_flow(
    req: WorkerDispatchRequest,
    traceparent: Optional[str] = Header(None, alias="traceparent")
):
    """
    Executes the continuous 5-step processing flow until a durable boundary
    (clarification, approval, or completion) is encountered.
    Propagates incoming W3C traceparent header from Platform Orchestrator.
    """
    return worker_executor.execute_flow(
        run_id=req.run_id,
        agent_name=req.agent_name,
        agent_version=req.agent_version,
        team_id=req.team_id,
        input_data=req.input_data,
        traceparent=traceparent
    )


@router.post("/worker/resume")
async def resume_worker_flow(
    req: WorkerResumeRequest,
    traceparent: Optional[str] = Header(None, alias="traceparent")
):
    """
    Resumes worker execution from a previously saved checkpoint snapshot.
    """
    return worker_executor.resume_flow(
        run_id=req.run_id,
        checkpoint_id=req.checkpoint_id,
        resume_payload=req.resume_payload,
        traceparent=traceparent
    )


@router.get("/metrics")
@router.get("/worker/metrics")
async def get_worker_telemetry_metrics():
    """
    OpenTelemetry Metrics endpoint for Agent Worker.
    Provides node-by-node latencies, skill usage, throughput, and checkpoint yields.
    """
    return worker_metrics_registry.get_metrics_summary()


@router.get("/worker/info")
async def get_worker_info():
    """
    Returns Agent Worker architectural capabilities and node definitions.
    """
    return {
        "service": "Agent Worker",
        "runtime": "LangGraph Continuous Execution Window",
        "supported_agents": [
            "product_prd_or_context_brief_agent (Write PRD or Context Brief)",
            "qe_test_case_generation_agent (Write Test Cases from Requirements)"
        ],
        "durable_boundaries": ["CP-01 (Clarification)", "CP-05 (Human Approval)", "CP-FINAL (Complete)"],
        "delegable_subworkers": [
            "Synthetic Data Generation Worker",
            "Parallel Browser Testing Worker",
            "Xray Publishing Worker",
            "Confluence Publishing Worker"
        ],
        "nodes": [
            "1. Understand Requirement / Stakeholder Inputs & Validate Inputs",
            "2. Retrieve Application / Domain Context (Context Engine)",
            "3. Identify Impacted Modules & Select Skills (Skill Engine)",
            "4. Generate Candidate Output / Synthesize Brief (LiteLLM / Tools)",
            "5. Review Quality, Check Completeness & Assemble Review Package"
        ]
    }


@router.get("/health")
async def health():
    return {"status": "UP", "service": "agent-worker"}
