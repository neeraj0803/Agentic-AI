from typing import Any, Dict, List, Optional

from ..storage.orchestrator_storage import OrchestratorStorage
from ..telemetry import logger, metrics_registry


class CheckpointManagementService:
    """
    Service managing durable Human-in-the-Loop checkpoints:
    - Ingests checkpoints emitted by Agent Workers (CP-01, CP-05, etc.)
    - Verifies checkpoint eligibility for resumption
    - Provides historical snapshots for audit and rollback
    """

    def __init__(self, storage: Optional[OrchestratorStorage] = None):
        self.storage = storage or OrchestratorStorage()

    def record_checkpoint(
        self,
        run_id: str,
        checkpoint_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        cp_id = checkpoint_data.get("checkpoint_id", "CP-UNKNOWN")
        step_name = checkpoint_data.get("step_name", "Unknown Step")
        node_name = checkpoint_data.get("node_name", "unknown_node")
        cp_type = checkpoint_data.get("checkpoint_type", "STEP_SAVE")
        snapshot = checkpoint_data.get("state_snapshot", {})
        metadata = checkpoint_data.get("metadata", {})

        saved = self.storage.save_checkpoint(
            run_id=run_id,
            checkpoint_id=cp_id,
            step_name=step_name,
            node_name=node_name,
            checkpoint_type=cp_type,
            state_snapshot=snapshot,
            metadata=metadata
        )

        metrics_registry.record_checkpoint(cp_type)
        logger.info(
            f"Durable Checkpoint {cp_id} recorded for run {run_id} ({cp_type})",
            run_id=run_id,
            checkpoint_id=cp_id
        )
        return saved

    def get_checkpoint(self, run_id: str, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_checkpoint(run_id, checkpoint_id)

    def list_checkpoints(self, run_id: str) -> List[Dict[str, Any]]:
        return self.storage.list_checkpoints(run_id)


checkpoint_service = CheckpointManagementService()
