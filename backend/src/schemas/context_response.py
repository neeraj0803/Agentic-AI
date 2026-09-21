from pydantic import BaseModel
from typing import List


class ContextAnalyzerResponse(BaseModel):
    problem_statement: str
    business_goal: str
    evidence: List[str]
    users: List[str]
    assumptions: List[str]
    constraints: List[str]

