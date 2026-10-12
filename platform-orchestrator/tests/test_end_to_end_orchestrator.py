import json
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.intent_resolver import intent_resolver
from src.services.mock_context_engine import mock_context_engine
from src.services.mock_skills_engine import mock_skills_engine
from src.services.preflight_service import preflight_service
from src.services.snapshot_service import snapshot_service
from src.services.workflow_registry import workflow_registry
from src.storage.orchestrator_storage import OrchestratorStorage


client = TestClient(app)


def test_workflow_registry_loading():
    workflows = workflow_registry.list_workflows()
    assert len(workflows) >= 5
    agent_ids = [w["agent_id"] for w in workflows]
    assert "AG-101" in agent_ids
    assert "AG-102" in agent_ids
    assert "AG-201" in agent_ids
    assert "AG-301" in agent_ids
    assert "AG-501" in agent_ids

    # Check input validation for AG-201
    missing = workflow_registry.validate_input_payload("AG-201", {})
    assert "jira_story_id" in missing
    assert "application_name" in missing

    valid_payload = {
        "jira_story_id": "CHK-4091",
        "application_name": "Checkout Service",
        "acceptance_criteria": ["Criteria 1", "Criteria 2"]
    }
    missing_none = workflow_registry.validate_input_payload("AG-201", valid_payload)
    assert len(missing_none) == 0


def test_intent_resolver():
    res_prd = intent_resolver.resolve_intent("Please generate a Product Requirements Document PRD for biometric login")
    assert res_prd["top_agent_id"] == "AG-101"
    assert res_prd["confidence_score"] > 0.5

    res_qe = intent_resolver.resolve_intent("Write automated test cases and BDD scenarios for payment retry CHK-123")
    assert res_qe["top_agent_id"] == "AG-201"
    assert res_qe["confidence_score"] > 0.5

    res_code = intent_resolver.resolve_intent("Generate backend API implementation and FastAPI code PR for user auth")
    assert res_code["top_agent_id"] == "AG-301"

    res_adr = intent_resolver.resolve_intent("Draft an Architecture Decision Record ADR for Kafka event streaming")
    assert res_adr["top_agent_id"] == "AG-501"


def test_mock_context_and_skills_engines():
    # Context Engine
    ctx_pack = mock_context_engine.build_context_package(
        team_id="team-checkout-qe",
        application_name="Checkout Payment Service",
        required_capabilities=["ARCHITECTURE_TOPOLOGY", "API_SWAGGER_DOCS"]
    )
    assert ctx_pack["total_items"] >= 2
    assert len(ctx_pack["citations"]) >= 2

    # Skills Engine
    skills = mock_skills_engine.bind_skills_for_workflow(
        agent_id="AG-201",
        team_id="team-checkout-qe",
        requested_skills=["xray_bdd_formatter", "jira_issue_reader"]
    )
    assert skills["agent_id"] == "AG-201"
    assert len(skills["bound_skills"]) >= 2


def test_preflight_validation_service():
    from src.models.run_models import PreflightRequest

    # 1. Failing preflight (missing inputs)
    bad_req = PreflightRequest(
        agent_id="AG-201",
        team_id="team-checkout-qe",
        user_id="usr-architect-01",
        inputs={}
    )
    bad_res = preflight_service.validate_preflight(bad_req)
    assert bad_res.valid is False
    assert "REQUIRED_INPUT_MISSING" in bad_res.error_codes

    # 2. Passing preflight
    good_req = PreflightRequest(
        agent_id="AG-201",
        team_id="team-checkout-qe",
        user_id="usr-architect-01",
        inputs={
            "jira_story_id": "CHK-4091",
            "application_name": "Checkout Payment Service",
            "acceptance_criteria": ["Criteria 1", "Criteria 2"],
            "target_output_format": "xray_bdd"
        }
    )
    good_res = preflight_service.validate_preflight(good_req)
    assert good_res.valid is True
    assert good_res.blockers_count == 0


