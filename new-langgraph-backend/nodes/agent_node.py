import json
from pathlib import Path
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI

ROOT_DIR = Path(__file__).resolve().parent.parent
SESSION_DIR = ROOT_DIR / "temp dir"
LLM_CONFIG_PATH = ROOT_DIR / "llm_model.json"


def load_llm_config() -> dict[str, Any]:
    with LLM_CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file).get("apiDetails", {})


def build_llm_client() -> AzureChatOpenAI:
    config = load_llm_config()

    return AzureChatOpenAI(
        azure_endpoint=config.get("baseURL", ""),
        api_key=config.get("apiKey", ""),
        api_version=config.get("apiVersion", "2025-01-01-preview"),
        azure_deployment=config.get("deploymentName", ""),
        model=config.get("model", "gpt-4o-mini"),
        temperature=float(config.get("temperature", 0.1)),
        top_p=float(config.get("top_p", 0.1)),
    )


def render_template(template: str, context: dict[str, Any]) -> str:
    if not template:
        return ""

    result = template
    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False)
        elif value is None:
            rendered = ""
        else:
            rendered = str(value)
        result = result.replace(placeholder, rendered)

    return result


def build_context_from_state(state: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}

    context["workflow_session_id"] = state.get("workflow_session_id")
    context["status"] = state.get("status")
    context["current_node"] = state.get("current_node")

    documents = state.get("input_documents", [])
    if documents:
        first_doc = documents[0]
        context["document_name"] = first_doc.get("name")
        context["document_type"] = first_doc.get("type")
        context["document_content"] = first_doc.get("content")
        context["document_size_bytes"] = first_doc.get("size_bytes")

    return context


def save_session_file(workflow: dict[str, Any]) -> None:
    session_id = workflow.get("workflow_session_id", "session")
    workflow_type = workflow.get("type", "Agent")
    file_name = f"{session_id}-{workflow_type}.json"
    file_path = SESSION_DIR / file_name

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(workflow, file, indent=2, ensure_ascii=False)
        file.write("\n")


def update_node_output(state: dict[str, Any], node_id: str, output_value: Any) -> None:
    nodes = state.get("nodes", [])
    for node in nodes:
        if node.get("node_id") == node_id:
            node["output"] = output_value
            break

    save_session_file(state)


def create_agent_node(node: dict[str, Any]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def agent_node(state: dict[str, Any]) -> dict[str, Any]:
        try:
            node_id = node.get("node_id", "unknown-agent")
            variables = node.get("variables", {})

            state["status"] = "running"
            state["current_node"] = node_id
            save_session_file(state)

            context = build_context_from_state(state)
            system_message = render_template(
                str(variables.get("system_message", "")),
                context
            )
            user_prompt = render_template(
                str(variables.get("user_prompt", "")),
                context
            )

            llm = build_llm_client()

            response = llm.invoke([
                SystemMessage(content=system_message),
                HumanMessage(content=user_prompt),
            ])

            output_content = response.content if hasattr(response, "content") else str(response)

            update_node_output(state, node_id, output_content)
            state["status"] = "running"
            state["current_node"] = node_id
            save_session_file(state)

            return state

        except Exception as exc:
            state.setdefault("errors", []).append(f"{node.get('node_id', 'unknown-agent')}: {str(exc)}")
            state["status"] = "failed"
            state["current_node"] = node.get("node_id", "unknown-agent")
            save_session_file(state)
            return state

    return agent_node