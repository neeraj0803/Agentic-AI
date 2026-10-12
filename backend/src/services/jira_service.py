import asyncio
import base64
import json
import logging
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

from ..config import settings
from ..schemas.jira_schema import (
    JiraCreatedIssue,
    JiraIssueCreate,
    JiraIssueData,
    JiraIssueResponse,
    JiraWritebackRequest,
    JiraWritebackResponse,
)


logger = logging.getLogger(__name__)


class JiraServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _fetch_issue_response(url: str, email: str, api_token: str) -> bytes:
    credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _create_issue_response(
    url: str,
    email: str,
    api_token: str,
    payload: dict[str, Any],
) -> bytes:
    credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _description_to_adf(description: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": line}] if line else [],
            }
            for line in description.splitlines() or [""]
        ],
    }


def _extract_text(content: Any) -> list[str]:
    if isinstance(content, str):
        return [content]

    if isinstance(content, list):
        return [
            text
            for item in content
            for text in _extract_text(item)
        ]

    if not isinstance(content, dict):
        return []

    if content.get("type") == "text":
        text = content.get("text")
        return [text] if isinstance(text, str) else []

    return _extract_text(content.get("content", []))


class JiraService:
    def _connector_details(self) -> tuple[str, str, str, str]:
        jira_base_url = settings.jira.base_url
        jira_email = settings.jira.email
        jira_api_token = settings.jira.api_token
        jira_cloud_id = settings.jira.cloud_id

        if (
            not jira_base_url
            or not jira_email
            or not jira_api_token
            or not jira_cloud_id
        ):
            raise JiraServiceError(
                status_code=503,
                detail="Jira connector details are not configured",
            )

        return jira_base_url, jira_email, jira_api_token, jira_cloud_id

    async def fetch_issue_by_key(self, issue_key: str) -> JiraIssueResponse:
        jira_base_url, jira_email, jira_api_token, jira_cloud_id = (
            self._connector_details()
        )

        url = (
            f"{jira_base_url.rstrip('/')}/{quote(jira_cloud_id, safe='')}"
            f"/rest/api/3/issue/{quote(issue_key, safe='')}?expand=names"
        )

        try:
            response_body = await asyncio.to_thread(
                _fetch_issue_response,
                url,
                jira_email,
                jira_api_token,
            )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.warning(
                "Jira returned HTTP %s while fetching issue %s",
                exc.code,
                issue_key,
            )
            raise JiraServiceError(
                status_code=exc.code,
                detail=detail or "Jira request failed",
            ) from exc
        except urllib.error.URLError as exc:
            logger.exception("Unable to reach Jira while fetching issue %s", issue_key)
            raise JiraServiceError(
                status_code=502,
                detail="Unable to reach Jira",
            ) from exc

        try:
            issue_data = json.loads(response_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.exception("Jira returned invalid JSON for issue %s", issue_key)
            raise JiraServiceError(
                status_code=502,
                detail="Jira returned an invalid JSON response",
            ) from exc

        if not isinstance(issue_data, dict) or not isinstance(
            issue_data.get("fields"), dict
        ):
            raise JiraServiceError(
                status_code=502,
                detail="Jira returned an unexpected issue response",
            )

        fields = issue_data["fields"]
        names = issue_data.get("names")
        acceptance_criteria_key = None
        if isinstance(names, dict):
            acceptance_criteria_key = next(
                (
                    key
                    for key, name in names.items()
                    if isinstance(name, str)
                    and name.strip().casefold() == "acceptance criteria"
                ),
                None,
            )

        def display_name(field_name: str) -> str | None:
            value = fields.get(field_name)
            if isinstance(value, dict):
                name = value.get("displayName") or value.get("name")
                return name if isinstance(name, str) else None
            return None

        issue_id = issue_data.get("id")
        response_issue_key = issue_data.get("key")
        if not isinstance(issue_id, (str, int)) or not isinstance(
            response_issue_key, str
        ):
            raise JiraServiceError(
                status_code=502,
                detail="Jira returned an issue without an ID or key",
            )

        return JiraIssueResponse(
            data=JiraIssueData(
                issue_key=response_issue_key,
                issue_id=str(issue_id),
                title=fields.get("summary"),
                status=display_name("status"),
                priority=display_name("priority"),
                assignee=display_name("assignee"),
                reporter=display_name("reporter"),
                description="\n".join(_extract_text(fields.get("description", {}))),
                acceptance_criteria="\n".join(
                    _extract_text(fields.get(acceptance_criteria_key, {}))
                )
                if acceptance_criteria_key
                else "",
            )
        )

    async def writeback_issue_tree(
        self,
        payload: JiraWritebackRequest,
    ) -> JiraWritebackResponse:
        jira_base_url, jira_email, jira_api_token, jira_cloud_id = (
            self._connector_details()
        )
        url = (
            f"{jira_base_url.rstrip('/')}/{quote(jira_cloud_id, safe='')}"
            "/rest/api/3/issue"
        )
        created_keys: list[str] = []

        async def create_item(
            item: JiraIssueCreate,
            parent_key: str | None = None,
            parent_issue_type: str | None = None,
        ) -> JiraCreatedIssue:
            fields = dict(item.fields)
            fields.update(
                {
                    "project": {"key": payload.project_key},
                    "issuetype": {"name": item.issue_type},
                    "summary": item.summary,
                }
            )
            if item.description is not None:
                fields["description"] = _description_to_adf(item.description)

            if parent_key:
                parent_is_epic = (
                    parent_issue_type is not None
                    and parent_issue_type.casefold() == "epic"
                )
                is_subtask = item.issue_type.casefold() in {"sub-task", "subtask"}
                if parent_is_epic and not is_subtask and payload.epic_link_field_id:
                    fields[payload.epic_link_field_id] = parent_key
                else:
                    fields["parent"] = {"key": parent_key}

            try:
                response_body = await asyncio.to_thread(
                    _create_issue_response,
                    url,
                    jira_email,
                    jira_api_token,
                    {"fields": fields},
                )
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                logger.warning(
                    "Jira returned HTTP %s while creating issue %r",
                    exc.code,
                    item.summary,
                )
                raise JiraServiceError(
                    status_code=exc.code,
                    detail=detail or "Jira issue creation failed",
                ) from exc
            except urllib.error.URLError as exc:
                logger.exception(
                    "Unable to reach Jira while creating issue %r",
                    item.summary,
                )
                raise JiraServiceError(
                    status_code=502,
                    detail="Unable to reach Jira while creating issues",
                ) from exc

            try:
                issue_data = json.loads(response_body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.exception(
                    "Jira returned invalid JSON while creating issue %r",
                    item.summary,
                )
                raise JiraServiceError(
                    status_code=502,
                    detail="Jira returned an invalid JSON response while creating an issue",
                ) from exc

            issue_key = issue_data.get("key") if isinstance(issue_data, dict) else None
            issue_id = issue_data.get("id") if isinstance(issue_data, dict) else None
            if not isinstance(issue_key, str) or not isinstance(issue_id, (str, int)):
                raise JiraServiceError(
                    status_code=502,
                    detail="Jira created an issue but returned no valid issue ID or key",
                )

            created_keys.append(issue_key)
            created_issue = JiraCreatedIssue(
                issue_key=issue_key,
                issue_id=str(issue_id),
                issue_type=item.issue_type,
                summary=item.summary,
                parent_key=parent_key,
            )
            created_issue.children = [
                await create_item(
                    child,
                    parent_key=issue_key,
                    parent_issue_type=item.issue_type,
                )
                for child in item.children
            ]
            return created_issue

        try:
            created_items = [
                await create_item(item) for item in payload.items
            ]
        except JiraServiceError as exc:
            if created_keys:
                raise JiraServiceError(
                    status_code=exc.status_code,
                    detail=(
                        f"{exc.detail} Write-back stopped after creating "
                        f"{len(created_keys)} issue(s): {', '.join(created_keys)}"
                    ),
                ) from exc
            raise

        return JiraWritebackResponse(
            project_key=payload.project_key,
            created_issue_count=len(created_keys),
            items=created_items,
        )
