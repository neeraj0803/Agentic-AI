from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..agents.prd_generator import PRDGeneratorPrompt
from ..services.llm_service import LLMService


class PRDGeneratorService:
    def generate(self, context: Any) -> str:
        context = self._normalize_context(context)

        if self._llm_available():
            try:
                prompt_template = PRDGeneratorPrompt.get_prompt()
                prompt = prompt_template.replace("{context}", json.dumps(context, indent=2))
                generated = LLMService.generate(prompt, provider=self._preferred_provider())
                if generated and "```" in generated:
                    generated = generated.replace("```json", "").replace("```", "").strip()
                if generated:
                    parsed = self._parse_generated_json(generated)
                    if parsed:
                        self._save_outputs(parsed)
                        return self._markdown_from_json(parsed)
            except Exception:
                pass

        raise ValueError("No valid PRD context was provided by the previous evidence model output.")

    def _llm_available(self) -> bool:
        try:
            from ..config import settings
            return bool(settings.azure_openai.azure_openai_api_key or settings.gemini.google_api_key)
        except Exception:
            return False

    def _preferred_provider(self) -> str:
        try:
            from ..config import settings
            if settings.azure_openai.azure_openai_api_key:
                return "azure"
            return "gemini"
        except Exception:
            return "gemini"

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
            "problem": problem,
            "users": users,
            "needs": needs,
            "expected_impact": expected_impact,
            "scope": scope,
            "assumptions": assumptions,
            "constraints": constraints,
        }

    def _parse_generated_json(self, content: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return None
            required_keys = ["problem", "users", "needs", "expected_impact", "scope", "assumptions", "constraints"]
            if any(key not in parsed for key in required_keys):
                return None
            return parsed
        except Exception:
            return None

    def _save_outputs(self, payload: dict[str, Any]) -> None:
        output_dir = Path(__file__).resolve().parents[2]
        json_path = output_dir / "prd_output.json"
        md_path = output_dir / "prd_output.md"

        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md_path.write_text(self._markdown_from_json(payload), encoding="utf-8")

    def _markdown_from_json(self, payload: dict[str, Any]) -> str:
        scope = payload.get("scope") or {}
        in_scope = scope.get("in_scope", [])
        out_scope = scope.get("out_of_scope", [])

        lines = [
            "# Product Requirements Document",
            "",
            "## Problem",
            "",
            payload.get("problem", ""),
            "",
            "## Users",
            "",
        ]

        users = payload.get("users") or []
        if users:
            for user in users:
                lines.append(f"- {user}")
        else:
            lines.append("- Not specified")

        lines.extend(["", "## Needs", ""])
        needs = payload.get("needs") or []
        if needs:
            for item in needs:
                lines.append(f"- {item}")
        else:
            lines.append("- Not specified")

        lines.extend(["", "## Expected Impact", ""])
        impacts = payload.get("expected_impact") or []
        if impacts:
            for item in impacts:
                lines.append(f"- {item}")
        else:
            lines.append("- Not specified")

        lines.extend(["", "## Scope", "", "### In Scope", ""])
        if in_scope:
            for item in in_scope:
                lines.append(f"- {item}")
        else:
            lines.append("- Not specified")

        lines.extend(["", "### Out of Scope", ""])
        if out_scope:
            for item in out_scope:
                lines.append(f"- {item}")
        else:
            lines.append("- Not specified")

        lines.extend(["", "## Assumptions", ""])
        assumptions = payload.get("assumptions") or []
        if assumptions:
            for item in assumptions:
                lines.append(f"- {item}")
        else:
            lines.append("- Not specified")

        lines.extend(["", "## Constraints", ""])
        constraints = payload.get("constraints") or []
        if constraints:
            for item in constraints:
                lines.append(f"- {item}")
        else:
            lines.append("- Not specified")

        return "\n".join(lines) + "\n"
