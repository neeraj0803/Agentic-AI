from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from ..agents.prd_generator import PRDGeneratorPrompt
from ..services.llm_service import LLMService


class PRDGeneratorService:
    """
    Generates structured 21-section PRDs directly via LLM.
    Zero deterministic fallback templates: ensures 100% dynamic AI generation.
    """

    def generate(
        self,
        context: Any,
        reviewer_feedback: Optional[str] = None
    ) -> str:
        context_data = self._normalize_context(context)
        title = (
            context_data.get("title")
            or context_data.get("document_name")
            or context_data.get("change_summary")
            or "Enterprise Capability PRD"
        )

        # 1. Enforce LLM availability
        if not self._llm_available():
            raise HTTPException(
                status_code=502,
                detail="LLM provider unavailable. Please configure your Azure OpenAI (AZURE_OPENAI_API_KEY) or Google Gemini (GOOGLE_API_KEY) credentials."
            )

        # 2. Invoke LLM for direct 21-section Markdown generation
        prompt = (
            PRDGeneratorPrompt.get_prompt()
            .replace("{title}", str(title))
            .replace("{context}", json.dumps(context_data, indent=2, default=str))
            .replace("{reviewer_feedback}", reviewer_feedback or "Initial generation - no reviewer changes.")
        )

        generated = LLMService.generate(prompt)
        if not generated or not generated.strip():
            raise HTTPException(
                status_code=502,
                detail="LLM service did not return a valid response. Please check model quota, connection, or credentials."
            )

        cleaned_md = generated.strip()
        if cleaned_md.startswith("```markdown") or cleaned_md.startswith("```md"):
            cleaned_md = cleaned_md.split("\n", 1)[1].rstrip("`").strip()
        elif cleaned_md.startswith("```") and cleaned_md.endswith("```"):
            cleaned_md = cleaned_md.strip("`").strip()

        # 3. Save generated artifacts
        self._save_outputs(context_data, cleaned_md)

        return cleaned_md

    def _llm_available(self) -> bool:
        try:
            from ..config import settings
            return bool(settings.azure_openai.azure_openai_api_key or settings.gemini.google_api_key)
        except Exception:
            return False

    def _normalize_context(self, context: Any) -> dict[str, Any]:
        if context is None:
            raise ValueError("PRD context is required.")

        if isinstance(context, list):
            merged: dict[str, Any] = {}
            for item in context:
                if isinstance(item, dict):
                    for key, value in item.items():
                        if value not in (None, "", [], {}):
                            merged[key] = value
            context = merged

        if not isinstance(context, dict):
            raise TypeError("PRD context must be a dictionary or list of dictionaries.")

        problem = (
            context.get("problem")
            or context.get("problem_statement")
            or context.get("business_goal")
            or ""
        )
        if isinstance(problem, dict):
            problem = problem.get("summary") or str(problem)

        users = context.get("users") or context.get("user_roles") or []
        needs = context.get("needs") or context.get("requirements") or []
        expected_impact = (
            context.get("expected_impact")
            or context.get("expected_outcome")
            or context.get("business_goal")
            or []
        )
        scope = context.get("scope") or {}
        if not scope and ("in_scope" in context or "out_of_scope" in context):
            scope = {
                "in_scope": context.get("in_scope") or [],
                "out_of_scope": context.get("out_of_scope") or [],
            }

        assumptions = context.get("assumptions") or []
        constraints = context.get("constraints") or []

        if isinstance(users, str):
            users = [users]
        if isinstance(needs, str):
            needs = [needs]
        if isinstance(expected_impact, str):
            expected_impact = [expected_impact]
        if isinstance(assumptions, str):
            assumptions = [assumptions]
        if isinstance(constraints, str):
            constraints = [constraints]

        if not problem:
            raise ValueError("Context must include a problem statement or business goal.")

        return {
            **context,
            "problem": problem,
            "problem_statement": problem,
            "users": users,
            "needs": needs,
            "expected_impact": expected_impact,
            "scope": scope,
            "assumptions": assumptions,
            "constraints": constraints,
        }

    def _save_outputs(
        self,
        context: dict[str, Any],
        prd_markdown: str
    ) -> None:
        try:
            output_dir = Path(__file__).resolve().parents[2] / "artifacts"
            output_dir.mkdir(parents=True, exist_ok=True)

            doc_title = context.get("title") or "PRD"
            safe_title = "".join(c for c in doc_title if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")

            json_file = output_dir / f"prd_context_{safe_title}.json"
            md_file = output_dir / f"prd_{safe_title}.md"

            json_file.write_text(json.dumps(context, indent=2, default=str), encoding="utf-8")
            md_file.write_text(prd_markdown, encoding="utf-8")

            # Standard output locations as required by workspace rules
            backend_dir = Path(__file__).resolve().parents[2]
            (backend_dir / "prd_output.json").write_text(json.dumps(context, indent=2, default=str), encoding="utf-8")
            (backend_dir / "prd_output.md").write_text(prd_markdown, encoding="utf-8")
        except Exception:
            pass
