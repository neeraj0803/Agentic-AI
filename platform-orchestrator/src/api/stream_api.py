from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..services.run_lifecycle_service import run_lifecycle_service
from ..streaming.sse_broadcaster import sse_broadcaster

router = APIRouter(prefix="/runs", tags=["UI Real-Time Streams"])


@router.get("/{run_id}/stream")
async def stream_run_lifecycle_events(run_id: str):
    """
    Server-Sent Events (SSE) streaming endpoint for real-time UI dashboard updates.
    Yields macro run state transitions, checkpoint notices, and completion payloads.
    """
    run = run_lifecycle_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    return StreamingResponse(
        sse_broadcaster.stream_for_run(run_id=run_id, replay_history=True),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
