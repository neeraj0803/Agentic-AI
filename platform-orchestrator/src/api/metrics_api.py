from typing import Optional
from fastapi import APIRouter, Query
from ..storage.orchestrator_storage import OrchestratorStorage
from ..telemetry.metrics import metrics_registry

router = APIRouter(tags=["Platform Observability, Telemetry & Audit"])
storage = OrchestratorStorage()


@router.get("/metrics")
async def get_orchestrator_metrics():
    """
    Exposes aggregated OpenTelemetry execution metrics for Platform Orchestrator:
    runs created, transitions, active checkpoints, retries, and latency.
    """
    return {
        "status": "healthy",
        "service": "platform-orchestrator",
        "telemetry_metrics": metrics_registry.get_snapshot()
    }


@router.get("/telemetry/database")
async def get_database_status():
    """
    Inspects durable SQLite database schema and row counts across all 8 enterprise tables:
    runs, checkpoints, tasks, spans, logs, metrics, audit events, and policy snapshots.
    """
    return storage.get_database_summary()


@router.get("/telemetry/spans")
async def get_telemetry_spans(
    run_id: Optional[str] = Query(None, description="Filter spans by workflow run ID"),
    trace_id: Optional[str] = Query(None, description="Filter spans by W3C trace ID"),
    limit: int = Query(50, ge=1, le=500)
):
    """Retrieves captured OpenTelemetry distributed trace spans with durations and status codes."""
    spans = storage.list_spans(run_id=run_id, trace_id=trace_id, limit=limit)
    return {"total": len(spans), "spans": spans}


@router.get("/telemetry/logs")
async def get_telemetry_logs(
    run_id: Optional[str] = Query(None, description="Filter logs by workflow run ID"),
    level: Optional[str] = Query(None, description="Filter by log level: INFO, WARN, ERROR"),
    limit: int = Query(100, ge=1, le=500)
):
    """Retrieves correlated structured JSON execution logs."""
    logs = storage.list_logs(run_id=run_id, level=level, limit=limit)
    return {"total": len(logs), "logs": logs}


@router.get("/telemetry/audit")
async def get_audit_trail(
    run_id: Optional[str] = Query(None, description="Filter audit events by workflow run ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=500)
):
    """Retrieves compliance and Human-in-the-Loop audit events (checkpoints, approvals, writebacks)."""
    events = storage.list_audit_events(run_id=run_id, event_type=event_type, limit=limit)
    return {"total": len(events), "audit_events": events}


@router.get("/health")
async def health_check():
    """Liveness & readiness probe for Kubernetes / Cloud Run."""
    return {
        "status": "UP",
        "service": "platform-orchestrator",
        "version": "1.0.0"
    }
