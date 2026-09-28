from typing import Any, Dict
from ..agents.prd_reviewer import PRDReviewerPrompt


class PRDReviewerService:
    """
    Executes automated PRD quality check against completeness and testability threshold.
    Corresponds to Step 6 (Run quality checks) in Agent Journey
    and Node G / Decision H (PRD Review Passed?) in flowchart.md.
    """

    def review(self, prd_markdown: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        return PRDReviewerPrompt.review(prd_markdown, context_data)

