import contextvars
import os
import secrets
import time
from typing import Any, Dict, Optional

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.sdk.trace import TracerProvider
    _provider = TracerProvider()
    trace.set_tracer_provider(_provider)
    _real_tracer = trace.get_tracer("platform.orchestrator", "1.0.0")
    HAS_OPENTELEMETRY = True
except (ImportError, Exception):
    HAS_OPENTELEMETRY = False
    _real_tracer = None

current_run_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_run_id", default=None)
_storage_hook: Any = None


def register_tracer_storage_hook(storage: Any) -> None:
    """Registers a storage engine for persisting OpenTelemetry spans."""
    global _storage_hook
    _storage_hook = storage


class OrchestratorSpan:
    """
    OpenTelemetry Span Context manager for the Platform Orchestrator.
    Emits W3C-compliant traces and injects span correlation into logs and worker requests.
    Falls back gracefully to standard W3C trace generation if opentelemetry package is not installed.
    """

    def __init__(
        self,
        name: str,
        run_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.run_id = run_id or current_run_id_var.get()
        self.attributes = attributes or {}
        self._span = None
        self._token_run = None
        self._start_time = 0.0
        self.trace_id: Optional[str] = None
        self.span_id: Optional[str] = None

    def __enter__(self):
        self._start_time = time.time()
        if self.run_id:
            self._token_run = current_run_id_var.set(self.run_id)

        if HAS_OPENTELEMETRY and _real_tracer:
            try:
                self._span = _real_tracer.start_span(self.name)
                ctx = self._span.get_span_context()
                if ctx and ctx.trace_id:
                    self.trace_id = format(ctx.trace_id, "032x")
                    self.span_id = format(ctx.span_id, "016x")
                if self.run_id:
                    self._span.set_attribute("orchestrator.run_id", self.run_id)
                for k, v in self.attributes.items():
                    if isinstance(v, (str, bool, int, float)):
                        self._span.set_attribute(k, v)
                    else:
                        self._span.set_attribute(k, str(v))
            except Exception:
                self._span = None

        if not self.trace_id:
            self.trace_id = secrets.token_hex(16)
            self.span_id = secrets.token_hex(8)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self._start_time) * 1000.0
        status_code = "ERROR" if exc_type is not None else "OK"

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

        # Persist span to database if hook is registered
        if _storage_hook and hasattr(_storage_hook, "record_span"):
            try:
                _storage_hook.record_span(
                    span_id=self.span_id,
                    trace_id=self.trace_id,
                    name=self.name,
                    run_id=self.run_id,
                    duration_ms=duration_ms,
                    status_code=status_code,
                    attributes=self.attributes
                )
            except Exception:
                pass

        if self._token_run:
            current_run_id_var.reset(self._token_run)
        return False

    def get_w3c_traceparent(self) -> str:
        """Returns standard W3C traceparent header: 00-{trace_id}-{span_id}-01"""
        t_id = self.trace_id or secrets.token_hex(16)
        s_id = self.span_id or secrets.token_hex(8)
        return f"00-{t_id}-{s_id}-01"


def trace_span(
    name: str,
    run_id: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
) -> OrchestratorSpan:
    return OrchestratorSpan(name=name, run_id=run_id, attributes=attributes)

