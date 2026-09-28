import json
from typing import Any, Dict
from ..services.llm_service import LLMService


def evidence_analyzer_node(context_analysis: Dict[str, Any]) -> Dict[str, Any]:
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

    prompt = f"""
You are an Evidence Analyzer Agent. Inspect the following product context and evaluate whether the evidence, problem statement, and requirements are sufficient to proceed with PRD generation.

Context to Analyze:
- Problem Statement: {prob}
- Business Goal: {goal}
- Target Users: {json.dumps(users)}
- Evidence Items: {json.dumps(evidence)}
- Assumptions: {json.dumps(assumptions)}
- Constraints: {json.dumps(constraints)}
- Document Snippet: {doc_text[:1500]}

Evaluate:
1. Is the problem well-defined and grounded?
2. Are business goals and success criteria present?
3. Is evidence or telemetry provided to back the problem?
4. Are missing context items or weak evidence identified?

Return ONLY valid JSON:
{{
  "sufficient": true,
  "missing_context": [],
  "weak_evidence": [],
  "rationale": "Evidence and problem framing are well-grounded."
}}
"""
    try:
        res = LLMService.generate(prompt)
        if res:
            cleaned = res.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "sufficient" in parsed:
                return parsed
    except Exception:
        pass

    # Dynamic fallback evaluation
    has_prob = bool(prob and len(str(prob).strip()) > 15)
    has_goal = bool(goal and len(str(goal).strip()) > 10)
    has_evidence = len(evidence) > 0 or len(doc_text) > 100

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
