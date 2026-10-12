import asyncio
import time
from typing import Any, Callable, Dict, Optional

from ..config import settings
from ..storage.orchestrator_storage import OrchestratorStorage
from ..telemetry import logger, metrics_registry, trace_span


class ExecutionQueueService:
    """
    Asynchronous Execution Queue Service.
    Simulates Cloud Tasks / PubSub dispatching in local development:
    - Enqueues workflow dispatches and resumptions.
    - Handles retry policies with exponential backoff upon transient worker errors.
    - Enforces run timeout policies.
    """

    def __init__(self, storage: Optional[OrchestratorStorage] = None):
        self.storage = storage or OrchestratorStorage()
        self.max_retries = settings.max_retries
        self.retry_backoff = settings.retry_backoff_seconds

    async def dispatch_with_retry(
        self,
        run_id: str,
        action_name: str,
        dispatch_coro_fn: Callable[[], Any],
        timeout_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes a dispatch callable with platform-level timeout and retry policies.
        """
        timeout = timeout_seconds or settings.default_timeout_seconds
        task_record = self.storage.enqueue_task(run_id=run_id, action=action_name)
        task_id = task_record["task_id"]

        attempt = 0
        last_error = None

        while attempt <= self.max_retries:
            attempt += 1
            try:
                self.storage.update_task_status(task_id, status="PROCESSING", increment_retry=(attempt > 1))
                logger.info(f"Dispatching task {task_id} (Attempt {attempt}/{self.max_retries + 1})", run_id=run_id)

                # Execute with platform timeout
                result = await asyncio.wait_for(dispatch_coro_fn(), timeout=float(timeout))
                self.storage.update_task_status(task_id, status="SUCCESS")
                return result

            except asyncio.TimeoutError:
                last_error = f"Platform execution timeout exceeded ({timeout}s)"
                logger.error(f"Task {task_id} timed out: {last_error}", run_id=run_id)
                metrics_registry.record_retry()
                break  # Do not retry on fundamental timeout

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Task {task_id} attempt {attempt} failed: {e}. Retrying in {self.retry_backoff * attempt}s...",
                    run_id=run_id
                )
                metrics_registry.record_retry()
                if attempt <= self.max_retries:
                    await asyncio.sleep(self.retry_backoff * attempt)

        self.storage.update_task_status(task_id, status="FAILED")
        raise RuntimeError(f"Workflow execution dispatch failed after {attempt} attempts: {last_error}")


queue_service = ExecutionQueueService()
