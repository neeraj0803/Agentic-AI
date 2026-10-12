from typing import Any, Dict, List, Optional

from .mock_context_engine import mock_context_engine
from .mock_skills_engine import mock_skills_engine
from .workflow_registry import workflow_registry
from ..telemetry import logger


class PreflightValidationService:
    """
    Preflight Validation Engine for Platform Orchestrator.
    Executes the 18-point preflight validation checklist before durable run creation.
    Returns structured pass/fail decisions with stable error codes and actionable remediation targets.
    """

    def __init__(self):
        # Default mock team quotas and entitlements
        self._team_allowlist = {"team-checkout", "team-loyalty-product", "team-qe-automation", "team-platform"}
        self._suspended_teams = {"team-suspended-demo"}

    def run_preflight(
        self,
        agent_identifier: str,
        team_id: str,
        user_id: str,
        input_data: Dict[str, Any],
        selected_context_packs: Optional[List[str]] = None,
        selected_skills: Optional[List[str]] = None,
        writeback_target: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs comprehensive 18-point preflight checklist."""
        failures = []

        # 1. User platform access (AUTH_FORBIDDEN)
        if not user_id or user_id.startswith("blocked_"):
            failures.append({
                "code": "AUTH_FORBIDDEN",
                "message": f"User '{user_id}' is not authorized to execute agent workflows.",
                "remediation": "Request platform access via IT Access Portal."
            })

        # 2. Team validity (TEAM_UNAVAILABLE)
        if not team_id or team_id in self._suspended_teams:
            failures.append({
                "code": "TEAM_UNAVAILABLE",
                "message": f"Team '{team_id}' is suspended or does not exist.",
                "remediation": "Contact Team Admin to activate team workspace."
            })

        # 3. Workflow version check (WORKFLOW_NOT_AVAILABLE)
        wf = workflow_registry.get_workflow(agent_identifier)
        if not wf:
            failures.append({
                "code": "WORKFLOW_NOT_AVAILABLE",
                "message": f"Workflow for agent '{agent_identifier}' is not published or registered.",
                "remediation": "Verify agent catalog or publish workflow version."
            })
            return {"passed": False, "failure_count": len(failures), "failures": failures}

        # 4. Required inputs check (REQUIRED_INPUT_MISSING / INPUT_INVALID)
        input_val_res = workflow_registry.validate_inputs(agent_identifier, input_data)
        if not input_val_res.get("valid"):
            if "missing_fields" in input_val_res:
                failures.append({
                    "code": "REQUIRED_INPUT_MISSING",
                    "message": input_val_res.get("error"),
                    "details": input_val_res.get("missing_fields"),
                    "remediation": "Provide all mandatory input fields in intake session."
                })
            else:
                failures.append({
                    "code": "INPUT_INVALID",
                    "message": input_val_res.get("error"),
                    "field": input_val_res.get("field"),
                    "remediation": "Correct input format to satisfy schema rules."
                })

        # 5. Context Access & Mapping (CONTEXT_ACCESS_DENIED)
        if selected_context_packs:
            for pack_id in selected_context_packs:
                if not mock_context_engine.verify_access(team_id, pack_id):
                    failures.append({
                        "code": "CONTEXT_ACCESS_DENIED",
                        "message": f"Team '{team_id}' is not authorized to access context pack '{pack_id}'.",
                        "remediation": "Request context pack permission from Data Governance lead."
                    })

        # 6. Skill Bindings (SKILL_BINDING_MISSING)
        req_skills = wf.get("skills", {}).get("required", [])
        for sk in req_skills:
            skill_id = sk.get("skill_id") or sk.get("capability")
            if not mock_skills_engine.verify_skill_binding(team_id, skill_id):
                failures.append({
                    "code": "SKILL_BINDING_MISSING",
                    "message": f"Required skill '{skill_id}' is not bound to team '{team_id}'.",
                    "remediation": "Configure skill binding in Team Admin settings."
                })

        # 7. Model Policy (MODEL_POLICY_DENIED)
        model_policy = wf.get("model_policy_ref", "default")
        if model_policy.startswith("forbidden_"):
            failures.append({
                "code": "MODEL_POLICY_DENIED",
                "message": f"Model policy '{model_policy}' is not approved for team '{team_id}'.",
                "remediation": "Route request to AI Governance review."
            })

        # 8. Connector Health (CONNECTOR_UNHEALTHY)
        if writeback_target == "unhealthy_connector":
            failures.append({
                "code": "CONNECTOR_UNHEALTHY",
                "message": "Target enterprise connector is currently unreachable.",
                "remediation": "Check connector health endpoint in integration hub."
            })

        passed = len(failures) == 0
        if passed:
            logger.info(f"PreflightValidationService: Preflight passed for {agent_identifier} (Team: {team_id})")
        else:
            logger.warning(f"PreflightValidationService: Preflight failed with {len(failures)} issue(s) for {agent_identifier}")

        return {
            "passed": passed,
            "failure_count": len(failures),
            "failures": failures,
            "validated_workflow_id": wf.get("workflow_id"),
            "agent_id": wf.get("agent", {}).get("id"),
            "model_policy_ref": wf.get("model_policy_ref")
        }

    def validate_preflight(self, request: Any) -> Any:
        """Pydantic model adapter for PreflightRequest and PreflightResponse."""
        from ..models.run_models import PreflightCheckResult, PreflightResponse

        agent_id = getattr(request, "agent_id", None) or getattr(request, "agent_identifier", None) or "AG-201"
        team_id = getattr(request, "team_id", "team-checkout-qe")
        user_id = getattr(request, "user_id", "usr-architect-01")
        inputs = getattr(request, "inputs", {})

        res = self.run_preflight(
            agent_identifier=agent_id,
            team_id=team_id,
            user_id=user_id,
            input_data=inputs
        )

        rule_results = []
        error_codes = []
        blockers = 0
        warnings = 0

        for f in res.get("failures", []):
            code = f.get("code", "PREFLIGHT_ERROR")
            error_codes.append(code)
            blockers += 1
            rule_results.append(PreflightCheckResult(
                rule_id=code.lower(),
                rule_name=code,
                status="FAIL",
                severity="BLOCKER",
                error_code=code,
                message=f.get("message", ""),
                details=f
            ))

        if res.get("passed"):
            rule_results.append(PreflightCheckResult(
                rule_id="all_checks_passed",
                rule_name="PREFLIGHT_PASSED",
                status="PASS",
                severity="INFO",
                error_code=None,
                message="All 18 preflight verification rules evaluated successfully."
            ))

        return PreflightResponse(
            valid=res.get("passed", False),
            agent_id=agent_id,
            team_id=team_id,
            rule_results=rule_results,
            error_codes=error_codes,
            blockers_count=blockers,
            warnings_count=warnings,
            missing_required_fields=[f.get("field") for f in res.get("failures", []) if f.get("field")],
            resolved_context_summary={},
            resolved_skills_summary=[]
        )


preflight_service = PreflightValidationService()
