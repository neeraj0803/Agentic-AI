import json

from ..state import PRDState

from ...services.llm_service import (
    LLMService
)

from ...agents.context_analyzer import ContextAnalyzerPrompt

def context_analyzer_node(
    state: PRDState
):

    prompt = (
        ContextAnalyzerPrompt.get_prompt()
        .format(
            document_text=state["extracted_text"]
        )
    )

    response = LLMService.generate(
        prompt
    )

    response = (
        response
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    extracted_context = json.loads(
        response
    )

    return {

        "problem_statement":
            extracted_context[
                "problem_statement"
            ],

        "business_goal":
            extracted_context[
                "business_goal"
            ],

        "evidence":
            extracted_context[
                "evidence"
            ],

        "users":
            extracted_context[
                "users"
            ],

        "assumptions":
            extracted_context[
                "assumptions"
            ],

        "constraints":
            extracted_context[
                "constraints"
            ]
    }