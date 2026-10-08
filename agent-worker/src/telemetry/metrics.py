import threading
import time
from typing import Any, Dict, List, Optional


class WorkerMetricsRegistry:
    """
    OpenTelemetry Metrics Collector for Agent Worker.
    Captures operational observability for:
    - Internal LangGraph node latencies
    - Context retrieval & skill invocation counts
    - Test scenario generation throughput
    - Durable checkpoint yields (CP-01, CP-05, CP-FINAL)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.flow_executions: Dict[str, int] = {}
        self.node_durations: Dict[str, List[float]] = {}
        self.skills_bound: Dict[str, int] = {}
        self.checkpoints_emitted: Dict[str, int] = {}
        self.total_test_scenarios_generated = 0
        self.start_time = time.time()

    def record_node_execution(self, node_name: str, duration_seconds: float) -> None:
        with self._lock:
            if node_name not in self.node_durations:
                self.node_durations[node_name] = []
            self.node_durations[node_name].append(round(duration_seconds, 4))
            # Keep recent 200 samples per node
            if len(self.node_durations[node_name]) > 200:
                self.node_durations[node_name].pop(0)

    def record_flow_result(self, agent_name: str, status: str) -> None:
        with self._lock:
            key = f"{agent_name}:{status}"
            self.flow_executions[key] = self.flow_executions.get(key, 0) + 1

    def record_skills_bound(self, skills: List[str]) -> None:
        with self._lock:
            for s in skills:
                self.skills_bound[s] = self.skills_bound.get(s, 0) + 1

    def record_checkpoint_emitted(self, checkpoint_id: str) -> None:
        with self._lock:
            self.checkpoints_emitted[checkpoint_id] = self.checkpoints_emitted.get(checkpoint_id, 0) + 1

    def record_scenarios_generated(self, count: int) -> None:
        with self._lock:
            self.total_test_scenarios_generated += count

    def get_metrics_summary(self) -> Dict[str, Any]:
        with self._lock:
            avg_durations = {}
            for node, durations in self.node_durations.items():
                if durations:
                    avg_durations[node] = {
                        "count": len(durations),
                        "avg_ms": round((sum(durations) / len(durations)) * 1000.0, 2),
                        "max_ms": round(max(durations) * 1000.0, 2)
                    }

            return {
                "service": "agent-worker",
                "uptime_seconds": round(time.time() - self.start_time, 2),
                "flow_executions": dict(self.flow_executions),
                "node_performance": avg_durations,
                "skills_bound": dict(self.skills_bound),
                "checkpoints_emitted": dict(self.checkpoints_emitted),
                "total_test_scenarios_generated": self.total_test_scenarios_generated
            }


worker_metrics_registry = WorkerMetricsRegistry()
