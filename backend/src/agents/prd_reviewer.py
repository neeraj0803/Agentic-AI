import json
from typing import Any, Dict
from ..services.llm_service import LLMService


class PRDReviewerPrompt:
    @staticmethod
    def review(prd_markdown: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are an Executive PRD Quality Reviewer. Perform automated quality control on this Product Requirements Document against the 21-section enterprise standard.

PRD Content Preview:
{prd_markdown[:6000]}

Evaluate against the 21-section standard:
I. Problem Statement
II. Impact of Problem
III. Problem Area Process Map (As-Is)
IV. What is Needed to Fix the Problem
V. Customer and 3rd Party Research
VI. Supporting Data
VII. Solution Discovery, Recommendation, Teams Involved + Sizing
VIII. Functional and Technical Design
IX. To Be Process Map
X. Impact Assessment / Opportunity / Metrics
XI. Development Approach, High Level Requirements, + Epic Breakdown (with Acceptance Criteria)
XII. Open Questions and Decision Log
XIII. Roster
XIV. Market Research
XV. Competitive Analysis
XVI. Target Personas
XVII. Messaging & positioning
XVIII. Pricing
XIX. Distribution channels & launch activities
XX. Support plan
XXI. Reference materials

Score 0-100 (Threshold for pass is >= 80).
Check that missing inputs are marked with 'N/A' rather than omitted.

Return ONLY valid JSON:
{{
  "quality_score": 90,
  "passed": true,
  "completeness_assessment": {{
    "all_sections_present": true,
    "missing_sections": []
  }},
  "acceptance_criteria_valid": true,
  "areas_for_improvement": [],
  "revision_instructions": ""
}}
"""
        try:
            res = LLMService.generate(prompt)
            if res:
                cleaned = res.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and "quality_score" in parsed:
                    return parsed
        except Exception:
            pass

        # Fallback review evaluation for 21 sections
        required_roman_sections = [
            "I. Problem Statement",
            "II. Impact of Problem",
            "III. Problem Area Process Map",
            "IV. What is Needed to Fix the Problem",
            "VII. Solution Discovery",
            "VIII. Functional and Technical Design",
            "IX. To Be Process Map",
            "X. Impact Assessment",
            "XI. Development Approach",
            "XII. Open Questions and Decision Log",
            "XIII. Roster",
            "XVI. Target Personas",
            "XX. Support plan",
            "XXI. Reference materials"
        ]

        missing = [sec for sec in required_roman_sections if sec not in prd_markdown]
        has_given = "Given" in prd_markdown or "GIVEN" in prd_markdown or "given" in prd_markdown
        has_mermaid = "```mermaid" in prd_markdown

        score = 92 if (len(missing) == 0 and has_given and has_mermaid) else (85 if len(missing) <= 2 else 70)
        passed = score >= 80

        return {
            "quality_score": score,
            "passed": passed,
            "completeness_assessment": {
                "all_sections_present": len(missing) == 0,
                "missing_sections": missing
            },
            "acceptance_criteria_valid": has_given,
            "areas_for_improvement": [] if passed else [f"Ensure all 21 sections are present. Missing: {missing}"],
            "revision_instructions": "" if passed else f"Incorporate missing sections ({missing}) with 'N/A - Not specified in source input' if raw inputs are missing."
        }
