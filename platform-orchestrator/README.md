# Platform Orchestrator Service (AI-DLC / MTech Apex)

The **Platform Orchestrator Service** is the enterprise control plane for the **AI-DLC / MTech Apex Platform**. In adherence with the core platform invariant:

> **The Platform Orchestrator manages runs; the Agent Worker manages the agent graph.**

---

## 1. Architectural Role & Responsibilities

| Responsibility | Implementation Details |
| :--- | :--- |
| **Run Creation & Locking** | Generates unique Run IDs (`RUN-xxxx`), locks workflow/agent version (e.g. `qe_test_case_generation_agent:v1.0`), and captures policy snapshots. |
| **Execution Queueing** | Queues workflow execution tasks and dispatches to Agent Workers via asynchronous task queue / REST dispatch. |
| **Lifecycle & Status Tracking** | Tracks macro status transitions: `QUEUED` → `RUNNING` → `WAITING_FOR_CLARIFICATION` / `WAITING_FOR_APPROVAL` → `COMPLETED` / `FAILED` / `CANCELLED`. |
| **Human-in-the-Loop (HITL)** | Manages durable clarification cycles (missing requirements) and human approval gates (review packages). |
| **Durable Resumption** | Resumes runs from designated checkpoints (`Resume RUN-xxxx from checkpoint CP-xx`) across worker instances. |
| **Platform Policies** | Enforces execution timeouts, automatic retries with exponential backoff, and graceful cancellations. |
| **UI Real-Time Streams** | Provides live status and event streams to UI portals via Server-Sent Events (SSE). |
| **Observability & Telemetry** | Emits OpenTelemetry distributed traces (`trace_id`, `span_id`), execution metrics (run counters, duration histograms), and structured audit logs. |

---

## 2. Recommended Execution Pattern

```
Platform Core
    ↓ Create run (POST /api/orchestrator/runs)
Platform Orchestrator
    ↓ Dispatch workflow (via Cloud Tasks / REST)
Agent Worker (Runs in agent-worker/)
    ├── Step 1: Understand request & validate input
    ├── Step 2: Retrieve context & bind skills
    ├── Step 3: Generate output
    ├── Step 4: Review quality
    └── Step 5: Prepare result & persist checkpoint
```

---

## 3. API Endpoints

### Run Management
- `POST /api/orchestrator/runs`: Create a new workflow run, lock versions, and dispatch worker.
- `GET /api/orchestrator/runs`: List workflow runs filtered by team or status.
- `GET /api/orchestrator/runs/{run_id}`: Retrieve detailed run metadata, active checkpoint, and output.
- `POST /api/orchestrator/runs/{run_id}/cancel`: Request run cancellation.

### Human-in-the-Loop & Checkpoints
- `GET /api/orchestrator/runs/{run_id}/checkpoints`: List all saved checkpoints (`CP-01`, `CP-05`).
- `POST /api/orchestrator/runs/{run_id}/clarify`: Provide missing information for runs in `WAITING_FOR_CLARIFICATION`.
- `POST /api/orchestrator/runs/{run_id}/approve`: Submit review decision (`approve` or `request_changes`) for runs in `WAITING_FOR_APPROVAL`.
- `POST /api/orchestrator/runs/{run_id}/resume`: Generic checkpoint resumption.

### Observability, Telemetry & Audit
- `GET /api/orchestrator/metrics`: OpenTelemetry operational metrics (run totals, status distributions, latency).
- `GET /api/orchestrator/telemetry/database`: Database schema health and table row count summary.
- `GET /api/orchestrator/telemetry/spans`: Distributed trace spans with durations and status codes.
- `GET /api/orchestrator/telemetry/logs`: Correlated structured execution logs.
- `GET /api/orchestrator/telemetry/audit`: Governance and Human-in-the-Loop audit events.
- `GET /health`: Health and readiness probe.

---

## 4. Durable Database Schema (SQLite / Cloud SQL)

The service maintains a relational database (`orchestrator_local.db` or Cloud SQL) across 8 core domains:

| Table Name | Primary Key | Purpose & Captured Fields |
| :--- | :--- | :--- |
| `orchestrator_runs` | `run_id` | Macro run state, locked agent version (`v1.0`), policy version (`2026.Q3`), team ID, input/output JSON, status, completed timestamp. |
| `orchestrator_checkpoints` | `(run_id, checkpoint_id)` | Durable state machine checkpoints (`CP-01`, `CP-05`, `CP-FINAL`), step names, serialized state snapshot, metadata. |
| `orchestrator_task_queue` | `task_id` | Cloud Tasks queue simulation, action payload, status (`PENDING`, `DISPATCHED`), retry counts. |
| `orchestrator_telemetry_spans` | `span_id` | OpenTelemetry distributed trace spans, W3C `trace_id`, parent span, start/end times, duration (ms), status code, attributes. |
| `orchestrator_telemetry_logs` | `log_id` | Correlated structured JSON logs (`INFO`, `WARN`, `ERROR`), trace/span ID, run ID, component, message, attributes. |
| `orchestrator_telemetry_metrics` | `metric_id` | Time-series and point-in-time metrics (`orchestrator_runs_total`, latency), type, labels, timestamp. |
| `orchestrator_audit_events` | `audit_id` | Compliance & HITL audit trail (e.g. `RUN_CREATED`, `CHECKPOINT_SAVED`, `STATUS_WAITING_FOR_APPROVAL`, `STATUS_COMPLETED`), actor ID, actor name, timestamp. |
| `orchestrator_policy_snapshots` | `policy_id` | Immutable governance rules, policy versions, team entitlements, locked timeout policies. |

---

## 5. Quickstart & Service Execution

### Initialize the Database
```powershell
python init_db.py
```

### Start the Platform Orchestrator (Port 8001)
```powershell
python run.py
# Or directly via uvicorn:
# uvicorn src.main:app --port 8001 --reload
```

### Start the Agent Worker (Port 8002) in a separate terminal
```powershell
cd ..\agent-worker
python run.py
```

### Test API via PowerShell
```powershell
# Using PowerShell Invoke-RestMethod:
Invoke-RestMethod -Uri "http://localhost:8001/api/orchestrator/metrics"
Invoke-RestMethod -Uri "http://localhost:8001/api/orchestrator/telemetry/database"

# Or using real curl (curl.exe in PowerShell):
curl.exe "http://localhost:8001/api/orchestrator/metrics"
```

## 6. Running Test Suites

```bash
# Run orchestrator test suite
python -m unittest tests/test_orchestrator.py

# Run worker test suite
cd ../agent-worker
python -m unittest tests/test_worker.py
```
