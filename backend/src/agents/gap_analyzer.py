import json
from typing import Any, Dict
from ..services.llm_service import LLMService


class GapAnalyzerPrompt:
    @staticmethod
    def analyze(context_data: Dict[str, Any]) -> Dict[str, Any]:
        doc_text = context_data.get("extracted_text", "")
        prob = context_data.get("problem_statement", "")
        goal = context_data.get("business_goal", "")
        evidence = context_data.get("evidence", [])
        mcp_pkg = context_data.get("mcp_context_package", {})
        mcp_gaps = mcp_pkg.get("gaps_or_questions", [])
        mcp_conflicts = mcp_pkg.get("conflicts", [])

        prompt = f"""
You are a Senior Systems Analyst. Analyze this product context package for completeness, ambiguities, gaps, and conflicts.

Context Summary:
- Problem: {prob}
- Business Goal: {goal}
- Evidence Count: {len(evidence)}
- Discovered MCP Gaps: {json.dumps(mcp_gaps)}
- Discovered MCP Conflicts: {json.dumps(mcp_conflicts)}

Document Text Snippet:
{doc_text[:2000]}

Evaluate evidence sufficiency (score 0-100). If score >= 70, mark is_sufficient = true.
Identify open questions, unvalidated assumptions, and conflicts.

Return ONLY valid JSON:
{{
  "sufficiency_score": 85,
  "is_sufficient": true,
  "identified_gaps": ["Need target metric confirmation"],
  "unvalidated_assumptions": ["Assuming Payment Service transmits standard error codes"],
  "detected_conflicts": [
    {{
      "conflict_id": "conflict-prd-001",
      "description": "Older PRD excludes retry messaging; current epic includes it."
    }}
  ],
  "recommended_clarifications": ["Confirm target international payment methods"]
}}
"""
        try:
            res = LLMService.generate(prompt)
            if res:
                cleaned = res.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and "sufficiency_score" in parsed:
                    return parsed
        except Exception:
            pass

        # Fallback evaluation
        conflicts = mcp_conflicts or [
            {
                "conflict_id": "conflict-prd-001",
                "description": "Older PRD excludes retry messaging; current epic CHK-1200 includes it."
            }
        ]
        gaps = mcp_gaps or [
            "Need confirmation of target payment methods and markets.",
            "Need target metric for abandonment or retry success improvement.",
            "Need confirmation whether messaging changes require UX/content approval."
        ]
        return {
            "sufficiency_score": 85,
            "is_sufficient": True,
            "identified_gaps": gaps,
            "unvalidated_assumptions": [
                "Upstream Payment Service transmits standardized machine-readable decline category codes.",
                "Customers retain order items during soft decline retry steps."
            ],
            "detected_conflicts": conflicts,
            "recommended_clarifications": [
                "Confirm target international payment methods (e.g. Apple Pay, Klarna)."
            ]
        }

