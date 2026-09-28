import json
import re
from typing import Any, Mapping
from ..services.llm_service import LLMService


def evidence_analyzer_node(context_analysis: Mapping[str, Any]) -> dict[str, Any]:
    """
    Evidence Analyzer Agent node.
    Inspects problem statements, business goals, evidence, users, assumptions,
    and constraints using the LLM to assess grounding and sufficiency.
    Returns structured JSON:
    {
      "sufficient": bool,
      "missing_context": List[str],
      "weak_evidence": List[str],
      "rationale": str
    }
    """
    prob = context_analysis.get("problem_statement") or context_analysis.get("problem") or ""
    goal = context_analysis.get("business_goal") or ""
    evidence = context_analysis.get("evidence", [])
    users = context_analysis.get("users", [])
    assumptions = context_analysis.get("assumptions", [])
    constraints = context_analysis.get("constraints", [])
    doc_text = context_analysis.get("extracted_text", "")

    context = {
        "problem_statement": prob,
        "business_goal": goal,
        "evidence": evidence,
        "users": users,
        "assumptions": assumptions,
        "constraints": constraints,
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
  "rationale": "Evidence and problem framing are well-grounded."
}}

If information is absent or too vague, set "sufficient" to false and explain
the gaps in the corresponding lists.

Context:
{json.dumps(context, ensure_ascii=False, indent=2)}
"""
    try:
        response = LLMService.generate(prompt)
        if response:
            cleaned_response = re.sub(
                r"^\s*```(?:json)?\s*|\s*```\s*$",
                "",
                response.strip(),
                flags=re.IGNORECASE,
            )
            review = json.loads(cleaned_response)
            if isinstance(review, dict) and isinstance(review.get("sufficient"), bool):
                return {
                    "sufficient": review["sufficient"],
                    "missing_context": review.get("missing_context", []),
                    "weak_evidence": review.get("weak_evidence", []),
                    "rationale": review.get("rationale", ""),
                }
    except Exception:
        pass

    # Dynamic fallback evaluation
    has_prob = bool(prob and len(str(prob).strip()) > 15)
    has_goal = bool(goal and len(str(goal).strip()) > 10)

    missing = []
    if not has_prob:
        missing.append("Problem statement is missing or too vague.")
    if not has_goal:
        missing.append("Business goal is missing or lacks clear target metrics.")

    weak = []
    if len(evidence) == 0:
        weak.append("No telemetry, audit data, or customer research evidence provided in source input.")

    is_sufficient = has_prob and has_goal

    return {
        "sufficient": is_sufficient,
        "missing_context": missing,
        "weak_evidence": weak,
        "rationale": "Context contains clear problem and business goal." if is_sufficient else "Insufficient problem or goal grounding."
    }
