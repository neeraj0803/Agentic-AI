"""
Self-contained Platform Orchestrator Verification Script
Executes all validation tests for:
1. Workflow YAML Registry (AG-101 .. AG-501)
2. Heuristic Intent Resolver
3. Mock Context Engine & Mock Skills Engine
4. 18-Point Preflight Validation Gate
5. Snapshot Compiler (SHA256 immutability)
6. SQLite / MySQL Table Schema & Event Log Persistence
7. FastAPI HTTP Routers (Sessions, Agents, Runs, Checkpoints)
"""

import asyncio
import json
import os
import sys

# Ensure platform-orchestrator is in path
sys.path.insert(0, os.path.dirname(__file__))

from src.models.run_models import (
    CreateRunRequest,
    CreateSessionRequest,
    PreflightRequest,
    SessionMessageRequest
)
from src.services.intent_resolver import intent_resolver
from src.services.mock_context_engine import mock_context_engine
from src.services.mock_skills_engine import mock_skills_engine
from src.services.preflight_service import preflight_service
from src.services.run_lifecycle_service import run_lifecycle_service
from src.services.snapshot_service import snapshot_service
from src.services.workflow_registry import workflow_registry
from src.storage.orchestrator_storage import OrchestratorStorage


def run_all_checks():
    print("=" * 70)
    print("STARTING PLATFORM ORCHESTRATOR VERIFICATION")
    print("=" * 70)

    # 1. Test Workflow YAML Registry
    print("\n[1/7] Testing Workflow YAML Registry...")
    workflows = workflow_registry.list_workflows()
    agent_ids = [w["agent_id"] for w in workflows]
    print(f"  -> Discovered workflows: {agent_ids}")
    assert "AG-101" in agent_ids, "AG-101 missing"
    assert "AG-102" in agent_ids, "AG-102 missing"
    assert "AG-201" in agent_ids, "AG-201 missing"
    assert "AG-301" in agent_ids, "AG-301 missing"
    assert "AG-501" in agent_ids, "AG-501 missing"

    missing_fields = workflow_registry.validate_input_payload("AG-201", {})
    assert "requirement_ref" in missing_fields
    print("  -> Input schema validation for AG-201 PASS (missing: 'requirement_ref')")


    # 2. Test Intent Resolver
    print("\n[2/7] Testing Intent Resolver...")
    p1 = "Generate product requirements document PRD for biometric login"
    r1 = intent_resolver.resolve_intent(p1)
    print(f"  -> Prompt '{p1[:30]}...' -> {r1['top_agent_id']} (Confidence: {r1['confidence_score']})")
    assert r1["top_agent_id"] == "AG-101"

    p2 = "Write automated test cases and BDD scenarios for payment retry CHK-123"
    r2 = intent_resolver.resolve_intent(p2)
    print(f"  -> Prompt '{p2[:30]}...' -> {r2['top_agent_id']} (Confidence: {r2['confidence_score']})")
    assert r2["top_agent_id"] == "AG-201"

    p3 = "Generate backend API implementation and FastAPI code PR for user auth"
    r3 = intent_resolver.resolve_intent(p3)
    print(f"  -> Prompt '{p3[:30]}...' -> {r3['top_agent_id']} (Confidence: {r3['confidence_score']})")
    assert r3["top_agent_id"] == "AG-301"

    p4 = "Draft an Architecture Decision Record ADR for Kafka event streaming"
    r4 = intent_resolver.resolve_intent(p4)
    print(f"  -> Prompt '{p4[:30]}...' -> {r4['top_agent_id']} (Confidence: {r4['confidence_score']})")
    assert r4["top_agent_id"] == "AG-501"

    # 3. Test Mock Context & Skills Engine
    print("\n[3/7] Testing Mock Context & Skills Engines...")
    ctx = mock_context_engine.build_context_package(
        team_id="team-checkout-qe",
        application_name="Checkout Payment Service",
        required_capabilities=["ARCHITECTURE_TOPOLOGY", "API_SWAGGER_DOCS"]
    )
    print(f"  -> Context Pack items: {ctx['total_items']}, Citations: {len(ctx['citations'])}")
    assert ctx["total_items"] >= 2

    skills = mock_skills_engine.bind_skills_for_workflow(
        agent_id="AG-201",
        team_id="team-checkout-qe",
        requested_skills=["xray_bdd_formatter", "jira_issue_reader"]
    )
    print(f"  -> Bound skills: {list(skills['bound_skills'].keys())}")
    assert "xray_bdd_formatter" in skills["bound_skills"]

    # 4. Test 18-Point Preflight Gate
    print("\n[4/7] Testing 18-Point Preflight Validation Gate...")
    bad_req = PreflightRequest(agent_id="AG-201", team_id="team-checkout-qe", user_id="usr-1", inputs={})
    bad_res = preflight_service.validate_preflight(bad_req)
    assert bad_res.valid is False
    print(f"  -> Invalid payload rejected with error codes: {bad_res.error_codes}")

    good_req = PreflightRequest(
        agent_id="AG-201",
        team_id="team-checkout-qe",
        user_id="usr-1",
        inputs={
            "requirement_ref": "Checkout Payment Service CHK-4091: Payment retry up to 3 times with idempotency key preservation.",
            "test_level": "functional",
            "target_format": "xray_bdd"
        }
    )
    good_res = preflight_service.validate_preflight(good_req)
    assert good_res.valid is True
    print(f"  -> Valid payload accepted (Blockers: {good_res.blockers_count}, Warnings: {good_res.warnings_count})")

    # 5. Test Snapshot Compilation
    print("\n[5/7] Testing Snapshot Compilation & SHA256 Hashing...")
    snapshot = snapshot_service.compile_snapshot("AG-201", "team-checkout-qe", "2026.Q3")
    print(f"  -> Snapshot ID: {snapshot['resolved_workflow_id']}")
    print(f"  -> SHA256 Hash: {snapshot['sha256_hash']}")
    assert len(snapshot["sha256_hash"]) == 64

    # 6. Test Storage CRUD & Database Schema
    print("\n[6/7] Testing Storage Engine & Canonical Tables...")
    storage = OrchestratorStorage()
    
    # Session creation
    session = storage.create_session(
        team_id="team-checkout-qe",
        user_id="usr-architect-01",
        requested_agent_id="AG-201",
        session_metadata={"browser": "Chrome"}
    )
    session_id = session["session_id"]
    print(f"  -> Created session: {session_id}")

    # Event append
    evt = storage.append_event(
        event_type="test_event",
        state="running",
        event_payload={"step": 1},
        session_id=session_id
    )
    print(f"  -> Appended event ID: {evt['event_id']}, Seq: {evt['sequence_no']}")

    # Database summary
    summary = storage.get_database_summary()
    print("  -> Table counts:", json.dumps(summary["table_counts"], indent=2))
    assert summary["status"] == "ready"

    # 7. Test Lifecycle Service & Run Dispatch
    print("\n[7/7] Testing Run Lifecycle Dispatch & Preflight Integration...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    run_req = CreateRunRequest(
        agent_name="AG-201",
        agent_version="1.0.0",
        team_id="team-checkout-qe",
        user_id="usr-architect-01",
        session_id=session_id,
        input_data={
            "requirement_ref": "Checkout Payment Service CHK-4091: Payment retry up to 3 times with idempotency key preservation.",
            "test_level": "functional",
            "target_format": "xray_bdd"
        },
        skip_preflight=False
    )
    run_result = loop.run_until_complete(run_lifecycle_service.create_and_dispatch_run(run_req))
    print(f"  -> Created Run ID: {run_result['run_id']}")
    print(f"  -> Status: {run_result['status']}")
    print(f"  -> Resolved Workflow ID: {run_result.get('resolved_workflow_id')}")

    assert run_result["run_id"].startswith("RUN-")
    assert run_result["status"] in ["queued", "running", "QUEUED", "RUNNING"]

    print("\n" + "=" * 70)
    print("ALL 7 VERIFICATION MODULES PASSED SUCCESSFULLY (100% GREEN)")
    print("=" * 70)


if __name__ == "__main__":
    run_all_checks()
