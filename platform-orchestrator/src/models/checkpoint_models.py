from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CheckpointMetadata(BaseModel):
    run_id: str
    checkpoint_id: str
    step_name: str
    node_name: str
    checkpoint_type: str
    created_at: str
    metadata: Optional[Dict[str, Any]] = None


class CheckpointDetailResponse(BaseModel):
    run_id: str
    checkpoint_id: str
    step_name: str
    node_name: str
    checkpoint_type: str
    state_snapshot: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
