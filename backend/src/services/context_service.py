import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..mcp import InProcessMCPClient
from ..services.llm_service import LLMService


class ContextAnalyzerService:
    """
    Context Analyzer Agent & Service.
    Implements:
    - Flowchart Node C (2. Context Analyzer)
    - Substep 1: Understand request and classify intent dynamically from document
    - Substep 2: Discover capabilities via MCP Skill Engine
    - Substep 3: Retrieve business, product, and application context via MCP Context Engine
    - Merges document extraction with dynamically retrieved Jira/Confluence/Git references.
    """

    def __init__(self, mcp_client: Optional[InProcessMCPClient] = None):
        self.mcp_client = mcp_client or InProcessMCPClient()

    def analyze(
        self,
        document_name: str,
        extracted_text: str,
        active_team_id: str = "team-enterprise-product",
        query_override: Optional[str] = None
    ) -> Dict[str, Any]:
        # 1. Classify intent & infer query
        intent_info = self._classify_intent(document_name, extracted_text, query_override)

        # 2. Discover skills from MCP Skill Engine
        skills_discovery = self.mcp_client.discover_skills(
            capability_need="prd_generation",
            domain="Product & Engineering",
            active_team_id=active_team_id
        )

        # 3. Retrieve context from MCP Context Engine (Prism)
        context_retrieval = self.mcp_client.retrieve_context(
            query_text=intent_info["query_text"],
            workflow_name="Generate PRD",
            agent_name="prd_context_brief_agent",
            active_team_id=active_team_id
        )

        mcp_context_package = context_retrieval.get("context_package", {})

        # 4. Synthesize document text + MCP evidence (LLM with deterministic parser fallback)
        analyzed_context = self._synthesize_context(
            document_name=document_name,
            extracted_text=extracted_text,
            mcp_context_package=mcp_context_package
        )

        # 5. Extract and normalize scope
        scope = analyzed_context.get("scope") or {}
        if not scope or (not scope.get("in_scope") and not scope.get("out_of_scope")):
            in_scope_items = self._extract_scope_items(extracted_text, "in_scope")
            out_scope_items = self._extract_scope_items(extracted_text, "out_of_scope")
            if not in_scope_items:
                in_scope_items = [
                    f"Core capabilities for {intent_info['title']}",
                    "Integration with enterprise domain services"
                ]
            scope = {
                "in_scope": in_scope_items,
                "out_of_scope": out_scope_items or ["Out-of-scope manual operational processes"]
            }

        # Merge all into structured context package
        result = {
            "document_name": document_name,
            "extracted_text": extracted_text,
            "intent": intent_info["intent"],
            "query_text": intent_info["query_text"],
            "title": intent_info["title"],
            "problem_statement": analyzed_context.get("problem_statement", ""),
            "business_goal": analyzed_context.get("business_goal", ""),
            "evidence": analyzed_context.get("evidence", []),
            "users": analyzed_context.get("users", []),
            "assumptions": analyzed_context.get("assumptions", []),
            "constraints": analyzed_context.get("constraints", []),
            "scope": scope,
            "mcp_skills": skills_discovery.get("skills", []),
            "mcp_context_package": mcp_context_package,
            "mcp_rpc_traces": {
                "skills_call": skills_discovery.get("request"),
                "context_call": context_retrieval.get("request")
            }
        }

        return result

    def _classify_intent(
        self,
        document_name: str,
        text: str,
        query_override: Optional[str] = None
    ) -> Dict[str, str]:
        if query_override:
            return {
                "intent": "prd_context_generation",
                "query_text": query_override,
                "title": query_override
            }

        # Derive clean title from document header or filename
        title = ""
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        for line in lines[:5]:
            cleaned = line.replace("#", "").replace("**", "").replace(":", "").strip()
            if len(cleaned) > 5 and not any(cleaned.lower().startswith(p) for p in ["problem", "objective", "tc-", "test"]):
                if cleaned.lower().startswith("business requirements document"):
                    cleaned = cleaned.split("document", 1)[-1].strip(" :-\t")
                title = cleaned
                break

        if not title and document_name:
            title = Path(document_name).stem.replace("_", " ").replace("-", " ").title()

        title = title or "Enterprise Feature Requirements"
        if len(title) > 80:
            title = title[:77] + "..."

        query_text = f"Create a PRD/context brief for {title.lower()}."

        return {
            "intent": "prd_context_generation",
            "query_text": query_text,
            "title": title
        }

    def _synthesize_context(
        self,
        document_name: str,
        extracted_text: str,
        mcp_context_package: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            mcp_summary = json.dumps({
                "references": mcp_context_package.get("retrieved_references", []),
                "signals": mcp_context_package.get("candidate_signals", {}),
                "conflicts": mcp_context_package.get("conflicts", []),
                "gaps": mcp_context_package.get("gaps_or_questions", [])
            }, indent=2)

            prompt = f"""
You are a Senior Business Analyst. Analyze the uploaded document alongside enterprise context retrieved via MCP.

Uploaded Document ({document_name}):
{extracted_text[:4000]}

Retrieved MCP Context (Jira, Confluence, Git references):
{mcp_summary}

Extract and synthesize the following fields directly from the provided text and MCP references. Do not hallucinate or hardcode unrelated domains.
1. Problem Statement
2. Business Goal
3. Supporting Evidence (synthesizing document facts and MCP references)
4. Users (Primary & Secondary personas)
5. Scope (in_scope and out_of_scope lists)
6. Assumptions
7. Constraints

Return ONLY valid JSON:
{{
  "problem_statement": "Clear problem statement extracted from the document",
  "business_goal": "Measurable business goal extracted from the document",
  "evidence": ["Evidence point 1", "Evidence point 2"],
  "users": ["Primary Persona", "Secondary Persona"],
  "scope": {{
    "in_scope": ["Feature 1", "Feature 2"],
    "out_of_scope": ["Out of scope 1"]
  }},
  "assumptions": ["Assumption 1"],
  "constraints": ["Constraint 1"]
}}
"""
            response = LLMService.generate(prompt)
            if response:
                cleaned = response.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and "problem_statement" in parsed and parsed["problem_statement"]:
                    return parsed
        except Exception:
            pass

        return self._deterministic_fallback_extraction(extracted_text, mcp_context_package)

    def _deterministic_fallback_extraction(
        self,
        text: str,
        mcp_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extracts sections dynamically from the markdown/text document.
        """
        problem = self._extract_section_text(text, ["problem", "problem statement", "objective", "challenge"])
        goal = self._extract_section_text(text, ["goal", "business goal", "target outcome", "expected outcome"])
        evidence = self._extract_list_items(text, ["evidence", "supporting evidence", "background", "signals"])
        users = self._extract_list_items(text, ["users", "personas", "stakeholders", "target personas"])
        assumptions = self._extract_list_items(text, ["assumptions", "known assumptions"])
        constraints = self._extract_list_items(text, ["constraints", "nfr", "non-functional requirements", "known constraints"])

        # Add retrieved MCP evidence
        for ref in mcp_context.get("retrieved_references", []):
            if ref.get("reason_for_relevance"):
                evidence.append(f"{ref.get('source_type', 'Reference').replace('_', ' ').title()}: {ref.get('title')} ({ref.get('reason_for_relevance')})")

        if not problem:
            problem = f"Requirements and capability enhancements defined in the document."
        if not goal:
            goal = f"Deliver the business capabilities and improvements outlined in the specification."
        if not users:
            users = ["Enterprise User", "Operations Lead", "System Administrator"]
        if not assumptions:
            assumptions = [f"Upstream domain APIs maintain target availability SLAs."]
        if not constraints:
            constraints = [f"System interactions must adhere to enterprise security and compliance standards."]

        return {
            "problem_statement": problem,
            "business_goal": goal,
            "evidence": evidence,
            "users": users,
            "assumptions": assumptions,
            "constraints": constraints
        }

    def _extract_section_text(self, text: str, section_names: List[str]) -> str:
        lines = text.split("\n")
        capturing = False
        captured = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                header_title = stripped.replace("#", "").replace("**", "").strip().lower()
                # Check if this header matches any section name
                if any(sec in header_title for sec in section_names):
                    capturing = True
                    continue
                elif capturing:
                    break
            elif capturing and stripped:
                if stripped.startswith("-") or stripped.startswith("*"):
                    captured.append(stripped.lstrip("-* ").strip())
                else:
                    captured.append(stripped)

        return " ".join(captured).strip()

    def _extract_list_items(self, text: str, section_names: List[str]) -> List[str]:
        lines = text.split("\n")
        capturing = False
        items = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                header_title = stripped.replace("#", "").replace("**", "").strip().lower()
                if any(sec in header_title for sec in section_names):
                    capturing = True
                    continue
                elif capturing:
                    break
            elif capturing and stripped:
                if stripped.startswith("-") or stripped.startswith("*") or re.match(r"^\d+\.", stripped):
                    item_text = re.sub(r"^[-*\d\.]+\s*", "", stripped).strip()
                    if item_text:
                        items.append(item_text)

        return items

    def _extract_scope_items(self, text: str, scope_type: str) -> List[str]:
        target_headers = ["in scope", "in-scope", "mvp"] if scope_type == "in_scope" else ["out of scope", "out-of-scope", "non-goals"]
        return self._extract_list_items(text, target_headers)