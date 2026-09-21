from typing import TypedDict


class PRDState(TypedDict, total=False):
    document_name: str
    extracted_text: str
    problem_statement: str
    business_goal: str
    evidence: list[str]
    users: list[str]
    assumptions: list[str]
    constraints: list[str]