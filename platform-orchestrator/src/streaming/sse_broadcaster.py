import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..storage.orchestrator_storage import OrchestratorStorage


class OrchestratorSSEBroadcaster:
    """
    Server-Sent Events (SSE) Broadcaster for Platform Orchestrator.
    Streams macro run status transitions, durable checkpoints, and HITL wait signals to UI portals.
    Supports durable event persistence into agent_run_event table and Last-Event-ID replay.
    """

    def __init__(self, storage: Optional[OrchestratorStorage] = None):
        self._listeners: Dict[str, List[asyncio.Queue]] = {}
        self._storage = storage

    def _get_storage(self) -> OrchestratorStorage:
        if self._storage is None:
            self._storage = OrchestratorStorage()
        return self._storage

    def broadcast(
        self,
        run_id: str,
        event_name: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        storage = self._get_storage()
        current_state = state or payload.get("status", "running")
        
        # 1. Persist to agent_run_event
        db_event = storage.append_event(
            event_type=event_name,
            state=str(current_state).lower(),
            event_payload=payload,
            run_id=run_id,
            session_id=session_id
        )

        event_obj = {
            "id": db_event["sequence_no"],
            "event_id": db_event["event_id"],
            "run_id": run_id,
            "session_id": session_id,
            "event": event_name,
            "state": db_event["state"],
            "timestamp": db_event["occurred_at"],
            "data": payload
        }

        # 2. Notify active listeners for run_id
        if run_id in self._listeners:
            for q in list(self._listeners[run_id]):
                try:
                    q.put_nowait(event_obj)
                except asyncio.QueueFull:
                    pass

        # 3. Notify listeners for session_id if listening at session level
        if session_id and session_id in self._listeners:
            for q in list(self._listeners[session_id]):
                try:
                    q.put_nowait(event_obj)
                except asyncio.QueueFull:
                    pass

        return event_obj

    async def stream_for_run(
        self,
        run_id: str,
        replay_history: bool = True,
        last_event_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        if run_id not in self._listeners:
            self._listeners[run_id] = []
        self._listeners[run_id].append(queue)

        try:
            # 1. Replay past events from storage
            if replay_history:
                storage = self._get_storage()
                past_events = storage.list_events(run_id=run_id, since_sequence_no=last_event_id, limit=200)
                for past in past_events:
                    seq_id = past.get("sequence_no", 0)
                    evt_name = past.get("event_type", "message")
                    data_str = json.dumps(past.get("event_payload", {}))
                    yield f"id: {seq_id}\nevent: {evt_name}\ndata: {data_str}\n\n"

            # 2. Stream live events
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    seq_id = event.get("id", 0)
                    evt_name = event.get("event", "message")
                    data_str = json.dumps(event.get("data", {}))
                    yield f"id: {seq_id}\nevent: {evt_name}\ndata: {data_str}\n\n"
                    
                    if evt_name in ["run_completed", "run_failed", "run_cancelled", "run_rejected"]:
                        break
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"

        finally:
            if run_id in self._listeners and queue in self._listeners[run_id]:
                self._listeners[run_id].remove(queue)
                if not self._listeners[run_id]:
                    del self._listeners[run_id]

    async def stream_for_session(
        self,
        session_id: str,
        replay_history: bool = True,
        last_event_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        if session_id not in self._listeners:
            self._listeners[session_id] = []
        self._listeners[session_id].append(queue)

        try:
            if replay_history:
                storage = self._get_storage()
                past_events = storage.list_events(session_id=session_id, since_sequence_no=last_event_id, limit=200)
                for past in past_events:
                    seq_id = past.get("sequence_no", 0)
                    evt_name = past.get("event_type", "message")
                    data_str = json.dumps(past.get("event_payload", {}))
                    yield f"id: {seq_id}\nevent: {evt_name}\ndata: {data_str}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    seq_id = event.get("id", 0)
                    evt_name = event.get("event", "message")
                    data_str = json.dumps(event.get("data", {}))
                    yield f"id: {seq_id}\nevent: {evt_name}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"

        finally:
            if session_id in self._listeners and queue in self._listeners[session_id]:
                self._listeners[session_id].remove(queue)
                if not self._listeners[session_id]:
                    del self._listeners[session_id]


sse_broadcaster = OrchestratorSSEBroadcaster()
