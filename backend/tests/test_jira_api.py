import asyncio
import base64
import json
import unittest
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError

from src.api.jira_api import fetch_jira_issue_by_key
from src.config import settings
from src.schemas.jira_schema import JiraIssueRequest


class TestJiraIssueAPI(unittest.TestCase):
    def setUp(self):
        self.settings_patcher = mock.patch.multiple(
            settings.jira,
            base_url="https://api.atlassian.com/ex/jira/",
            email="jira@example.com",
            api_token="test-token",
            cloud_id="cloud-id",
        )
        self.settings_patcher.start()
        self.addCleanup(self.settings_patcher.stop)

    def test_fetches_issue_and_returns_typed_response(self):
        jira_issue = {
            "id": "10001",
            "key": "PROJ-7",
            "fields": {
                "summary": "Checkout retry",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Alex"},
                "reporter": {"displayName": "Sam"},
                "customfield_10042": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Given a shopper has items in their cart",
                                }
                            ],
                        },
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "When checkout is retried",
                                }
                            ],
                        },
                    ],
                },
                "description": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "First line"}],
                        },
                        {
                            "type": "bulletList",
                            "content": [
                                {
                                    "type": "listItem",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "Nested line"}
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
            },
            "names": {"customfield_10042": "Acceptance Criteria"},
        }
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            jira_issue
        ).encode()

        with mock.patch(
            "src.services.jira_service.urllib.request.urlopen",
            return_value=response,
        ) as urlopen:
            result = asyncio.run(
                fetch_jira_issue_by_key(
                    JiraIssueRequest(issue_key="  PROJ-7  ")
                )
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.atlassian.com/ex/jira/cloud-id/"
            "rest/api/3/issue/PROJ-7?expand=names",
        )
        self.assertEqual(
            request.get_header("Authorization"),
            "Basic "
            + base64.b64encode(b"jira@example.com:test-token").decode(),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data.issue_id, "10001")
        self.assertEqual(result.data.status, "In Progress")
        self.assertEqual(result.data.description, "First line\nNested line")
        self.assertEqual(
            result.data.acceptance_criteria,
            "Given a shopper has items in their cart\nWhen checkout is retried",
        )

    def test_acceptance_criteria_is_empty_when_jira_field_is_missing(self):
        issue = {
            "id": "10001",
            "key": "PROJ-7",
            "fields": {"summary": "Checkout retry"},
            "names": {},
        }

        with mock.patch(
            "src.services.jira_service._fetch_issue_response",
            return_value=json.dumps(issue).encode(),
        ):
            result = asyncio.run(
                fetch_jira_issue_by_key(JiraIssueRequest(issue_key="PROJ-7"))
            )

        self.assertEqual(result.data.acceptance_criteria, "")

    def test_rejects_blank_issue_key(self):
        with self.assertRaises(ValidationError):
            JiraIssueRequest(issue_key="   ")

    def test_missing_connector_configuration_returns_service_unavailable(self):
        with mock.patch.object(settings.jira, "api_token", None):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(
                    fetch_jira_issue_by_key(
                        JiraIssueRequest(issue_key="PROJ-7")
                    )
                )

        self.assertEqual(context.exception.status_code, 503)
