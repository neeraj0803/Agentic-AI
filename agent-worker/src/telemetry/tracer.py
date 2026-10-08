import contextvars
import secrets
import time
from typing import Any, Dict, Optional

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.sdk.trace import TracerProvider
    _provider = TracerProvider()
    trace.set_tracer_provider(_provider)
    _real_tracer = trace.get_tracer("agent.worker", "1.0.0")
    HAS_OPENTELEMETRY = True
except (ImportError, Exception):
    HAS_OPENTELEMETRY = False
    _real_tracer = None

current_worker_run_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_worker_run_id", default=None)
current_worker_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_worker_trace_id", default=None)


class WorkerSpan:
    """
    OpenTelemetry Span Context Manager for Agent Worker.
    Propagates W3C distributed trace context received from Platform Orchestrator
    and measures latency per internal graph node.
    """

    def __init__(
        self,
        name: str,
        run_id: Optional[str] = None,
        traceparent: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.run_id = run_id or current_worker_run_id.get()
        self.traceparent = traceparent
        self.attributes = attributes or {}
        self._span = None
        self._start_time = 0.0
        self.trace_id: Optional[str] = None
        self.span_id: Optional[str] = None

    def __enter__(self):
        self._start_time = time.time()
        if self.run_id:
            current_worker_run_id.set(self.run_id)

        # Parse incoming W3C traceparent (format: 00-{trace_id}-{parent_id}-01)
        if self.traceparent and self.traceparent.startswith("00-"):
            parts = self.traceparent.split("-")
            if len(parts) >= 3:
                self.trace_id = parts[1]

        if not self.trace_id:
            self.trace_id = current_worker_trace_id.get() or secrets.token_hex(16)
        current_worker_trace_id.set(self.trace_id)
        self.span_id = secrets.token_hex(8)

        if HAS_OPENTELEMETRY and _real_tracer:
            try:
                self._span = _real_tracer.start_span(self.name)
                if self.run_id:
                    self._span.set_attribute("agent_worker.run_id", self.run_id)
                for k, v in self.attributes.items():
                    if isinstance(v, (str, bool, int, float)):
                        self._span.set_attribute(k, v)
                    else:
                        self._span.set_attribute(k, str(v))
            except Exception:
                self._span = None

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self._start_time) * 1000.0

        if self._span:
            try:
                if exc_type is not None:
                    self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
                    self._span.record_exception(exc_val)
                else:
                    self._span.set_status(Status(StatusCode.OK))
                self._span.end()
            except Exception:
                pass
        return False

    def get_w3c_traceparent(self) -> str:
        t_id = self.trace_id or secrets.token_hex(16)
        s_id = self.span_id or secrets.token_hex(8)
        return f"00-{t_id}-{s_id}-01"


def trace_worker_span(
    name: str,
    run_id: Optional[str] = None,
    traceparent: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
) -> WorkerSpan:
    return WorkerSpan(name=name, run_id=run_id, traceparent=traceparent, attributes=attributes)
