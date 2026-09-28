from typing import Any, Dict, Optional
from .mock_skill_engine import MockSkillEngine
from .mock_context_engine import MockContextEngine


class InProcessMCPClient:
    """
    In-process programmatic client dispatching JSON-RPC 2.0 payloads
    to MockSkillEngine and MockContextEngine.
    """

    def __init__(
        self,
        skill_engine: Optional[MockSkillEngine] = None,
        context_engine: Optional[MockContextEngine] = None
    ):
        self.skill_engine = skill_engine or MockSkillEngine()
        self.context_engine = context_engine or MockContextEngine()

    def discover_skills(
        self,
        capability_need: str = "prd_generation",
        domain: str = "DevOps",
        active_team_id: str = "team-devops-platform"
    ) -> Dict[str, Any]:
        request_payload = {
            "jsonrpc": "2.0",
            "id": "skills-discover-admin-001",
            "method": "tools/call",
            "params": {
                "name": "discover_skills",
                "arguments": {
                    "search_context": {
                        "requested_by": "team_admin",
                        "active_team_id": active_team_id
                    },
                    "filters": {
                        "capability_need": capability_need,
                        "domain": domain,
                        "sdlc_phase": "Operate",
                        "governance_status": "approved",
                        "lifecycle_status": "active"
                    },
                    "result_preferences": {
                        "include_metadata": True,
                        "include_deprecated": False,
                        "max_results": 20
                    }
                }
            }
        }
        rpc_response = self.skill_engine.handle_request(request_payload)
        return {
            "request": request_payload,
            "response": rpc_response,
            "skills": rpc_response.get("result", {}).get("skills", [])
        }

    def retrieve_context(
        self,
        query_text: str = "Create a PRD/context brief for improving payment retry messaging in checkout.",
        workflow_name: str = "Generate PRD",
        agent_name: str = "prd_context_brief_agent",
        active_team_id: str = "team-checkout-product"
    ) -> Dict[str, Any]:
        request_payload = {
            "jsonrpc": "2.0",
            "id": "prd-context-request-001",
            "method": "tools/call",
            "params": {
                "name": "prism.context.retrieve",
                "arguments": {
                    "caller_reference": {
                        "platform": "Apex",
                        "workflow_run_reference": "apex-run-prd-001",
                        "workflow_name": workflow_name,
                        "agent_name": agent_name,
                        "agent_version": "1.0",
                        "step_name": "Retrieve Context",
                        "step_sequence": 2,
                        "correlation_id": "corr-prd-001"
                    },
                    "actor": {
                        "bearer_token": "<forwarded-user-token>",
                        "channel": "platform_ui",
                        "user_reference": "user-123"
                    },
                    "apex_scope": {
                        "active_team_id": active_team_id,
                        "scope_profile_id": "scope-checkout-v1",
                        "business_hints": {
                            "portfolios": ["Digital Engineering"],
                            "domains": ["Checkout"],
                            "products": ["Checkout Experience"]
                        },
                        "application_hints": {
                            "applications": ["Checkout Service"],
                            "repositories": ["checkout-service"],
                            "jira_projects": ["CHK"],
                            "confluence_spaces": ["CHECKOUT"]
                        }
                    },
                    "step_context": {
                        "step_intent": "Retrieve evidence for PRD/context brief generation.",
                        "configured_context_types": [
                            "prior_prds",
                            "related_epics",
                            "domain_docs",
                            "architecture_notes",
                            "standards"
                        ],
                        "configured_source_families": [
                            "jira",
                            "confluence",
                            "git"
                        ]
                    },
                    "query": {
                        "query_type": "natural_language",
                        "text": query_text
                    },
                    "retrieval_request": {
                        "context_needed": [
                            "retrieved_references",
                            "candidate_signals",
                            "gaps_or_questions",
                            "conflicts"
                        ],
                        "output_expectation": {
                            "package_type": "evidence_reference_package",
                            "include_relevance_rationale": True,
                            "include_citations": True,
                            "include_permission_exclusions": True
                        }
                    },
                    "controls": {
                        "data_classification": "internal",
                        "freshness_days": 180,
                        "context_size_target": "medium",
                        "timeout_ms": 30000
                    }
                }
            }
        }
        rpc_response = self.context_engine.handle_request(request_payload)
        return {
            "request": request_payload,
            "response": rpc_response,
            "context_package": rpc_response.get("result", {}).get("context_package", {})
        }

