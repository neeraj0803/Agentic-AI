# Agent Worker Service (AI-DLC / MTech Apex)

The **Agent Worker Service** is the execution engine for the **AI-DLC / MTech Apex Platform**.

> **The Platform Orchestrator manages runs; the Agent Worker manages the agent graph.**

---

## 1. Architectural Role & Invariants

- **Continuous Processing Window**: The worker executes internal graph nodes in a single processing window without orchestrator-per-node dispatch.
- **Durable Boundaries**: The worker pauses and saves checkpoints only at defined boundaries:
  - `CP-01`: User clarification required (missing mandatory acceptance criteria).
  - `CP-05`: Human approval required (review package ready for review).
  - `CP-FINAL`: Completion and writeback.
- **Stateless Resumption**: Workers load checkpoint state snapshots without requiring pod affinity.

---

## 2. Five-Step Continuous Execution Pattern

```
Agent Worker
  ├── Step 1: Understand request & validate input (yields CP-01 if AC missing)
  ├── Step 2: Retrieve context & dynamically bind skills
  ├── Step 3: Generate candidate test scenarios (positive, negative, boundary)
  ├── Step 4: Review quality, check duplicates, & assemble review package (yields CP-05)
  └── Step 5: Publish / write back to Xray/Jira upon approval (CP-FINAL)
```

---

## 3. Endpoints

- `POST /worker/dispatch`: Dispatches continuous execution from Step 1.
- `POST /worker/resume`: Resumes execution from a designated checkpoint (`CP-01` or `CP-05`).
- `GET /health`: Readiness & liveness probe.

---

## 4. Local Execution

```bash
# Start Agent Worker (port 8002)
uv run uvicorn src.main:app --port 8002 --reload
```
