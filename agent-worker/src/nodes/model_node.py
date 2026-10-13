import copy
import json
import logging
from pathlib import Path
from typing import Any, Callable

from openai import AzureOpenAI

from ..config import ROOT_DIR, get_llm_config_path

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


def _build_default_prompts(
    state: dict[str, Any],
    node_def: dict[str, Any] | None = None,
    workflow_spec: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Generates default system message and user prompt dynamically based on node definition and context."""
    node_id = (node_def or {}).get("id") or (node_def or {}).get("node_id") or "llm_node"
    node_name = (node_def or {}).get("name") or node_id.replace("_", " ").title()
    node_desc = (node_def or {}).get("description")
    wf_agent = (workflow_spec or {}).get("agent", {}) if isinstance(workflow_spec, dict) else {}
    agent_desc = wf_agent.get("description") or wf_agent.get("name") or "Workflow Intelligent Assistant"

    # If specifically a test generation node or has test in name, provide test guidance, otherwise generic task guidance
    if "test" in node_id.lower() or "test" in str(node_name).lower():
        system_message = (
            f"You are an expert AI Agent performing the '{node_name}' task for: {agent_desc}.\n"
            "Your task is to analyze the provided input context and produce a structured, thorough output.\n"
            "You must respond with a valid JSON object."
        )
    else:
        system_message = (
            f"You are an expert AI Agent performing the '{node_name}' task.\n"
            f"Context: {agent_desc}.\n"
            f"Objective: {node_desc or f'Process the accumulated inputs and execute the {node_name} operation.'}\n"
            "You must respond with a valid JSON object containing your structured findings, fields, and results."
        )

    context_payload = state.get("input_context") or state.get("validated_inputs") or state.get("context_data") or {}
    rework_feedback = state.get("rework_feedback", "")
    rework_section = f"\nReviewer Feedback to Address:\n{rework_feedback}\n" if rework_feedback else ""

    # Include any upstream node outputs
    upstream_summaries = []
    for node in state.get("nodes", []):
        nid = node.get("node_id") or node.get("id")
        if nid and nid != node_id and node.get("output") is not None:
            upstream_summaries.append(f"Output of [{nid}]:\n{json.dumps(node['output'], indent=2, default=str)}")

    upstream_section = ("\n\nUpstream Node Results:\n" + "\n".join(upstream_summaries)) if upstream_summaries else ""

    user_prompt = (
        f"Task: {node_name}\n"
        f"Input Context:\n{json.dumps(context_payload, indent=2, default=str)}"
        f"{upstream_section}"
        f"{rework_section}\n\n"
        f"Perform the analysis and return the complete results as a JSON object."
    )

    return system_message, user_prompt


def _format_prompt_template(template: str, state: dict[str, Any]) -> str:
    """Safely formats prompt template with state values."""
    context_payload = state.get("input_context") or state.get("validated_inputs") or {}
    context_str = json.dumps(context_payload, indent=2, default=str) if isinstance(context_payload, (dict, list)) else str(context_payload)

    replacements = {
        "{input_context}": context_str,
        "{context}": context_str,
        "{user_stories}": json.dumps(state.get("user_stories", []), indent=2, default=str),
        "{context_brief}": str(state.get("context_brief", "")),
        "{rework_feedback}": state.get("rework_feedback", ""),
        "{story_id}": str(state.get("validated_inputs", {}).get("jira_story_or_epic_id", "")),
        "{status}": str(state.get("status", "")),
    }

    formatted = template
    for key, val in replacements.items():
        formatted = formatted.replace(key, val)
    return formatted


def _fallback_test_cases(state: dict[str, Any]) -> dict[str, Any]:
    """Provides fallback test cases if LLM is offline or blocked."""
    validated = state.get("validated_inputs")
    input_ctx = state.get("input_context")

    def _resolve_field(field_names: list[str], default: str = "") -> str:
        for src in [validated, input_ctx]:
            if isinstance(src, dict):
                for fn in field_names:
                    if src.get(fn):
                        return str(src[fn])
            elif isinstance(src, list) and src:
                for item in src:
                    if isinstance(item, dict):
                        for fn in field_names:
                            if item.get(fn):
                                return str(item[fn])
        return default

    story_id = _resolve_field(["jira_story_or_epic_id", "id", "key", "story_id", "reference_id"], "CHK-100")
    scope = _resolve_field(["test_scope_and_type", "test_scope", "scope"], "functional_and_negative")
    target_env = _resolve_field(["target_application_and_env", "target_env", "env"], "Staging")

    return {
        "story_id": story_id,
        "test_scope": scope,
        "target_application_and_env": target_env,
        "manual_test_cases": [
            {
                "test_id": f"TC-{story_id}-001",
                "title": f"Positive: Validate core workflow for {story_id}",
                "type": "positive",
                "priority": "P1",
                "pre_conditions": "Service is healthy and test credentials are active.",
                "steps": [
                    "1. Submit valid payload according to API specifications.",
                    "2. Verify HTTP 200 response with correct correlation headers."
                ],
                "expected_result": "Payload is processed successfully with compliant output.",
                "ac_covered": "AC-1",
            },
            {
                "test_id": f"TC-{story_id}-002",
                "title": f"Boundary: Test extreme limits and special characters",
                "type": "boundary",
                "priority": "P2",
                "pre_conditions": "Input validator configured with standard boundary limits.",
                "steps": [
                    "1. Send maximum allowed payload size with boundary characters.",
                    "2. Check response payload and memory consumption."
                ],
                "expected_result": "Input is handled cleanly without memory leaks or truncation errors.",
                "ac_covered": "AC-2",
            },
            {
                "test_id": f"TC-{story_id}-003",
                "title": f"Negative: Malformed payload and missing required fields",
                "type": "negative",
                "priority": "P1",
                "pre_conditions": "API endpoint accessible.",
                "steps": [
                    "1. Submit JSON with omitted mandatory attributes.",
                    "2. Validate HTTP 400 Bad Request error response code."
                ],
                "expected_result": "400 error returned with descriptive field validation messages.",
                "ac_covered": "AC-1",
            },
            {
                "test_id": f"TC-{story_id}-004",
                "title": f"Resilience: Timeout and downstream service failure",
                "type": "negative",
                "priority": "P2",
                "pre_conditions": "Downstream mock configured to delay >100ms or fail 500.",
                "steps": [
                    "1. Trigger request when downstream dependency times out.",
                    "2. Verify fallback or retry policy triggers cleanly."
                ],
                "expected_result": "Circuit breaker or retry policy executes without uncaught exceptions.",
                "ac_covered": "AC-3",
            },
            {
                "test_id": f"TC-{story_id}-005",
                "title": f"Regression: Verify existing upstream APIs and backward compatibility",
                "type": "regression",
                "priority": "P2",
                "pre_conditions": "Baseline test suite ready.",
                "steps": [
                    "1. Execute baseline integration tests.",
                    "2. Confirm zero regressions in existing workflows."
                ],
                "expected_result": "All baseline regression tests pass with 100% parity.",
                "ac_covered": "REG-1",
            },
            {
                "test_id": f"TC-{story_id}-006",
                "title": f"NFR: Latency and throughput verification under concurrency",
                "type": "performance",
                "priority": "P3",
                "pre_conditions": "Staging environment with telemetry enabled.",
                "steps": [
                    "1. Apply concurrent user load of 250 requests/sec.",
                    "2. Monitor p95 latency and error rate."
                ],
                "expected_result": "p95 latency remains within acceptable threshold with 0% error rate.",
                "ac_covered": "NFR-1",
            },
        ],
        "requirement_traceability_matrix": [
            {"ac_id": "AC-1", "test_case_ids": [f"TC-{story_id}-001", f"TC-{story_id}-003"], "coverage": "100%"},
            {"ac_id": "AC-2", "test_case_ids": [f"TC-{story_id}-002"], "coverage": "100%"},
            {"ac_id": "AC-3", "test_case_ids": [f"TC-{story_id}-004"], "coverage": "100%"},
            {"ac_id": "REG-1", "test_case_ids": [f"TC-{story_id}-005"], "coverage": "100%"},
            {"ac_id": "NFR-1", "test_case_ids": [f"TC-{story_id}-006"], "coverage": "100%"},
        ],
        "regression_scope": {
            "critical_modules": ["Gateway", "Validation", "Downstream-Connector"],
            "suggested_regression_tests": [f"TC-{story_id}-005"],
        },
        "assumptions_and_gaps": [
            "Downstream API contract is versioned and backward compatible.",
            "Test credentials for staging environment have required RBAC permissions."
        ],
    }


def create_llm_node(
    node_def: dict[str, Any], workflow_spec: dict[str, Any]
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Factory creating a dynamic LLM call node with configurable system message, prompt, and model settings."""
    node_id = node_def.get("id") or node_def.get("node_id") or "test_cases_generation"
    custom_system = node_def.get("system_message") or node_def.get("system_prompt")
    custom_user = node_def.get("user_prompt") or node_def.get("prompt")
    custom_config_path = Path(node_def["llm_config_path"]) if "llm_config_path" in node_def else None
    response_format = node_def.get("response_format", "json_object")
    output_key = node_def.get("output_key", "drafted_tests")
    temperature_override = node_def.get("temperature")

    def llm_node(state: dict[str, Any]) -> dict[str, Any]:
        state["status"] = "running"
        state["current_node"] = node_id

        # 1. Build dynamic system message and user prompt
        default_sys, default_usr = _build_default_prompts(state, node_def, workflow_spec)
        system_msg = custom_system if custom_system else default_sys
        user_msg = _format_prompt_template(custom_user, state) if custom_user else default_usr

        # Ensure prompt contains 'json' when response_format is json_object
        if response_format == "json_object":
            if "json" not in system_msg.lower() and "json" not in user_msg.lower():
                system_msg = f"{system_msg}\nYou must respond with a valid JSON object."

        # 2. Load LLM configuration
        llm_cfg = load_llm_config(custom_config_path)
        api_details = llm_cfg.get("apiDetails", {})
        api_key = api_details.get("apiKey")
        api_version = api_details.get("apiVersion", "2025-01-01-preview")
        base_url = api_details.get("baseURL")
        deployment_name = api_details.get("deploymentName", "gpt-4o-mini-developers")
        temperature = (
            float(temperature_override)
            if temperature_override is not None
            else float(api_details.get("temperature", 0.1))
        )

        llm_result: Any = None
        source_engine = "azure_openai"

        # 3. Call Azure OpenAI if configured
        if api_key and base_url:
            try:
                client = AzureOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=base_url,
                )
                call_kwargs: dict[str, Any] = {
                    "model": deployment_name,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": temperature,
                }
                if response_format == "json_object":
                    call_kwargs["response_format"] = {"type": "json_object"}

                response = client.chat.completions.create(**call_kwargs)
                raw_content = response.choices[0].message.content or ""

                if response_format == "json_object":
                    try:
                        llm_result = json.loads(raw_content)
                    except json.JSONDecodeError:
                        llm_result = {"raw_response": raw_content}
                else:
                    llm_result = raw_content

                logger.info("Node '%s': LLM call completed successfully via %s", node_id, deployment_name)
            except Exception as exc:
                logger.warning("Node '%s': LLM call failed or network blocked (%s). Falling back.", node_id, exc)
                source_engine = f"fallback (error: {exc})"
                llm_result = _fallback_test_cases(state)
        else:
            source_engine = "fallback (no api credentials)"
            llm_result = _fallback_test_cases(state)

        # 4. Save to state dynamically
        state[output_key] = llm_result
        if output_key == "drafted_tests" or node_id == "test_cases_generation":
            state["drafted_tests"] = llm_result
        state[f"{node_id}_output"] = llm_result

        node_output = {
            "status": "completed",
            "node_id": node_id,
            "engine": source_engine,
            "system_message_len": len(system_msg),
            "user_prompt_len": len(user_msg),
            "output": llm_result,
        }

        if "nodes" not in state or not isinstance(state["nodes"], list):
            state["nodes"] = []

        found = False
        for item in state.get("nodes", []):
            if item.get("node_id") == node_id or item.get("id") == node_id:
                item["output"] = node_output
                item["status"] = "completed"
                found = True
                break
        if not found:
            state["nodes"].append({
                "id": node_id,
                "node_id": node_id,
                "node_name": str(node_id).replace("_", " ").title(),
                "node_type": "agent",
                "output": node_output,
                "status": "completed",
            })

        return state


    return llm_node


# Export alias for compatibility
create_model_node = create_llm_node

