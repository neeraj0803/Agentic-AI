from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ConfluenceContextAdapter(ABC):
    """Adapter interface for retrieving Confluence-like page content.

    This layer isolates the application from the specific Confluence integration
    implementation. A future real plugin can replace the mock adapter without
    changing service or API consumers.
    """

    @abstractmethod
    def fetch_page(self, page_id: str, space_key: str | None = None) -> dict[str, Any]:
        """Return a Confluence-like page payload for the given page id."""


class MockConfluenceContextAdapter(ConfluenceContextAdapter):
    """Mock implementation of the Confluence adapter.

    This simulates a Confluence page response containing the requirement inputs
    needed by the PRD workflow. It is intentionally structured so the real
    plugin can adopt the same contract later.
    """

    def fetch_page(self, page_id: str, space_key: str | None = None) -> dict[str, Any]:
        mock_pages = {
            "requirements-demo": {
                "page_id": "requirements-demo",
                "space_key": space_key or "REQ",
                "title": "Requirements Intake",
                "problem_statement": (
                    "Employees struggle to find the right enterprise knowledge articles and "
                    "support teams repeatedly answer the same questions using outdated or fragmented sources."
                ),
                "raw_notes": [
                    "Search is time-consuming and inconsistent across teams.",
                    "Support agents answer duplicate questions daily.",
                    "Users are not always sure which source is authoritative."
                ],
                "supporting_evidence": [
                    "70% of surveyed employees report difficulty finding the correct support documentation.",
                    "Average knowledge lookup time is 8 minutes per inquiry.",
                    "Support tickets containing repeat questions are increasing by 18% month over month.",
                    "Documentation links: https://confluence.example.com/knowledge-base, https://confluence.example.com/support-guides"
                ],
                "links": [
                    "https://confluence.example.com/knowledge-base",
                    "https://confluence.example.com/support-guides"
                ],
                "business_goal": "Improve enterprise knowledge discovery and reduce repeat support work across teams.",
                "expected_outcome": "Users can find trusted documentation quickly and support teams spend less time answering repeat questions.",
                "application_indicator": "New application",
                "assumptions": [
                    "The required documents already exist in approved knowledge repositories.",
                    "The team can integrate with the current document indexing pipeline."
                ],
                "constraints": [
                    "Delivery must fit within the next 8-week sprint.",
                    "No additional major licensing costs should be introduced.",
                    "Current security and access controls must remain in place."
                ],
                "users": [
                    "Employees",
                    "Support Engineers",
                    "Operations Teams"
                ]
            }
        }

        page = mock_pages.get(page_id)
        if page is None:
            raise ValueError(f"No mock Confluence page found for page_id='{page_id}'")

        return page


class ConfluenceContextService:
    """Service responsible for retrieving Confluence page context and normalizing it."""

    def __init__(self, adapter: ConfluenceContextAdapter | None = None):
        self.adapter = adapter or MockConfluenceContextAdapter()

    def fetch_page(self, page_id: str, space_key: str | None = None) -> dict[str, Any]:
        raw_page = self.adapter.fetch_page(page_id=page_id, space_key=space_key)
        return self._normalize_page(raw_page)

    def _normalize_page(self, raw_page: dict[str, Any]) -> dict[str, Any]:
        evidence = raw_page.get("supporting_evidence") or raw_page.get("evidence") or []
        if isinstance(evidence, str):
            evidence = [evidence]

        assumptions = raw_page.get("assumptions") or []
        constraints = raw_page.get("constraints") or []
        if isinstance(assumptions, str):
            assumptions = [assumptions]
        if isinstance(constraints, str):
            constraints = [constraints]

        users = raw_page.get("users") or []
        if isinstance(users, str):
            users = [users]

        normalized = {
            "page_id": raw_page.get("page_id"),
            "space_key": raw_page.get("space_key"),
            "title": raw_page.get("title"),
            "problem_statement": raw_page.get("problem_statement") or "",
            "supporting_evidence": evidence,
            "business_goal": raw_page.get("business_goal") or raw_page.get("expected_outcome") or "",
            "expected_outcome": raw_page.get("expected_outcome") or "",
            "application_indicator": raw_page.get("application_indicator") or "Unknown",
            "assumptions": assumptions,
            "constraints": constraints,
            "users": users,
            "links": raw_page.get("links") or [],
            "raw_notes": raw_page.get("raw_notes") or [],
        }

        return normalized

    def to_requirement_context(self, page_id: str, space_key: str | None = None) -> dict[str, Any]:
        page = self.fetch_page(page_id=page_id, space_key=space_key)

        return {
            "problem_statement": page.get("problem_statement") or "",
            "business_goal": page.get("business_goal") or "",
            "expected_outcome": page.get("expected_outcome") or "",
            "evidence": page.get("supporting_evidence") or [],
            "links": page.get("links") or [],
            "application_indicator": page.get("application_indicator") or "Unknown",
            "assumptions": page.get("assumptions") or [],
            "constraints": page.get("constraints") or [],
            "users": page.get("users") or [],
            "raw_notes": page.get("raw_notes") or [],
        }


MockConfluenceContextService = ConfluenceContextService
