import json
import re
from typing import Any, Mapping

from ..services.llm_service import LLMService


def evidence_analyzer_node(context_analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Assess whether analyzed context is sufficient to proceed with PRD generation."""
    context = {
        key: context_analysis.get(key, default)
        for key, default in {
            "problem_statement": "",
            "business_goal": "",
            "evidence": [],
            "users": [],
            "assumptions": [],
            "constraints": [],
        }.items()
    }

    prompt = f"""
You are a senior business analyst reviewing context before PRD generation.

Decide whether the supplied context and evidence are sufficient to draft a
grounded PRD. Check whether the problem and business goal are clear, users
are identified, and evidence is specific and relevant. Do not treat
assumptions as evidence. Do not invent missing information.

Return only valid JSON with this shape:
{{
  "sufficient": true,
  "missing_context": [],
  "weak_evidence": [],
  "rationale": ""
}}

If information is absent or too vague, set "sufficient" to false and explain
the gaps in the corresponding lists.

Context:
{json.dumps(context, ensure_ascii=False, indent=2)}
"""

    response = LLMService.generate(prompt)
    cleaned_response = re.sub(
        r"^\s*```(?:json)?\s*|\s*```\s*$",
        "",
        response.strip(),
        flags=re.IGNORECASE,
    )
    review = json.loads(cleaned_response)

    if not isinstance(review, dict) or not isinstance(review.get("sufficient"), bool):
        raise ValueError("Evidence review must contain a boolean 'sufficient' field.")

    return {
        "sufficient": review["sufficient"],
        "missing_context": review.get("missing_context", []),
        "weak_evidence": review.get("weak_evidence", []),
        "rationale": review.get("rationale", ""),
    }