from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class JiraIssueRequest(BaseModel):
    issue_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Jira issue key, such as PROJ-123",
    )

    @field_validator("issue_key")
    @classmethod
    def strip_issue_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Issue key must not be blank")
        return value


class JiraIssueData(BaseModel):
    issue_key: str
    issue_id: str
    title: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    reporter: str | None = None
    description: str = ""
    acceptance_criteria: str = ""


class JiraIssueResponse(BaseModel):
    success: bool = True
    data: JiraIssueData


class JiraIssueCreate(BaseModel):
    issue_type: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    children: list["JiraIssueCreate"] = Field(default_factory=list)

    @field_validator("issue_type", "summary")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Issue type and summary must not be blank")
        return value

    @field_validator("fields")
    @classmethod
    def reject_managed_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        managed_fields = {"project", "issuetype", "summary", "description", "parent"}
        conflicts = managed_fields.intersection(key.casefold() for key in value)
        if conflicts:
            raise ValueError(
                "The fields object cannot override managed fields: "
                + ", ".join(sorted(conflicts))
            )
        return value


class JiraWritebackRequest(BaseModel):
    project_key: str = Field(..., min_length=1, max_length=100)
    items: list[JiraIssueCreate] = Field(..., min_length=1)
    epic_link_field_id: str | None = Field(
        default=None,
        description=(
            "Optional Jira custom field ID for linking non-subtask issues "
            "directly under an Epic, for example customfield_10014."
        ),
        pattern=r"^customfield_\d+$",
    )

    @field_validator("project_key")
    @classmethod
    def strip_project_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project key must not be blank")
        return value

    @model_validator(mode="after")
    def limit_issue_count(self) -> "JiraWritebackRequest":
        def count_items(items: list[JiraIssueCreate]) -> int:
            return sum(1 + count_items(item.children) for item in items)

        if count_items(self.items) > 100:
            raise ValueError("A write-back request cannot contain more than 100 issues")
        return self


class JiraCreatedIssue(BaseModel):
    issue_key: str
    issue_id: str
    issue_type: str
    summary: str
    parent_key: str | None = None
    children: list["JiraCreatedIssue"] = Field(default_factory=list)


class JiraWritebackResponse(BaseModel):
    success: bool = True
    project_key: str
    created_issue_count: int
    items: list[JiraCreatedIssue]
