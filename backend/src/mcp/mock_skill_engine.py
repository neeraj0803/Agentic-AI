from typing import Any, Dict, List
from .schemas import JsonRpcRequest, JsonRpcResponse


class MockSkillEngine:
    """
    In-process Mock MCP Skill Engine.
    Handles `tools/call` for `discover_skills` conforming strictly to the user's schema:
    Request: { "jsonrpc": "2.0", "id": "...", "method": "tools/call", "params": { "name": "discover_skills", "arguments": {...} } }
    Response: { "jsonrpc": "2.0", "id": "...", "result": { "skills": [...] } }
    """

    def __init__(self):
        self._skills_catalog = [
            {
                "skill_id": "runbook_generator",
                "skill_version": "2.0",
                "capability": "runbook_generation",
                "domain": "DevOps",
                "input_type": "application_operations_context",
                "output_type": "runbook_document",
                "governance_status": "approved",
                "lifecycle_status": "active",
                "owner": "DevOps Skills Team"
            },
            {
                "skill_id": "prd_generator",
                "skill_version": "2.0",
                "capability": "prd_generation",
                "domain": "Product & Engineering",
                "input_type": "context_and_evidence_package",
                "output_type": "product_requirements_document",
                "governance_status": "approved",
                "lifecycle_status": "active",
                "owner": "Apex Product Architecture Team"
            },
            {
                "skill_id": "context_brief_generator",
                "skill_version": "1.5",
                "capability": "context_brief_synthesis",
                "domain": "Enterprise Architecture",
                "input_type": "jira_confluence_git_signals",
                "output_type": "context_brief",
                "governance_status": "approved",
                "lifecycle_status": "active",
                "owner": "Prism Context Team"
            }
        ]

    def handle_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request_payload.get("id", "skills-discover-001")
        params = request_payload.get("params", {})
        args = params.get("arguments", {})
        filters = args.get("filters", {})

        cap_need = filters.get("capability_need")
        domain = filters.get("domain")

        matching_skills = []
        for skill in self._skills_catalog:
            if cap_need and skill["capability"] != cap_need:
                # If capability specifically requested (e.g. runbook_generation), match strictly
                if cap_need == "runbook_generation" and skill["skill_id"] == "runbook_generator":
                    matching_skills.append(skill)
                elif cap_need == "prd_generation" and skill["skill_id"] == "prd_generator":
                    matching_skills.append(skill)
                continue
            matching_skills.append(skill)

        if not matching_skills:
            matching_skills = [self._skills_catalog[1]]  # Default prd_generator

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "skills": matching_skills
            }
        }

