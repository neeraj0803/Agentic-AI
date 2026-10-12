import re
from typing import Any, Dict, List, Optional

from .workflow_registry import workflow_registry
from ..telemetry import logger


class IntentResolver:
    """
    Agent Intent Resolution Service.
    Resolves natural language requests or problem statements to published workflow agents (AG-101 to AG-501).
    Computes semantic keyword confidence.
    If confidence >= 0.8, directly resolves.
    If ambiguous, returns top candidates for user clarification.
    """

    def __init__(self):
        self._intent_keywords = {
            "AG-101": ["prd", "product requirements", "feature spec", "brief", "initiative", "problem statement", "user persona", "scope"],
            "AG-102": ["epic", "user stories", "breakdown", "story points", "jira tickets", "acceptance criteria", "agile"],
            "AG-201": ["test case", "qe", "testing", "bdd", "gherkin", "regression", "qa", "test suite", "functional test"],
            "AG-202": ["xray", "test sync", "zephyr", "jira test", "export test"],
            "AG-301": ["code", "implementation", "feature code", "backend", "frontend", "git", "gitlab", "pull request", "merge request", "patch"],
            "AG-501": ["adr", "architecture", "c4 diagram", "architecture decision", "tradeoff", "system design", "tech stack"]
        }

    def resolve_intent(
        self,
        user_prompt: str,
        team_id: Optional[str] = None,
        context_hints: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Resolves natural language user query to matching agent workflow."""
        prompt_lower = user_prompt.lower()
        scores: Dict[str, float] = {}

        # 1. Exact agent code mention (e.g. "Run AG-201")
        for agent_id in self._intent_keywords.keys():
            if agent_id.lower() in prompt_lower or agent_id.replace("-", "").lower() in prompt_lower:
                wf = workflow_registry.get_workflow(agent_id)
                if wf:
                    return {
                        "resolved": True,
                        "confidence": 1.0,
                        "confidence_score": 1.0,
                        "agent_id": agent_id,
                        "top_agent_id": agent_id,
                        "agent_name": wf.get("agent", {}).get("name"),
                        "workflow_name": wf.get("agent", {}).get("name"),
                        "workflow_id": wf.get("workflow_id"),
                        "extracted_parameters": {},
                        "candidates": [],
                        "suggested_alternatives": []
                    }

        # 2. Keyword heuristic scoring
        words = set(re.findall(r"\b\w+\b", prompt_lower))
        for agent_id, keywords in self._intent_keywords.items():
            match_count = sum(1 for kw in keywords if kw in prompt_lower or any(w in kw for w in words if len(w) > 3))
            if match_count > 0:
                scores[agent_id] = min(0.95, 0.4 + (match_count * 0.2))

        if not scores:
            # Default to AG-101 (PRD generator) if no specific keywords match
            wf = workflow_registry.get_workflow("AG-101")
            return {
                "resolved": False,
                "confidence": 0.3,
                "confidence_score": 0.3,
                "top_agent_id": "AG-101",
                "agent_id": "AG-101",
                "workflow_name": "Product PRD & Context Brief Generator",
                "clarification_required": True,
                "extracted_parameters": {},
                "message": "Could not determine the target agent with high confidence. Please select from available options.",
                "candidates": [
                    {"agent_id": "AG-101", "name": "Product PRD & Context Brief Generator", "domain": "PRODUCT_MANAGEMENT"},
                    {"agent_id": "AG-201", "name": "QE Test Case Generator", "domain": "QUALITY_ENGINEERING"},
                    {"agent_id": "AG-301", "name": "Software Engineering & Code Generator", "domain": "SOFTWARE_ENGINEERING"}
                ],
                "suggested_alternatives": []
            }

        sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_agent, top_score = sorted_agents[0]

        wf = workflow_registry.get_workflow(top_agent)
        agent_name = wf.get("agent", {}).get("name") if wf else top_agent

        if top_score >= 0.7:
            logger.info(f"IntentResolver: Resolved '{user_prompt[:40]}...' to {top_agent} (Confidence: {top_score:.2f})")
            return {
                "resolved": True,
                "confidence": round(top_score, 2),
                "confidence_score": round(top_score, 2),
                "agent_id": top_agent,
                "top_agent_id": top_agent,
                "agent_name": agent_name,
                "workflow_name": agent_name,
                "workflow_id": wf.get("workflow_id") if wf else None,
                "extracted_parameters": {},
                "candidates": [],
                "suggested_alternatives": []
            }
        else:
            candidates = []
            for ag_id, sc in sorted_agents[:3]:
                w = workflow_registry.get_workflow(ag_id)
                if w:
                    candidates.append({
                        "agent_id": ag_id,
                        "name": w.get("agent", {}).get("name"),
                        "confidence": round(sc, 2)
                    })
            return {
                "resolved": False,
                "confidence": round(top_score, 2),
                "confidence_score": round(top_score, 2),
                "top_agent_id": top_agent,
                "agent_id": top_agent,
                "workflow_name": agent_name,
                "clarification_required": True,
                "extracted_parameters": {},
                "message": f"Did you mean to run {agent_name} ({top_agent})?",
                "suggested_agent_id": top_agent,
                "candidates": candidates,
                "suggested_alternatives": candidates
            }



intent_resolver = IntentResolver()
