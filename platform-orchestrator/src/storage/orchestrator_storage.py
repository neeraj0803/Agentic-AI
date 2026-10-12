import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings


class OrchestratorStorage:
    """
    Enterprise Durable Storage Engine for Platform Orchestrator.
    Supports both SQLite (local embedded) and MySQL 8.0+ schemas.
    
    Tables Managed:
    1. agent_run_session: Conversational intake sessions
    2. agent_run / orchestrator_runs: Authoritative macro run records
    3. agent_run_resolved_workflow: Immutable compiled YAML snapshots (rwf_*)
    4. agent_run_overlay: Context, skills, and validation overlays
    5. agent_run_state_transition: 17-state macro state transition ledger
    6. agent_run_event: Append-only SSE & trace event store
    7. orchestrator_checkpoints: Durable HITL checkpoints (CP-01, CP-05, etc.)
    8. approval_request / approval_decision / approval_feedback: Human governance gates
    9. idempotency_key: Idempotent run deduplication
    10. orchestrator_telemetry_spans / logs / metrics / audit_events: Observability
    """

    def __init__(self, db_path: Optional[str] = None):
        import threading
        self._lock = threading.RLock()
        if db_path:
            self.db_path = Path(db_path)
        else:
            base_dir = Path(__file__).resolve().parent.parent
            self.db_path = base_dir / "orchestrator_local.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
            try:
                yield conn
            finally:
                conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # ------------------------------------------------------------------
            # 1. Intake Sessions Table
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_run_session (
                session_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'default-tenant',
                team_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                requested_agent_id TEXT,
                session_state TEXT NOT NULL DEFAULT 'session_created',
                intake_channel TEXT NOT NULL DEFAULT 'WEB_PORTAL',
                trace_id TEXT NOT NULL,
                session_metadata TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # ------------------------------------------------------------------
            # 2. Canonical Runs Table (agent_run)
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_run (
                run_id TEXT PRIMARY KEY,
                session_id TEXT,
                tenant_id TEXT NOT NULL DEFAULT 'default-tenant',
                team_id TEXT NOT NULL,
                initiating_user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                agent_version TEXT NOT NULL DEFAULT '1.0.0',
                workflow_id TEXT NOT NULL,
                workflow_version TEXT NOT NULL DEFAULT '1.0.0',
                resolved_workflow_id TEXT NOT NULL,
                run_state TEXT NOT NULL DEFAULT 'run_created',
                pause_reason TEXT,
                current_checkpoint_id TEXT,
                total_cost_usd REAL NOT NULL DEFAULT 0.0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                idempotency_key TEXT UNIQUE,
                trace_id TEXT NOT NULL,
                input_data TEXT NOT NULL,
                output_data TEXT,
                error_message TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                rework_cycle_count INTEGER NOT NULL DEFAULT 0,
                validation_attempt_count INTEGER NOT NULL DEFAULT 0,
                timeout_seconds INTEGER NOT NULL DEFAULT 300,
                queued_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            );
            """)

            # ------------------------------------------------------------------
            # 2b. Legacy Runs Table (orchestrator_runs for backward compatibility)
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_runs (
                run_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                agent_version TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                team_id TEXT NOT NULL,
                status TEXT NOT NULL,
                current_checkpoint_id TEXT,
                input_data TEXT,
                output_data TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                timeout_seconds INTEGER DEFAULT 300,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            """)

            # ------------------------------------------------------------------
            # 3. Resolved Workflow Snapshot (agent_run_resolved_workflow)
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_run_resolved_workflow (
                resolved_workflow_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                sha256_hash TEXT NOT NULL,
                workflow_yaml TEXT NOT NULL,
                policy_snapshot TEXT NOT NULL,
                team_config_snapshot TEXT NOT NULL,
                step_bindings_map TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # ------------------------------------------------------------------
            # 4. Overlays Table (agent_run_overlay)
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_run_overlay (
                overlay_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                overlay_type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # ------------------------------------------------------------------
            # 5. State Transitions Table (agent_run_state_transition)
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_run_state_transition (
                transition_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_type TEXT NOT NULL DEFAULT 'SYSTEM',
                checkpoint_id TEXT,
                trace_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # ------------------------------------------------------------------
            # 6. Event Store (agent_run_event)
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_run_event (
                sequence_no INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                session_id TEXT,
                run_id TEXT,
                event_type TEXT NOT NULL,
                state TEXT NOT NULL,
                event_payload TEXT NOT NULL,
                producer_service TEXT NOT NULL DEFAULT 'platform-orchestrator',
                trace_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            """)

            # ------------------------------------------------------------------
            # 7. Checkpoints Table (orchestrator_checkpoints)
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_checkpoints (
                run_id TEXT NOT NULL,
                checkpoint_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                node_name TEXT NOT NULL,
                checkpoint_type TEXT NOT NULL,
                state_snapshot TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (run_id, checkpoint_id)
            );
            """)

            # ------------------------------------------------------------------
            # 8. Approvals & Human Review Tables
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS approval_request (
                approval_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                checkpoint_id TEXT NOT NULL,
                artifact_version_id TEXT NOT NULL,
                writeback_payload_version_id TEXT NOT NULL,
                reviewer_user_id TEXT NOT NULL,
                approval_state TEXT NOT NULL DEFAULT 'PENDING',
                rework_cycle_count INTEGER NOT NULL DEFAULT 0,
                requested_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS approval_decision (
                decision_id TEXT PRIMARY KEY,
                approval_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                decided_by TEXT NOT NULL,
                reviewed_payload_sha256 TEXT NOT NULL,
                comments TEXT,
                decided_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS approval_feedback (
                feedback_id TEXT PRIMARY KEY,
                approval_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                rework_cycle_number INTEGER NOT NULL,
                feedback_text TEXT NOT NULL,
                resume_target_step_id TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # ------------------------------------------------------------------
            # 9. Idempotency Reservations
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_key (
                idempotency_key_id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_fingerprint_sha256 TEXT NOT NULL,
                result_reference_id TEXT,
                status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (scope, idempotency_key)
            );
            """)

            # ------------------------------------------------------------------
            # 10. Observability / Telemetry Tables
            # ------------------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_task_queue (
                task_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                action TEXT NOT NULL,
                payload TEXT,
                status TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_telemetry_spans (
                span_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                parent_span_id TEXT,
                run_id TEXT,
                name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_ms REAL,
                status_code TEXT NOT NULL DEFAULT 'OK',
                attributes TEXT,
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_telemetry_logs (
                log_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                run_id TEXT,
                trace_id TEXT,
                span_id TEXT,
                level TEXT NOT NULL,
                component TEXT NOT NULL,
                message TEXT NOT NULL,
                attributes TEXT
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_telemetry_metrics (
                metric_id TEXT PRIMARY KEY,
                metric_name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT,
                labels TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_audit_events (
                audit_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                actor_name TEXT,
                details TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_policy_snapshots (
                policy_id TEXT PRIMARY KEY,
                policy_version TEXT NOT NULL,
                team_id TEXT NOT NULL,
                rules TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Performance Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON agent_run_session(user_id, session_state);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_run_team_state ON agent_run(team_id, run_state);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_run ON agent_run_event(run_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_run ON agent_run_state_transition(run_id);")

            conn.commit()

    # -------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------

    def create_session(
        self,
        team_id: str,
        user_id: str,
        requested_agent_id: Optional[str] = None,
        intake_channel: str = "WEB_PORTAL",
        session_metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        session_id = session_id or f"SES-{uuid.uuid4().hex[:12].upper()}"
        trace_id = trace_id or uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        expires_at = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + 86400, tz=timezone.utc).isoformat()
        meta_json = json.dumps(session_metadata or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO agent_run_session (
                    session_id, tenant_id, team_id, user_id, requested_agent_id,
                    session_state, intake_channel, trace_id, session_metadata,
                    expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id, "default-tenant", team_id, user_id, requested_agent_id,
                    "session_created", intake_channel, trace_id, meta_json,
                    expires_at, now, now
                )
            )
            conn.commit()

        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_run_session WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("session_metadata"):
                try:
                    data["session_metadata"] = json.loads(data["session_metadata"])
                except Exception:
                    pass
            return data

    def update_session_state(
        self,
        session_id: str,
        session_state: str,
        metadata_update: Optional[Dict[str, Any]] = None,
        requested_agent_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            session = self.get_session(session_id)
            if not session:
                return None

            current_meta = session.get("session_metadata", {})
            if metadata_update:
                current_meta.update(metadata_update)

            query = "UPDATE agent_run_session SET session_state = ?, session_metadata = ?, updated_at = ?"
            params = [session_state, json.dumps(current_meta), now]

            if requested_agent_id:
                query += ", requested_agent_id = ?"
                params.append(requested_agent_id)

            query += " WHERE session_id = ?"
            params.append(session_id)

            cursor.execute(query, tuple(params))
            conn.commit()

        return self.get_session(session_id)

    def list_sessions(
        self,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM agent_run_session WHERE 1=1"
            params = []
            if team_id:
                query += " AND team_id = ?"
                params.append(team_id)
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("session_metadata"):
                    try:
                        item["session_metadata"] = json.loads(item["session_metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results

    # -------------------------------------------------------------------
    # State Transition & Event Append Log
    # -------------------------------------------------------------------

    def _insert_state_transition_raw(
        self,
        cursor,
        transition_id: str,
        run_id: str,
        from_state: str,
        to_state: str,
        reason_code: str,
        actor_id: str,
        actor_type: str = "SYSTEM",
        checkpoint_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        created_at: Optional[str] = None
    ) -> None:
        now = created_at or datetime.now(timezone.utc).isoformat()
        trace_id = trace_id or uuid.uuid4().hex
        cursor.execute(
            """
            INSERT INTO agent_run_state_transition (
                transition_id, run_id, from_state, to_state, reason_code,
                actor_id, actor_type, checkpoint_id, trace_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transition_id, run_id, from_state, to_state, reason_code,
                actor_id, actor_type, checkpoint_id, trace_id, now
            )
        )

    def record_state_transition(
        self,
        run_id: str,
        from_state: str,
        to_state: str,
        reason_code: str,
        actor_id: str,
        actor_type: str = "SYSTEM",
        checkpoint_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        transition_id = f"TRN-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        trace_id = trace_id or uuid.uuid4().hex

        with self._get_connection() as conn:
            cursor = conn.cursor()
            self._insert_state_transition_raw(
                cursor=cursor,
                transition_id=transition_id,
                run_id=run_id,
                from_state=from_state,
                to_state=to_state,
                reason_code=reason_code,
                actor_id=actor_id,
                actor_type=actor_type,
                checkpoint_id=checkpoint_id,
                trace_id=trace_id,
                created_at=now
            )
            conn.commit()

        return {
            "transition_id": transition_id,
            "run_id": run_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason_code": reason_code,
            "created_at": now
        }

    def append_event(
        self,
        event_type: str,
        state: str,
        event_payload: Dict[str, Any],
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        producer_service: str = "platform-orchestrator",
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        trace_id = trace_id or uuid.uuid4().hex
        payload_json = json.dumps(event_payload)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO agent_run_event (
                    event_id, session_id, run_id, event_type, state,
                    event_payload, producer_service, trace_id, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, session_id, run_id, event_type, state,
                    payload_json, producer_service, trace_id, now
                )
            )
            seq_no = cursor.lastrowid
            conn.commit()

        return {
            "event_id": event_id,
            "sequence_no": seq_no,
            "run_id": run_id,
            "session_id": session_id,
            "event_type": event_type,
            "state": state,
            "event_payload": event_payload,
            "occurred_at": now
        }

    def list_events(
        self,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        since_sequence_no: Optional[int] = None,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM agent_run_event WHERE 1=1"
            params = []
            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            if since_sequence_no is not None:
                query += " AND sequence_no > ?"
                params.append(since_sequence_no)

            query += " ORDER BY sequence_no ASC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("event_payload"):
                    try:
                        item["event_payload"] = json.loads(item["event_payload"])
                    except Exception:
                        pass
                results.append(item)
            return results

    # -------------------------------------------------------------------
    # Resolved Workflow & Overlay Snapshots
    # -------------------------------------------------------------------

    def save_resolved_workflow(
        self,
        resolved_workflow_id: str,
        run_id: str,
        workflow_id: str,
        sha256_hash: str,
        workflow_yaml: str,
        policy_snapshot: Dict[str, Any],
        team_config_snapshot: Dict[str, Any],
        step_bindings_map: Dict[str, Any]
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO agent_run_resolved_workflow (
                    resolved_workflow_id, run_id, workflow_id, sha256_hash,
                    workflow_yaml, policy_snapshot, team_config_snapshot,
                    step_bindings_map, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_workflow_id, run_id, workflow_id, sha256_hash,
                    workflow_yaml, json.dumps(policy_snapshot),
                    json.dumps(team_config_snapshot),
                    json.dumps(step_bindings_map), now
                )
            )
            conn.commit()

        return {
            "resolved_workflow_id": resolved_workflow_id,
            "run_id": run_id,
            "workflow_id": workflow_id,
            "sha256_hash": sha256_hash,
            "created_at": now
        }

    def get_resolved_workflow(self, resolved_workflow_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_run_resolved_workflow WHERE resolved_workflow_id = ?", (resolved_workflow_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            for k in ["policy_snapshot", "team_config_snapshot", "step_bindings_map"]:
                if data.get(k):
                    try:
                        data[k] = json.loads(data[k])
                    except Exception:
                        pass
            return data

    def save_overlay(
        self,
        run_id: str,
        overlay_type: str,
        item_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        overlay_id = f"OVL-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO agent_run_overlay (
                    overlay_id, run_id, overlay_type, item_id, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (overlay_id, run_id, overlay_type, item_id, json.dumps(payload), now)
            )
            conn.commit()
        return {"overlay_id": overlay_id, "run_id": run_id, "overlay_type": overlay_type, "item_id": item_id}

    # -------------------------------------------------------------------
    # Approvals & Human Review Records
    # -------------------------------------------------------------------

    def create_approval_request(
        self,
        run_id: str,
        checkpoint_id: str,
        artifact_version_id: str,
        writeback_payload_version_id: str,
        reviewer_user_id: str,
        rework_cycle_count: int = 0,
        expires_in_seconds: int = 86400
    ) -> Dict[str, Any]:
        approval_id = f"APR-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        expires_at = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + expires_in_seconds, tz=timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO approval_request (
                    approval_id, run_id, checkpoint_id, artifact_version_id,
                    writeback_payload_version_id, reviewer_user_id, approval_state,
                    rework_cycle_count, requested_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id, run_id, checkpoint_id, artifact_version_id,
                    writeback_payload_version_id, reviewer_user_id, "PENDING",
                    rework_cycle_count, now, expires_at
                )
            )
            conn.commit()

        return {
            "approval_id": approval_id,
            "run_id": run_id,
            "checkpoint_id": checkpoint_id,
            "approval_state": "PENDING",
            "requested_at": now,
            "expires_at": expires_at
        }

    def record_approval_decision(
        self,
        approval_id: str,
        decision: str,
        decided_by: str,
        reviewed_payload_sha256: str,
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        decision_id = f"DEC-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO approval_decision (
                    decision_id, approval_id, decision, decided_by,
                    reviewed_payload_sha256, comments, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (decision_id, approval_id, decision, decided_by, reviewed_payload_sha256, comments, now)
            )
            cursor.execute(
                "UPDATE approval_request SET approval_state = ? WHERE approval_id = ?",
                (decision.upper(), approval_id)
            )
            conn.commit()

        return {
            "decision_id": decision_id,
            "approval_id": approval_id,
            "decision": decision,
            "decided_by": decided_by,
            "decided_at": now
        }

    def record_approval_feedback(
        self,
        approval_id: str,
        run_id: str,
        rework_cycle_number: int,
        feedback_text: str,
        resume_target_step_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        feedback_id = f"FDB-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO approval_feedback (
                    feedback_id, approval_id, run_id, rework_cycle_number,
                    feedback_text, resume_target_step_id, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id, approval_id, run_id, rework_cycle_number,
                    feedback_text, resume_target_step_id, created_by, now
                )
            )
            conn.commit()

        return {
            "feedback_id": feedback_id,
            "approval_id": approval_id,
            "run_id": run_id,
            "rework_cycle_number": rework_cycle_number,
            "created_at": now
        }

    # -------------------------------------------------------------------
    # Run Lifecycle Methods (agent_run & orchestrator_runs)
    # -------------------------------------------------------------------

    def get_run_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Look up an existing agent run by its idempotency key."""
        if not idempotency_key:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT run_id FROM agent_run WHERE idempotency_key = ?", (idempotency_key,))
            row = cursor.fetchone()
            if row:
                run_id = row["run_id"] if isinstance(row, dict) or hasattr(row, "__getitem__") else row[0]
                return self.get_run(run_id)
            return None

    def create_run(
        self,
        agent_name: str,
        agent_version: str,
        team_id: str,
        policy_version: str,
        input_data: Dict[str, Any],
        timeout_seconds: int = 300,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        resolved_workflow_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if idempotency_key:
            existing = self.get_run_by_idempotency_key(idempotency_key)
            if existing:
                return existing

        run_id = run_id or f"RUN-{uuid.uuid4().hex[:8].upper()}"
        user_id = user_id or "usr-architect-01"
        trace_id = trace_id or uuid.uuid4().hex
        resolved_workflow_id = resolved_workflow_id or f"rwf_{agent_name}_{uuid.uuid4().hex[:8]}"
        idempotency_key = idempotency_key or f"idemp_{run_id}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert into canonical agent_run
            cursor.execute(
                """
                INSERT INTO agent_run (
                    run_id, session_id, tenant_id, team_id, initiating_user_id,
                    agent_id, agent_version, workflow_id, workflow_version,
                    resolved_workflow_id, run_state, pause_reason, current_checkpoint_id,
                    total_cost_usd, total_tokens, idempotency_key, trace_id,
                    input_data, output_data, error_message, retry_count,
                    rework_cycle_count, validation_attempt_count, timeout_seconds,
                    queued_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, session_id, "default-tenant", team_id, user_id,
                    agent_name, agent_version, agent_name, agent_version,
                    resolved_workflow_id, "queued", None, None,
                    0.0, 0, idempotency_key, trace_id,
                    json.dumps(input_data), None, None, 0,
                    0, 0, timeout_seconds,
                    now, None, None
                )
            )

            # Insert into legacy orchestrator_runs table for backwards compatibility
            cursor.execute(
                """
                INSERT OR REPLACE INTO orchestrator_runs (
                    run_id, agent_name, agent_version, policy_version,
                    team_id, status, current_checkpoint_id, input_data,
                    output_data, error_message, retry_count, timeout_seconds,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, agent_name, agent_version, policy_version,
                    team_id, "QUEUED", None, json.dumps(input_data),
                    None, None, 0, timeout_seconds, now, now
                )
            )

            # Record initial state transition
            self._insert_state_transition_raw(
                cursor=cursor,
                transition_id=f"TRN-{uuid.uuid4().hex[:12].upper()}",
                run_id=run_id,
                from_state="run_created",
                to_state="queued",
                reason_code="WORKFLOW_ENQUEUED",
                actor_id=user_id,
                actor_type="SYSTEM",
                trace_id=trace_id,
                created_at=now
            )

            # Record initial audit event
            self._insert_audit_event_raw(
                cursor,
                audit_id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                event_type="RUN_CREATED",
                actor_type="PLATFORM_SYSTEM",
                actor_id=team_id,
                actor_name="Platform Orchestrator",
                details=json.dumps({"agent": f"{agent_name}:{agent_version}", "policy": policy_version}),
                timestamp=now
            )
            conn.commit()

        return self.get_run(run_id)

    @staticmethod
    def _map_state_to_macro_status(run_state: Optional[str]) -> str:
        if not run_state:
            return "QUEUED"
        mapping = {
            "queued": "QUEUED",
            "running": "RUNNING",
            "step_running": "RUNNING",
            "paused_for_validation": "WAITING_FOR_CLARIFICATION",
            "awaiting_clarification": "WAITING_FOR_CLARIFICATION",
            "waiting_for_clarification": "WAITING_FOR_CLARIFICATION",
            "awaiting_approval": "WAITING_FOR_APPROVAL",
            "waiting_for_approval": "WAITING_FOR_APPROVAL",
            "completed": "COMPLETED",
            "failed": "FAILED",
            "cancelled": "CANCELLED",
            "rejected": "REJECTED",
            "dead_lettered": "DEAD_LETTERED"
        }
        return mapping.get(run_state.lower(), run_state.upper())

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Prefer agent_run
            cursor.execute("SELECT * FROM agent_run WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["agent_name"] = data.get("agent_id")
                data["run_state"] = data.get("run_state", "queued")
                data["status"] = self._map_state_to_macro_status(data["run_state"])
                data["policy_version"] = "2026.Q3"
                data["created_at"] = data.get("queued_at")
                data["updated_at"] = data.get("completed_at") or data.get("started_at") or data.get("queued_at")
                if data.get("input_data"):
                    try:
                        data["input_data"] = json.loads(data["input_data"])
                    except Exception:
                        pass
                if data.get("output_data"):
                    try:
                        data["output_data"] = json.loads(data["output_data"])
                    except Exception:
                        pass
                return data

            # Fallback to legacy orchestrator_runs
            cursor.execute("SELECT * FROM orchestrator_runs WHERE run_id = ?", (run_id,))
            legacy_row = cursor.fetchone()
            if not legacy_row:
                return None
            ldata = dict(legacy_row)
            ldata["status"] = self._map_state_to_macro_status(ldata.get("status"))
            if ldata.get("input_data"):
                try:
                    ldata["input_data"] = json.loads(ldata["input_data"])
                except Exception:
                    pass
            if ldata.get("output_data"):
                try:
                    ldata["output_data"] = json.loads(ldata["output_data"])
                except Exception:
                    pass
            return ldata

    def list_runs(
        self,
        team_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM agent_run WHERE 1=1"
            params: List[Any] = []

            if team_id:
                query += " AND team_id = ?"
                params.append(team_id)
            if status:
                query += " AND (run_state = ? OR run_state = ?)"
                params.append(status.lower())
                params.append(status.upper())

            query += " ORDER BY queued_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["agent_name"] = item.get("agent_id")
                item["run_state"] = item.get("run_state", "queued")
                item["status"] = self._map_state_to_macro_status(item["run_state"])
                item["policy_version"] = "2026.Q3"
                item["created_at"] = item.get("queued_at")
                item["updated_at"] = item.get("completed_at") or item.get("started_at") or item.get("queued_at")
                if item.get("input_data"):
                    try:
                        item["input_data"] = json.loads(item["input_data"])
                    except Exception:
                        pass
                if item.get("output_data"):
                    try:
                        item["output_data"] = json.loads(item["output_data"])
                    except Exception:
                        pass
                results.append(item)
            return results

    def update_run_status(
        self,
        run_id: str,
        status: str,
        current_checkpoint_id: Optional[str] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        increment_retry: bool = False,
        increment_rework: bool = False,
        increment_validation: bool = False,
        pause_reason: Optional[str] = None,
        cost_delta: float = 0.0,
        tokens_delta: int = 0
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        state_canonical = status.lower()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Update canonical agent_run
            query = "UPDATE agent_run SET run_state = ?"
            params = [state_canonical]

            if current_checkpoint_id is not None:
                query += ", current_checkpoint_id = ?"
                params.append(current_checkpoint_id)
            if pause_reason is not None:
                query += ", pause_reason = ?"
                params.append(pause_reason)
            if output_data is not None:
                query += ", output_data = ?"
                params.append(json.dumps(output_data))
            if error_message is not None:
                query += ", error_message = ?"
                params.append(error_message)
            if increment_retry:
                query += ", retry_count = retry_count + 1"
            if increment_rework:
                query += ", rework_cycle_count = rework_cycle_count + 1"
            if increment_validation:
                query += ", validation_attempt_count = validation_attempt_count + 1"
            if cost_delta > 0:
                query += f", total_cost_usd = total_cost_usd + {cost_delta}"
            if tokens_delta > 0:
                query += f", total_tokens = total_tokens + {tokens_delta}"
            if state_canonical in ["running", "step_running"]:
                query += ", started_at = COALESCE(started_at, ?)"
                params.append(now)
            if state_canonical in ["completed", "failed", "rejected", "cancelled", "dead_lettered"]:
                query += ", completed_at = ?"
                params.append(now)

            query += " WHERE run_id = ?"
            params.append(run_id)
            cursor.execute(query, tuple(params))

            # Update legacy orchestrator_runs
            cursor.execute(
                """
                UPDATE orchestrator_runs
                SET status = ?, current_checkpoint_id = COALESCE(?, current_checkpoint_id),
                    output_data = COALESCE(?, output_data), error_message = COALESCE(?, error_message),
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    status.upper(), current_checkpoint_id,
                    json.dumps(output_data) if output_data else None,
                    error_message, now, run_id
                )
            )

            # Record state transition
            self._insert_state_transition_raw(
                cursor=cursor,
                transition_id=f"TRN-{uuid.uuid4().hex[:12].upper()}",
                run_id=run_id,
                from_state="unknown",
                to_state=state_canonical,
                reason_code=f"TRANSITION_TO_{state_canonical.upper()}",
                actor_id="platform-orchestrator",
                actor_type="SYSTEM",
                checkpoint_id=current_checkpoint_id,
                created_at=now
            )

            conn.commit()

        return self.get_run(run_id)

    # -------------------------------------------------------------------
    # Checkpoint Methods
    # -------------------------------------------------------------------

    def save_checkpoint(
        self,
        run_id: str,
        checkpoint_id: str,
        step_name: str,
        node_name: str,
        checkpoint_type: str,
        state_snapshot: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        state_json = json.dumps(state_snapshot)
        meta_json = json.dumps(metadata or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO orchestrator_checkpoints (
                    run_id, checkpoint_id, step_name, node_name,
                    checkpoint_type, state_snapshot, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, checkpoint_id, step_name, node_name,
                    checkpoint_type, state_json, meta_json, now
                )
            )
            cursor.execute(
                "UPDATE agent_run SET current_checkpoint_id = ? WHERE run_id = ?",
                (checkpoint_id, run_id)
            )
            cursor.execute(
                "UPDATE orchestrator_runs SET current_checkpoint_id = ?, updated_at = ? WHERE run_id = ?",
                (checkpoint_id, now, run_id)
            )
            conn.commit()

        return {
            "run_id": run_id,
            "checkpoint_id": checkpoint_id,
            "step_name": step_name,
            "node_name": node_name,
            "checkpoint_type": checkpoint_type,
            "created_at": now
        }

    def get_checkpoint(self, run_id: str, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orchestrator_checkpoints WHERE run_id = ? AND checkpoint_id = ?",
                (run_id, checkpoint_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            if item.get("state_snapshot"):
                try:
                    item["state_snapshot"] = json.loads(item["state_snapshot"])
                except Exception:
                    pass
            if item.get("metadata"):
                try:
                    item["metadata"] = json.loads(item["metadata"])
                except Exception:
                    pass
            return item

    def list_checkpoints(self, run_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orchestrator_checkpoints WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,)
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("state_snapshot"):
                    try:
                        item["state_snapshot"] = json.loads(item["state_snapshot"])
                    except Exception:
                        pass
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results

    # -------------------------------------------------------------------
    # Task Queue Methods
    # -------------------------------------------------------------------

    def enqueue_task(
        self,
        run_id: str,
        action: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO orchestrator_task_queue (
                    task_id, run_id, action, payload, status, retry_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, run_id, action, payload_json, "PENDING", 0, now, now)
            )
            conn.commit()

        return {
            "task_id": task_id,
            "run_id": run_id,
            "action": action,
            "status": "PENDING",
            "created_at": now
        }

    def update_task_status(
        self,
        task_id: str,
        status: str,
        increment_retry: bool = False
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "UPDATE orchestrator_task_queue SET status = ?, updated_at = ?"
            params = [status, now]
            if increment_retry:
                query += ", retry_count = retry_count + 1"
            query += " WHERE task_id = ?"
            params.append(task_id)
            cursor.execute(query, tuple(params))
            conn.commit()

    # -------------------------------------------------------------------
    # Telemetry Spans & Logs
    # -------------------------------------------------------------------

    def record_span(
        self,
        span_id: str,
        trace_id: str,
        name: str,
        run_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        status_code: str = "OK",
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        attr_json = json.dumps(attributes or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO orchestrator_telemetry_spans (
                    span_id, trace_id, parent_span_id, run_id, name,
                    start_time, end_time, duration_ms, status_code, attributes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    span_id, trace_id, parent_span_id, run_id, name,
                    now, now, duration_ms or 0.0, status_code, attr_json, now
                )
            )
            conn.commit()

    def list_spans(
        self,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM orchestrator_telemetry_spans WHERE 1=1"
            params: List[Any] = []
            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)
            if trace_id:
                query += " AND trace_id = ?"
                params.append(trace_id)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("attributes"):
                    try:
                        item["attributes"] = json.loads(item["attributes"])
                    except Exception:
                        pass
                results.append(item)
            return results

    def record_log(
        self,
        level: str,
        component: str,
        message: str,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        log_id = f"LOG-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        attr_json = json.dumps(attributes or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO orchestrator_telemetry_logs (
                    log_id, timestamp, run_id, trace_id, span_id, level, component, message, attributes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (log_id, now, run_id, trace_id, span_id, level, component, message, attr_json)
            )
            conn.commit()

    def list_logs(
        self,
        run_id: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM orchestrator_telemetry_logs WHERE 1=1"
            params: List[Any] = []
            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)
            if level:
                query += " AND level = ?"
                params.append(level)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("attributes"):
                    try:
                        item["attributes"] = json.loads(item["attributes"])
                    except Exception:
                        pass
                results.append(item)
            return results

    # -------------------------------------------------------------------
    # Audit Events Methods
    # -------------------------------------------------------------------

    def _insert_audit_event_raw(
        self,
        cursor: sqlite3.Cursor,
        audit_id: str,
        run_id: str,
        event_type: str,
        actor_type: str,
        actor_id: Optional[str],
        actor_name: Optional[str],
        details: str,
        timestamp: str
    ) -> None:
        cursor.execute(
            """
            INSERT INTO orchestrator_audit_events (
                audit_id, run_id, event_type, actor_type, actor_id, actor_name, details, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (audit_id, run_id, event_type, actor_type, actor_id, actor_name, details, timestamp)
        )

    def record_audit_event(
        self,
        run_id: str,
        event_type: str,
        actor_type: str = "USER",
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        detail_json = json.dumps(details or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            self._insert_audit_event_raw(
                cursor, audit_id, run_id, event_type, actor_type, actor_id, actor_name, detail_json, now
            )
            conn.commit()

        return {
            "audit_id": audit_id,
            "run_id": run_id,
            "event_type": event_type,
            "actor_type": actor_type,
            "actor_name": actor_name,
            "timestamp": now
        }

    def list_audit_events(
        self,
        run_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM orchestrator_audit_events WHERE 1=1"
            params: List[Any] = []
            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("details"):
                    try:
                        item["details"] = json.loads(item["details"])
                    except Exception:
                        pass
                results.append(item)
            return results

    # -------------------------------------------------------------------
    # Database Summary & Diagnostic Stats
    # -------------------------------------------------------------------

    def get_database_summary(self) -> Dict[str, Any]:
        """Returns row counts and health stats across all tables."""
        tables = [
            "agent_run_session",
            "agent_run",
            "agent_run_resolved_workflow",
            "agent_run_overlay",
            "agent_run_state_transition",
            "agent_run_event",
            "orchestrator_runs",
            "orchestrator_checkpoints",
            "approval_request",
            "approval_decision",
            "approval_feedback",
            "orchestrator_task_queue",
            "orchestrator_telemetry_spans",
            "orchestrator_telemetry_logs",
            "orchestrator_telemetry_metrics",
            "orchestrator_audit_events"
        ]
        counts = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for t in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {t}")
                    counts[t] = cursor.fetchone()[0]
                except Exception:
                    counts[t] = 0

        return {
            "database_type": settings.db_type,
            "database_path": str(self.db_path),
            "status": "ready",
            "table_counts": counts
        }
