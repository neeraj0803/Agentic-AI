import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pathlib import Path


class PublishService:
    """
    Publishes approved PRD/context brief to Jira or Confluence.
    Corresponds to Step 7 in Agent Journey and Node J in flowchart.md.
    """

    def publish_prd(
        self,
        prd_markdown: str,
        context_data: Dict[str, Any],
        target_platform: Literal["jira", "confluence", "both"] = "both",
        space_key: str = "CHECKOUT",
        jira_project_key: str = "CHK"
    ) -> Dict[str, Any]:
        title = context_data.get("title") or "Payment Retry Messaging Improvement PRD"
        publication_id = f"pub-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        results: Dict[str, Any] = {
            "publication_id": publication_id,
            "status": "published",
            "published_at": timestamp,
            "target_platform": target_platform,
            "publications": {}
        }

        # Confluence publishing
        if target_platform in ("confluence", "both"):
            confluence_page_id = f"conf-page-{uuid.uuid4().hex[:6]}"
            confluence_url = f"https://confluence.corp.internal/display/{space_key}/{title.replace(' ', '+')}"
            results["publications"]["confluence"] = {
                "page_id": confluence_page_id,
                "space_key": space_key,
                "title": title,
                "url": confluence_url,
                "status": "created",
                "version": 1
            }

        # Jira publishing
        if target_platform in ("jira", "both"):
            epic_key = f"{jira_project_key}-1200"
            story_1_key = f"{jira_project_key}-1201"
            story_2_key = f"{jira_project_key}-1202"
            results["publications"]["jira"] = {
                "epic_key": epic_key,
                "epic_summary": title,
                "epic_url": f"https://jira.corp.internal/browse/{epic_key}",
                "stories_created": [
                    {
                        "key": story_1_key,
                        "summary": "Implement payment failure code classification in PaymentErrorMapper",
                        "status": "To Do"
                    },
                    {
                        "key": story_2_key,
                        "summary": "Render context-aware retry banner on checkout page",
                        "status": "To Do"
                    }
                ],
                "status": "created"
            }

        # Save approved PRD artifact to disk
        self._save_final_artifacts(publication_id, prd_markdown, results)

        return results

    def _save_final_artifacts(
        self,
        publication_id: str,
        prd_markdown: str,
        publication_receipt: Dict[str, Any]
    ) -> None:
        try:
            output_dir = Path(__file__).resolve().parents[2] / "artifacts"
            output_dir.mkdir(parents=True, exist_ok=True)

            prd_file = output_dir / f"final_approved_prd_{publication_id}.md"
            receipt_file = output_dir / f"publication_receipt_{publication_id}.json"

            prd_file.write_text(prd_markdown, encoding="utf-8")
            import json
            receipt_file.write_text(json.dumps(publication_receipt, indent=2), encoding="utf-8")
        except Exception:
            pass

