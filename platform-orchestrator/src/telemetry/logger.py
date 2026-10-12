import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from .tracer import current_run_id_var

_logger_storage_hook: Any = None


def register_logger_storage_hook(storage: Any) -> None:
    """Registers a storage engine for persisting structured telemetry logs."""
    global _logger_storage_hook
    _logger_storage_hook = storage


class OrchestratorLogger:
    """Structured JSON Logger for the Platform Orchestrator with run correlation and database persistence."""

    def __init__(self, name: str = "platform.orchestrator"):
        self.name = name
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def _log(
        self,
        level: str,
        message: str,
        run_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        eff_run_id = run_id or current_run_id_var.get()
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "timestamp": timestamp,
            "level": level,
            "component": self.name,
            "message": message,
            "run_id": eff_run_id,
            "attributes": extra or {}
        }
        serialized = json.dumps(entry)
        if level == "ERROR":
            self._logger.error(serialized)
        elif level == "WARN":
            self._logger.warning(serialized)
        elif level == "DEBUG":
            self._logger.debug(serialized)
        else:
            self._logger.info(serialized)

        # Persist to database if storage hook is registered
        if _logger_storage_hook and hasattr(_logger_storage_hook, "record_log"):
            try:
                _logger_storage_hook.record_log(
                    level=level,
                    component=self.name,
                    message=message,
                    run_id=eff_run_id,
                    attributes=extra
                )
            except Exception:
                pass

    def info(self, message: str, run_id: Optional[str] = None, **kwargs) -> None:
        self._log("INFO", message, run_id=run_id, extra=kwargs)

    def warning(self, message: str, run_id: Optional[str] = None, **kwargs) -> None:
        self._log("WARN", message, run_id=run_id, extra=kwargs)

    def error(self, message: str, run_id: Optional[str] = None, **kwargs) -> None:
        self._log("ERROR", message, run_id=run_id, extra=kwargs)

    def debug(self, message: str, run_id: Optional[str] = None, **kwargs) -> None:
        self._log("DEBUG", message, run_id=run_id, extra=kwargs)


logger = OrchestratorLogger()
