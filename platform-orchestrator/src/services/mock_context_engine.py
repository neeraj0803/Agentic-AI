import time
from typing import Any, Dict, List, Optional
import uuid

from ..telemetry import logger


class MockContextEngine:
    """
    Mock Context Engine for Platform Orchestrator boundaries.
    Simulates Prism Context Engine MCP/JSON-RPC server when live context provider is not connected.
    Supplies:
    - Context catalog per domain/team
    - Context authorization and scope checks
    - Simulated context package retrieval with citations, freshness, and status
    """

    def __init__(self):
        self._packs = {
            "ctx_enterprise_brd": {
                "pack_id": "ctx_enterprise_brd",
                "name": "Enterprise Baseline BRD & Architectural Principles",
                "domain": "ENTERPRISE",
                "summary": "Covers platform objectives (OBJ-01 to OBJ-06), FinOps controls, and standard isolation boundaries.",
                "freshness": "FRESH",
                "citations": ["docs/BRD.md#L1-L150", "docs/00_hld_master_blueprint.md#L45-L90"]
            },
            "ctx_checkout_domain": {
                "pack_id": "ctx_checkout_domain",
                "name": "Checkout & Payments Domain Glossary",
                "domain": "CHECKOUT",
                "summary": "Payment intent state machine, idempotent retry keys, and error recovery policies.",
                "freshness": "FRESH",
                "citations": ["docs/02_end_to_end_agent_execution_design.md#L20-L80"]
            },
            "ctx_qe_standards": {
                "pack_id": "ctx_qe_standards",
                "name": "Enterprise QE Testing Standards & Templates",
                "domain": "QUALITY_ENGINEERING",
                "summary": "BDD Gherkin format rules, boundary testing guidelines, and security test patterns.",
                "freshness": "FRESH",
                "citations": ["docs/08_traceability_validation_and_handoff.md"]
            }
        }

    def list_available_packs(self, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists available context packs for the active team."""
        return list(self._packs.values())

    def verify_access(self, team_id: str, pack_id: str) -> bool:
        """Verifies if the active team is authorized to access the requested context pack."""
        # In mock mode, all registered packs are authorized unless prefixed with 'restricted_'
        if pack_id.startswith("restricted_"):
            return False
        return True

    def retrieve_package(
        self,
        pack_ids: List[str],
        query: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Simulates building a unified Prism context package for the given pack IDs."""
        package_id = f"pkg_{uuid.uuid4().hex[:12]}"
        retrieved_citations = []
        snippets = []

        for pid in pack_ids:
            pack = self._packs.get(pid)
            if pack:
                retrieved_citations.extend(pack["citations"])
                snippets.append({
                    "pack_id": pid,
                    "title": pack["name"],
                    "content": pack["summary"]
                })

        logger.info(f"MockContextEngine: Generated context package {package_id} with {len(snippets)} pack(s).")
        return {
            "package_id": package_id,
            "status": "READY",
            "freshness": "FRESH",
            "total_items": len(snippets) + len(retrieved_citations),
            "citation_count": len(retrieved_citations),
            "citations": retrieved_citations,
            "snippets": snippets,
            "generated_at": time.time()
        }

    def build_context_package(
        self,
        team_id: str,
        application_name: str,
        required_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Builds a contextual bundle for preflight checks and worker runtime."""
        pack_keys = list(self._packs.keys())
        citations = []
        snippets = []
        for pk in pack_keys:
            p = self._packs[pk]
            citations.extend(p.get("citations", []))
            snippets.append({
                "pack_id": pk,
                "title": p.get("name"),
                "summary": p.get("summary")
            })

        return {
            "package_id": f"ctx_pkg_{uuid.uuid4().hex[:10]}",
            "team_id": team_id,
            "application_name": application_name,
            "required_capabilities": required_capabilities,
            "total_items": len(snippets),
            "citation_count": len(citations),
            "citations": citations,
            "snippets": snippets,
            "status": "READY",
            "freshness": "FRESH",
            "generated_at": time.time()
        }


mock_context_engine = MockContextEngine()
