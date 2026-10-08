from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any, Dict, Optional

from .tracer import current_worker_run_id, current_worker_trace_id


class WorkerStructuredLogger:
    """
    Correlated JSON Logger for Agent Worker.
    Automatically attaches active run_id and trace_id to all log events.
    """

    def __init__(self, service_name: str = "agent-worker"):
        self.service_name = service_name
        self._std_logger = logging.getLogger(service_name)
        if not self._std_logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            self._std_logger.addHandler(handler)
            self._std_logger.setLevel(logging.INFO)

    def _emit(
        self,
        level: str,
        message: str,
        run_id: Optional[str] = None,
        node_name: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        rid = run_id or current_worker_run_id.get()
        tid = current_worker_trace_id.get()

        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "level": level,
            "message": message,
            "run_id": rid,
            "trace_id": tid,
            "node_name": node_name,
            "attributes": attributes or {}
        }
        self._std_logger.info(json.dumps(log_payload))

    def info(self, msg: str, run_id: Optional[str] = None, node_name: Optional[str] = None, **kwargs) -> None:
        self._emit("INFO", msg, run_id=run_id, node_name=node_name, attributes=kwargs)

    def warning(self, msg: str, run_id: Optional[str] = None, node_name: Optional[str] = None, **kwargs) -> None:
        self._emit("WARNING", msg, run_id=run_id, node_name=node_name, attributes=kwargs)

    def error(self, msg: str, run_id: Optional[str] = None, node_name: Optional[str] = None, **kwargs) -> None:
        self._emit("ERROR", msg, run_id=run_id, node_name=node_name, attributes=kwargs)


worker_logger = WorkerStructuredLogger()
