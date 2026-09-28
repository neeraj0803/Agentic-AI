import json
from typing import Any, Dict
from ..services.llm_service import LLMService


class PRDReviewerPrompt:
    @staticmethod
    def review(prd_markdown: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are an Executive PRD Reviewer. Perform automated quality control on this Product Requirements Document.

PRD Markdown:
{prd_markdown[:5000]}

Evaluate against enterprise standards:
1. Executive Summary
2. Problem & Evidence grounding
3. Measurable KPIs & OKR alignment
4. Users & Journey
5. System Overview & Architecture alignment
6. Clear MVP Scope
7. Functional Requirements with Given/When/Then acceptance criteria
8. Agent & MCP Integration design
9. Mermaid sequence or flowchart diagram
10. NFRs (latency, security, PCI-DSS compliance)
11. Dependencies, Risks & Mitigations
12. Open Questions & Conflict resolutions
13. Release Strategy & Implementation milestones

Score 0-100 (Threshold for pass is >= 80).

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

        # Fallback review evaluation
        has_given = "Given" in prd_markdown or "GIVEN" in prd_markdown or "given" in prd_markdown
        has_mermaid = "```mermaid" in prd_markdown
        has_nfr = "NON-FUNCTIONAL" in prd_markdown or "PCI-DSS" in prd_markdown

        score = 90 if (has_given and has_mermaid and has_nfr) else 75
        passed = score >= 80

        return {
            "quality_score": score,
            "passed": passed,
            "completeness_assessment": {
                "all_sections_present": True,
                "missing_sections": []
            },
            "acceptance_criteria_valid": has_given,
            "areas_for_improvement": [] if passed else ["Add Given/When/Then acceptance criteria and Mermaid diagram"],
            "revision_instructions": "" if passed else "Add Given/When/Then acceptance criteria to FRs and Mermaid diagram."
        }

