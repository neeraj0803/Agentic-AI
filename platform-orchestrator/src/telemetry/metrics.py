import time
from typing import Any, Dict
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider

_provider = MeterProvider()
metrics.set_meter_provider(_provider)
meter = metrics.get_meter("platform.orchestrator", "1.0.0")

# OpenTelemetry instruments
run_counter = meter.create_counter(
    "orchestrator_runs_total",
    description="Total workflow runs created and tracked by Platform Orchestrator",
    unit="1"
)

checkpoint_counter = meter.create_counter(
    "orchestrator_checkpoints_total",
    description="Total checkpoints saved or encountered across all runs",
    unit="1"
)

retry_counter = meter.create_counter(
    "orchestrator_retries_total",
    description="Total execution retries triggered by platform policies",
    unit="1"
)


class MetricsRegistry:
    """In-memory telemetry metrics aggregator for Prometheus/Dynatrace exposition and health monitoring."""

    def __init__(self):
        self._stats = {
            "runs_created": 0,
            "runs_completed": 0,
            "runs_failed": 0,
            "runs_cancelled": 0,
            "runs_waiting_clarification": 0,
            "runs_waiting_approval": 0,
            "checkpoints_recorded": 0,
            "retries_dispatched": 0,
            "durations": []
        }

    def record_run_created(self, agent_name: str, team_id: str) -> None:
        self._stats["runs_created"] += 1
        run_counter.add(1, {"agent": agent_name, "team": team_id, "status": "QUEUED"})

    def record_run_transition(self, status: str, duration_s: float = 0.0) -> None:
        if status == "COMPLETED":
            self._stats["runs_completed"] += 1
        elif status == "FAILED":
            self._stats["runs_failed"] += 1
        elif status == "CANCELLED":
            self._stats["runs_cancelled"] += 1
        elif status == "WAITING_FOR_CLARIFICATION":
            self._stats["runs_waiting_clarification"] += 1
        elif status == "WAITING_FOR_APPROVAL":
            self._stats["runs_waiting_approval"] += 1

        if duration_s > 0:
            self._stats["durations"].append(duration_s)

    def record_checkpoint(self, checkpoint_type: str) -> None:
        self._stats["checkpoints_recorded"] += 1
        checkpoint_counter.add(1, {"type": checkpoint_type})

    def record_retry(self) -> None:
        self._stats["retries_dispatched"] += 1
        retry_counter.add(1)

    def get_snapshot(self) -> Dict[str, Any]:
        durations = self._stats["durations"]
        avg_dur = round(sum(durations) / len(durations), 2) if durations else 0.0
        return {
            "runs_created": self._stats["runs_created"],
            "runs_completed": self._stats["runs_completed"],
            "runs_failed": self._stats["runs_failed"],
            "runs_cancelled": self._stats["runs_cancelled"],
            "runs_waiting_clarification": self._stats["runs_waiting_clarification"],
            "runs_waiting_approval": self._stats["runs_waiting_approval"],
            "checkpoints_recorded": self._stats["checkpoints_recorded"],
            "retries_dispatched": self._stats["retries_dispatched"],
            "average_completed_duration_seconds": avg_dur
        }


metrics_registry = MetricsRegistry()
