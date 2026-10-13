import copy
import json
import logging
from pathlib import Path
from typing import Any, Callable

from openai import AzureOpenAI

from ..config import get_llm_config_path, get_mock_input_path

logger = logging.getLogger(__name__)


def load_llm_config(config_path: Path | None = None) -> dict[str, Any]:
    target = config_path or get_llm_config_path()
    if target.exists():
        try:
            with target.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load LLM config from %s: %s", target, exc)
    return {}


def load_mock_input_context(mock_path: Path | None = None) -> Any:
    target = mock_path or get_mock_input_path()
    if target.exists():
        try:
            with target.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load mock input from %s: %s", target, exc)
    return []


def _rule_based_validate(input_defs: list[dict[str, Any]], input_context: Any) -> dict[str, Any]:
    """Fallback rule-based validation if LLM is unreachable."""
    comments: list[str] = []
    items = input_context if isinstance(input_context, list) else [input_context]

    for idx, item in enumerate(items):
        prefix = f"Entry [{idx}]: " if len(items) > 1 else ""
        if not isinstance(item, dict):
            comments.append(f"{prefix}Input context item is not a valid object.")
            continue

        for defn in input_defs:
            field_id = defn.get("id")
            if not field_id:
                continue

            val = item.get(field_id)
            is_required = defn.get("required", False)

            if is_required and (val is None or val == ""):
                comments.append(f"{prefix}Missing required input '{field_id}'.")

            allowed = defn.get("allowed_values")
            if allowed and val is not None and val != "" and val not in allowed:
                comments.append(
                    f"{prefix}Value '{val}' for '{field_id}' is not in allowed values: {allowed}."
                )

    approved = "true" if not comments else "false"
    return {
        "approved": approved,
        "comments": comments,
    }


def _llm_validate(
    input_defs: list[dict[str, Any]],
    input_context: Any,
    llm_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Validates the input context against YAML input requirements using Azure OpenAI."""
    api_details = llm_cfg.get("apiDetails", {})
    api_key = api_details.get("apiKey")
    api_version = api_details.get("apiVersion", "2025-01-01-preview")
    base_url = api_details.get("baseURL")
    deployment_name = api_details.get("deploymentName", "gpt-4o-mini-developers")
    temperature = float(api_details.get("temperature", 0.1))

    if not api_key or not base_url:
        raise ValueError("Missing apiKey or baseURL in llm_model.json")

    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=base_url,
    )

    system_prompt = (
        "You are an input validation agent for a QE test generation workflow.\n"
        "Your task is to validate the provided Input-Context against the input requirements defined in the workflow YAML specification.\n\n"
        "Requirements:\n"
        "1. Check if all required inputs specified in the YAML schema are present in the Input-Context.\n"
        "2. For fields with 'allowed_values', verify that the provided values match one of the allowed options.\n"
        "3. If the Input-Context is a list, validate the input entries against the schema.\n"
        "4. If all required inputs are present and valid, approve the input context.\n"
        "5. If any required input is missing or invalid, do not approve and provide detailed comments explaining what is missing or invalid.\n\n"
        "You must respond ONLY with valid JSON in this exact structure:\n"
        "{\n"
        '  "approved": "true",\n'
        '  "comments": []\n'
        "}\n\n"
        "If not approved:\n"
        "{\n"
        '  "approved": "false",\n'
        '  "comments": [\n'
        '    "Explanation of missing or invalid input"\n'
        "  ]\n"
        "}\n"
        "Note: 'approved' must be a string (\"true\" or \"false\"). 'comments' must be a JSON array of strings."
    )

    user_prompt = (
        f"YAML Input Schema:\n{json.dumps(input_defs, indent=2)}\n\n"
        f"Input-Context to Validate:\n{json.dumps(input_context, indent=2)}\n\n"
        "Validate the Input-Context and return the JSON response:"
    )

    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    raw_content = response.choices[0].message.content or "{}"
    parsed = json.loads(raw_content)

    approved_val = parsed.get("approved")
    if isinstance(approved_val, bool):
        approved_str = "true" if approved_val else "false"
    else:
        approved_str = (
            "true"
            if str(approved_val).strip().lower() in {"true", "1", "yes"}
            else "false"
        )

    comments = parsed.get("comments", [])
    if not isinstance(comments, list):
        comments = [str(comments)] if comments else []

    return {
        "approved": approved_str,
        "comments": [str(c) for c in comments],
    }


def create_validation_node(
    node_def: dict[str, Any], workflow_spec: dict[str, Any]
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    node_id = node_def.get("id") or node_def.get("node_id") or "validate_inputs"

    def validation_node(state: dict[str, Any]) -> dict[str, Any]:
        state["status"] = "running"
        state["current_node"] = node_id

        # 1. Resolve Input-Context: keep from Mock-Input as mock input context of the whole flow
        input_context = state.get("input_context")
        if not input_context:
            raw_inputs = state.get("inputs")
            if isinstance(raw_inputs, (list, dict)) and raw_inputs:
                input_context = raw_inputs
            else:
                input_context = load_mock_input_context()

        # Persist Input-Context in workflow state across the entire flow
        state["input_context"] = input_context

        # Set active validated_inputs for downstream nodes (using primary story entry)
        if isinstance(input_context, list) and input_context:
            primary_inputs = copy.deepcopy(input_context[0])
        elif isinstance(input_context, dict):
            primary_inputs = copy.deepcopy(input_context)
        else:
            primary_inputs = {}

        state["validated_inputs"] = primary_inputs

        # 2. Retrieve YAML input requirements
        input_defs = workflow_spec.get("inputs") or state.get("inputs") or []

        # 3. Perform validation via LLM using llm_model.json
        llm_cfg = load_llm_config()
        validation_result: dict[str, Any]

        try:
            validation_result = _llm_validate(input_defs, input_context, llm_cfg)
            logger.info("Validation completed via Azure OpenAI LLM: %s", validation_result)
        except Exception as exc:
            logger.warning("LLM validation failed or network blocked (%s). Falling back to schema validator.", exc)
            validation_result = _rule_based_validate(input_defs, input_context)

        approved_str = str(validation_result.get("approved", "false")).lower()
        is_approved = approved_str in {"true", "yes", "1"}

        formatted_output = {
            "approved": "true" if is_approved else "false",
            "comments": validation_result.get("comments", []),
        }

        # 4. Update workflow state and node tracking output
        if not is_approved:
            state["status"] = "failed"
            state.setdefault("errors", []).extend(formatted_output["comments"])

        for item in state.get("nodes", []):
            if item.get("node_id") == node_id or item.get("id") == node_id:
                item["output"] = formatted_output
                item["status"] = "completed" if is_approved else "failed"
                break

        return state

    return validation_node

