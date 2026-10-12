-- ==============================================================================
-- Enterprise MySQL 8.0+ Schema for Platform Orchestrator
-- Character Set: utf8mb4 | Collation: utf8mb4_unicode_ci | Engine: InnoDB
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS agentic_orchestrator
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE agentic_orchestrator;

-- ------------------------------------------------------------------------------
-- 1. Conversational Intake & Sessions
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_run_session (
    session_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default-tenant',
    team_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    requested_agent_id VARCHAR(32) NULL,
    session_state VARCHAR(32) NOT NULL DEFAULT 'session_created',
    intake_channel VARCHAR(32) NOT NULL DEFAULT 'WEB_PORTAL',
    trace_id VARCHAR(64) NOT NULL,
    session_metadata JSON NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_session_user (user_id, session_state),
    INDEX idx_session_team (team_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 2. Authoritative Macro Execution Runs
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_run (
    run_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NULL,
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default-tenant',
    team_id VARCHAR(64) NOT NULL,
    initiating_user_id VARCHAR(64) NOT NULL,
    agent_id VARCHAR(32) NOT NULL,
    agent_version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
    workflow_id VARCHAR(64) NOT NULL,
    workflow_version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
    resolved_workflow_id VARCHAR(64) NOT NULL,
    run_state VARCHAR(32) NOT NULL DEFAULT 'run_created',
    pause_reason VARCHAR(64) NULL,
    current_checkpoint_id VARCHAR(64) NULL,
    total_cost_usd DECIMAL(10, 4) NOT NULL DEFAULT 0.0000,
    total_tokens INT NOT NULL DEFAULT 0,
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    trace_id VARCHAR(64) NOT NULL,
    input_data JSON NOT NULL,
    output_data JSON NULL,
    error_message TEXT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    rework_cycle_count INT NOT NULL DEFAULT 0,
    validation_attempt_count INT NOT NULL DEFAULT 0,
    timeout_seconds INT NOT NULL DEFAULT 300,
    queued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    INDEX idx_run_team_state (team_id, run_state),
    INDEX idx_run_user (initiating_user_id, queued_at),
    CONSTRAINT fk_run_session FOREIGN KEY (session_id) REFERENCES agent_run_session(session_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 3. Immutable Resolved Workflow Snapshot
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_run_resolved_workflow (
    resolved_workflow_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    workflow_id VARCHAR(64) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    workflow_yaml MEDIUMTEXT NOT NULL,
    policy_snapshot JSON NOT NULL,
    team_config_snapshot JSON NOT NULL,
    step_bindings_map JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_resolved_wf_run (run_id),
    CONSTRAINT fk_resolved_wf_run FOREIGN KEY (run_id) REFERENCES agent_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 4. Runtime Overlays (Context, Skills, Validation)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_run_overlay (
    overlay_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    overlay_type VARCHAR(32) NOT NULL, -- 'CONTEXT', 'SKILL', 'VALIDATION', 'FEEDBACK'
    item_id VARCHAR(64) NOT NULL,
    payload JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_overlay_run (run_id),
    CONSTRAINT fk_overlay_run FOREIGN KEY (run_id) REFERENCES agent_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 5. Macro State Transition Ledger
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_run_state_transition (
    transition_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    from_state VARCHAR(32) NOT NULL,
    to_state VARCHAR(32) NOT NULL,
    reason_code VARCHAR(64) NOT NULL,
    actor_id VARCHAR(64) NOT NULL,
    actor_type VARCHAR(32) NOT NULL DEFAULT 'SYSTEM',
    checkpoint_id VARCHAR(64) NULL,
    trace_id VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_transition_run (run_id, created_at),
    CONSTRAINT fk_transition_run FOREIGN KEY (run_id) REFERENCES agent_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 6. Append-Only Event Store (SSE & Replay)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_run_event (
    event_id VARCHAR(64) PRIMARY KEY,
    sequence_no BIGINT NOT NULL AUTO_INCREMENT,
    session_id VARCHAR(64) NULL,
    run_id VARCHAR(64) NULL,
    event_type VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    event_payload JSON NOT NULL,
    producer_service VARCHAR(32) NOT NULL DEFAULT 'platform-orchestrator',
    trace_id VARCHAR(64) NOT NULL,
    occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_event_seq (sequence_no),
    INDEX idx_event_run_seq (run_id, sequence_no),
    INDEX idx_event_session_seq (session_id, sequence_no)
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 7. Durable Human-in-the-Loop Checkpoints
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orchestrator_checkpoints (
    run_id VARCHAR(64) NOT NULL,
    checkpoint_id VARCHAR(64) NOT NULL,
    step_name VARCHAR(64) NOT NULL,
    node_name VARCHAR(64) NOT NULL,
    checkpoint_type VARCHAR(32) NOT NULL,
    state_snapshot MEDIUMTEXT NOT NULL,
    metadata JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, checkpoint_id),
    CONSTRAINT fk_cp_run FOREIGN KEY (run_id) REFERENCES agent_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 8. Approvals & Human Review Packages
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approval_request (
    approval_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    checkpoint_id VARCHAR(64) NOT NULL,
    artifact_version_id VARCHAR(64) NOT NULL,
    writeback_payload_version_id VARCHAR(64) NOT NULL,
    reviewer_user_id VARCHAR(64) NOT NULL,
    approval_state VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    rework_cycle_count INT NOT NULL DEFAULT 0,
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    INDEX idx_approval_run (run_id),
    CONSTRAINT fk_approval_run FOREIGN KEY (run_id) REFERENCES agent_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS approval_decision (
    decision_id VARCHAR(64) PRIMARY KEY,
    approval_id VARCHAR(64) NOT NULL,
    decision VARCHAR(32) NOT NULL, -- 'APPROVE', 'REQUEST_CHANGES', 'REJECT', 'CANCEL'
    decided_by VARCHAR(64) NOT NULL,
    reviewed_payload_sha256 VARCHAR(64) NOT NULL,
    comments TEXT NULL,
    decided_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_decision_approval FOREIGN KEY (approval_id) REFERENCES approval_request(approval_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS approval_feedback (
    feedback_id VARCHAR(64) PRIMARY KEY,
    approval_id VARCHAR(64) NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    rework_cycle_number INT NOT NULL,
    feedback_text TEXT NOT NULL,
    resume_target_step_id VARCHAR(64) NOT NULL,
    created_by VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_feedback_approval FOREIGN KEY (approval_id) REFERENCES approval_request(approval_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------------------------
-- 9. Idempotency Reservations
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS idempotency_key (
    idempotency_key_id VARCHAR(64) PRIMARY KEY,
    scope VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    request_fingerprint_sha256 VARCHAR(64) NOT NULL,
    result_reference_id VARCHAR(64) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'IN_PROGRESS',
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_scope_key (scope, idempotency_key)
) ENGINE=InnoDB;