def test_snapshot_compilation():
    snapshot = snapshot_service.compile_snapshot(
        workflow_id="AG-201",
        team_id="team-checkout-qe",
        policy_version="2026.Q3"
    )
    assert snapshot["resolved_workflow_id"].startswith("rwf_AG-201_")
    assert len(snapshot["sha256_hash"]) == 64
    assert "workflow_yaml" in snapshot
    assert "step_bindings_map" in snapshot


def test_orchestrator_sessions_api():
    # 1. Create Session
    create_res = client.post("/api/orchestrator/sessions", json={
        "team_id": "team-checkout-qe",
        "user_id": "usr-architect-01",
        "intake_channel": "WEB_PORTAL",
        "session_metadata": {"browser": "Chrome"}
    })
    assert create_res.status_code == 201
    session_data = create_res.json()
    session_id = session_data["session_id"]
    assert session_id.startswith("SES-")

    # 2. Post Chat Message to Session
    msg_res = client.post(f"/api/orchestrator/sessions/{session_id}/messages", json={
        "user_id": "usr-architect-01",
        "message": "Generate test cases for checkout story CHK-4091 on Checkout Service",
        "current_inputs": {
            "jira_story_id": "CHK-4091",
            "application_name": "Checkout Service",
            "acceptance_criteria": ["Retry 3x on 503", "Preserve Idempotency Key"]
        }
    })
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert msg_data["resolved_agent_id"] == "AG-201"
    assert msg_data["is_preflight_ready"] is True

    # 3. Get Session
    get_res = client.get(f"/api/orchestrator/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["session_state"] == "preflight_ready"


def test_orchestrator_agents_api():
    # 1. Catalog discovery
    cat_res = client.get("/api/orchestrator/agents")
    assert cat_res.status_code == 200
    catalog = cat_res.json()
    assert len(catalog) >= 5

    # 2. Get specific agent specification
    ag_res = client.get("/api/orchestrator/agents/AG-201")
    assert ag_res.status_code == 200
    ag_data = ag_res.json()
    assert ag_data["workflow_metadata"]["workflow_id"] == "AG-201"

    # 3. Intent resolution endpoint
    resolve_res = client.post("/api/orchestrator/agents:resolve-intent", json={
        "user_prompt": "I need architecture ADR documentation for database migration"
    })
    assert resolve_res.status_code == 200
    assert resolve_res.json()["top_agent_id"] == "AG-501"

    # 4. Preview Context & Skills
    preview_res = client.get("/api/orchestrator/agents/AG-201/context-and-skills?team_id=team-checkout-qe")
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert "context_package" in preview
    assert "skills_binding" in preview


def test_runs_preflight_and_execution_lifecycle():
    # 1. Create Run with Preflight Validation
    run_payload = {
        "agent_name": "AG-201",
        "agent_version": "1.0.0",
        "team_id": "team-checkout-qe",
        "user_id": "usr-architect-01",
        "input_data": {
            "jira_story_id": "CHK-4091",
            "application_name": "Checkout Payment Service",
            "acceptance_criteria": [
                "Payment transaction must retry up to 3 times on transient network error (HTTP 503)",
                "Preserve idempotency key across retries"
            ],
            "target_output_format": "xray_bdd"
        },
        "skip_preflight": False
    }

    create_res = client.post("/api/orchestrator/runs", json=run_payload)
    assert create_res.status_code == 201
    run_data = create_res.json()
    run_id = run_data["run_id"]
    assert run_id.startswith("RUN-")
    assert run_data["status"] in ["queued", "running", "QUEUED", "RUNNING"]

    # 2. Verify state transitions and resolved workflow snapshot in storage
    storage = OrchestratorStorage()
    resolved_wf = storage.get_resolved_workflow(run_data["resolved_workflow_id"])
    assert resolved_wf is not None
    assert resolved_wf["workflow_id"] == "AG-201"

    # 3. Verify Database Summary
    summary = storage.get_database_summary()
    assert summary["status"] == "ready"
    assert summary["table_counts"]["agent_run"] >= 1
    assert summary["table_counts"]["agent_run_resolved_workflow"] >= 1
    assert summary["table_counts"]["agent_run_state_transition"] >= 1

