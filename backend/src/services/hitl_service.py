from datetime import datetime, timezone
from typing import Any, Dict, Literal
from pydantic import BaseModel, Field


class HITLReviewDecision(BaseModel):
    reviewer_name: str = "Lead Product Owner"
    reviewer_role: str = "Product Owner / Business Analyst"
    decision: Literal["approve", "request_changes"]
    comments: str = Field(default="")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HITLService:
    """
    Handles Human-In-The-Loop review (BA / Product Owner).
    Corresponds to Step 6 (HITL Review) in flowchart.md and Agent Journey.
    """

    def process_review(
        self,
        prd_content: str,
        decision: str,
        reviewer_name: str = "Lead Product Owner",
        reviewer_role: str = "Product Owner / Business Analyst",
        comments: str = ""
    ) -> Dict[str, Any]:
        decision_clean = decision.strip().lower()
        if decision_clean not in ("approve", "request_changes"):
            raise ValueError(f"Invalid HITL decision: {decision}. Must be 'approve' or 'request_changes'.")

        is_approved = decision_clean == "approve"
        review_record = {
            "reviewer_name": reviewer_name,
            "reviewer_role": reviewer_role,
            "decision": decision_clean,
            "is_approved": is_approved,
            "comments": comments or ("Approved for production implementation and Confluence/Jira publishing." if is_approved else "Changes requested."),
            "reviewed_at": datetime.now(timezone.utc).isoformat()
        }
        return review_record

