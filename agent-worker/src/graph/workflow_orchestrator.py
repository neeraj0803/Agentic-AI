import copy
import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command
from openai import AzureOpenAI

from ..config import ROOT_DIR, get_llm_config_path
from ..nodes.artifact_node import create_artifact_node
from ..nodes.connector_node import create_connector_node
from ..nodes.context_node import create_context_node
from ..nodes.hitl_node import create_hitl_node
from ..nodes.model_node import create_llm_node, create_model_node, load_llm_config
from ..nodes.skill_node import create_skill_node
from ..nodes.validation_node import create_validation_node
from ..session_manager import (
    init_workflow_session,
    save_session_file,
)
from .state import WorkflowNode, WorkflowState

logger = logging.getLogger(__name__)

CHECKPOINTER = MemorySaver()
load_or_create_session_file = init_workflow_session



def normalize_workflow_state(workflow: dict[str, Any]) -> WorkflowState:
    raw_nodes = workflow.get("nodes") or workflow.get("graph", {}).get("nodes", [])
    nodes_state: list[dict[str, Any]] = []
    for node in raw_nodes:
        node_id = node.get("id") or node.get("node_id")
        node_copy = dict(node)
        node_copy["node_id"] = node_id
        node_copy["id"] = node_id
        node_copy.setdefault("node_name", node.get("name") or node.get("node_name") or str(node_id).replace("_", " ").title())
        node_copy.setdefault("node_type", node.get("type") or node.get("node_type", "agent"))
        node_copy.setdefault("checkpoint", node.get("checkpoint"))
        node_copy.setdefault("status", node.get("status", "pending"))
        node_copy.setdefault("output", node.get("output"))
        nodes_state.append(node_copy)

    return {
        "conversation_id": workflow.get("conversation_id"),
        "workflow_session_id": workflow.get("workflow_session_id"),
        "workflow_id": workflow.get("workflow_id"),
        "version": workflow.get("version"),
        "type": "Agent",
        "status": workflow.get("status", "not_started"),
        "current_node": workflow.get("current_node", ""),
        "next_node": workflow.get("next_node", ""),
        "agent": workflow.get("agent", {}),
        "actors": workflow.get("actors", {}),
        "channels": workflow.get("channels", {}),
        "run_modes": workflow.get("run_modes", {}),
        "inputs": workflow.get("inputs", []),
        "input_context": workflow.get("input_context"),
        "validated_inputs": workflow.get("validated_inputs", {}),
        "intake": workflow.get("intake", {}),
        "context": workflow.get("context", {}),
        "context_data": workflow.get("context_data", {}),
        "skills": workflow.get("skills", {}),
        "context_brief": workflow.get("context_brief", {}),
        "model_policy_ref": workflow.get("model_policy_ref", "azure_standard_test_generation"),
        "drafted_tests": workflow.get("drafted_tests", {}),
        "artifacts": workflow.get("artifacts", {}),
        "artifact_path": workflow.get("artifact_path", ""),
        "artifact_file": workflow.get("artifact_file", ""),
        "artifact_content": workflow.get("artifact_content", ""),
        "rework_count": workflow.get("rework_count", 0),
        "rework_feedback": workflow.get("rework_feedback", ""),
        "review_history": workflow.get("review_history", []),
        "publish_result": workflow.get("publish_result", {}),
        "graph": workflow.get("graph", {}),
        "nodes": nodes_state,
        "edges": workflow.get("graph", {}).get("edges", []) or workflow.get("edges", []),
        "outputs": workflow.get("outputs", {}),
        "failure_policy": workflow.get("failure_policy", {}),
        "errors": workflow.get("errors", []),
    }



def get_checkpoint_nodes(raw_nodes: list[dict[str, Any]]) -> list[str]:
    """Returns list of node IDs where checkpoint is True, excluding the last node."""
    if not raw_nodes or len(raw_nodes) <= 1:
        return []
    checkpoint_nodes: list[str] = []
    for node in raw_nodes[:-1]:
        nid = node.get("id") or node.get("node_id")
        cp = node.get("checkpoint")
        if cp is True or str(cp).lower() in {"true", "after", "before_and_after"}:
            if nid:
                checkpoint_nodes.append(nid)
    return checkpoint_nodes


def _heuristic_feedback_interpretation(
    feedback: str,
    current_node: str,
    node_ids: list[str],
    next_node: str | None,
) -> dict[str, Any]:
    """Deterministic fallback for interpreting feedback if LLM is unreachable."""
    fb = feedback.lower().strip()
    first_node = node_ids[0] if node_ids else ""

    if any(w in fb for w in ["whole workflow", "from start", "beginning", "restart", "start over", "run again from start", "run the whole"]):
        return {
            "action": "restart",
            "target_node": first_node,
            "reasoning": "Feedback indicated running the whole workflow again from start.",
        }

    m = re.search(r"(\d+)(?:st|nd|rd|th)?\s*node", fb)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(node_ids):
            return {
                "action": "run_from_node",
                "target_node": node_ids[idx],
                "reasoning": f"Feedback specified node position {idx + 1} ({node_ids[idx]}).",
            }

    word_map = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}
    for word, idx in word_map.items():
        if f"{word} node" in fb:
            if 0 <= idx < len(node_ids):
                return {
                    "action": "run_from_node",
                    "target_node": node_ids[idx],
                    "reasoning": f"Feedback specified '{word} node' ({node_ids[idx]}).",
                }

    for nid in node_ids:
        if nid.lower() in fb or nid.replace("_", " ").lower() in fb:
            return {
                "action": "run_from_node",
                "target_node": nid,
                "reasoning": f"Feedback mentioned specific node '{nid}'.",
            }

    if any(w in fb for w in ["retry", "rework", "run this again", "same node"]):
        return {
            "action": "rework_current",
            "target_node": current_node or first_node,
            "reasoning": f"Feedback requested rework of current node '{current_node}'.",
        }

    return {
        "action": "proceed",
        "target_node": next_node or first_node,
        "reasoning": "Feedback indicated approval or continuation to the next node.",
    }


def interpret_human_feedback(
    feedback: str,
    current_node: str,
    raw_nodes: list[dict[str, Any]],
    next_node: str | None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Uses Azure OpenAI to understand human feedback and decide the target node."""
    node_ids = [n.get("id") or n.get("node_id") for n in raw_nodes if (n.get("id") or n.get("node_id"))]
    first_node = node_ids[0] if node_ids else ""
    node_listing = "\n".join(f"{idx + 1}. {nid}" for idx, nid in enumerate(node_ids))

    system_prompt = (
        "You are an expert workflow orchestrator reasoning engine.\n"
        "A workflow paused after executing a node because a human-in-the-loop checkpoint was reached.\n"
        "Analyze the user's feedback text and determine what action to take and which node to run next.\n\n"
        f"Available Workflow Nodes (in sequential order):\n{node_listing}\n\n"
        "Decision Guidelines:\n"
        "1. PROCEED: If the user approves, says 'ok', 'okay', 'proceed', 'looks good', 'continue', or provides positive feedback to move on:\n"
        f"   action = 'proceed', target_node = '{next_node or node_ids[-1]}'\n"
        "2. RESTART: If the user says 'run again', 'restart', 'start over', 'rerun from beginning', 'we need to run the whole workflow again':\n"
        f"   action = 'restart', target_node = '{first_node}'\n"
        "3. RUN FROM SPECIFIC NODE: If the user specifies a node by position or name (e.g., 'run from 2nd node', 'start from 3rd node', 'rerun skill_retriever', 'jump to node 4'):\n"
        "   action = 'run_from_node', target_node = <exact node_id string from the list above>\n"
        "4. REWORK CURRENT: If the user asks to redo or adjust the current node itself (e.g., 'rework this', 'try again with different prompt'):\n"
        f"   action = 'rework_current', target_node = '{current_node}'\n\n"
        "Respond ONLY with a valid JSON object matching this schema:\n"
        "{\n"
        '  "action": "proceed" | "restart" | "run_from_node" | "rework_current",\n'
        '  "target_node": "<exact node_id from the available list>",\n'
        '  "reasoning": "<short explanation of why this was chosen>"\n'
        "}"
    )

    user_prompt = (
        f"Current completed node: {current_node}\n"
        f"Default next node: {next_node}\n"
        f"User feedback text: \"{feedback}\"\n\n"
        "Classify and return the JSON decision:"
    )

    try:
        llm_cfg = load_llm_config(config_path)
        api_details = llm_cfg.get("apiDetails", {})
        api_key = api_details.get("apiKey")
        base_url = api_details.get("baseURL")
        api_version = api_details.get("apiVersion", "2025-01-01-preview")
        deployment_name = api_details.get("deploymentName", "gpt-4o-mini-developers")

        if api_key and base_url:
            client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=base_url,
            )
            response = client.chat.completions.create(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
            raw = (response.choices[0].message.content or "").strip()
            if raw.startswith("```json") and raw.endswith("```"):
                raw = raw[7:-3].strip()
            elif raw.startswith("```") and raw.endswith("```"):
                raw = raw[3:-3].strip()

            parsed = json.loads(raw)
            target = str(parsed.get("target_node", "")).strip()

            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(node_ids):
                    target = node_ids[idx]

            if target not in node_ids:
                matched = next((nid for nid in node_ids if target.lower() in nid.lower()), None)
                target = matched or next_node or first_node

            parsed["target_node"] = target
            return parsed
    except Exception as exc:
        logger.warning("LLM feedback interpretation call failed (%s). Using heuristic fallback.", exc)

    return _heuristic_feedback_interpretation(feedback, current_node, node_ids, next_node)


def passthrough_node(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    node_id = node.get("id") or node.get("node_id") or "unknown-node"
    state["status"] = "running"
    state["current_node"] = node_id

    output = {
        "node_id": node_id,
        "node_type": node.get("type") or node.get("node_type"),
        "status": "completed",
    }
    for item in state.get("nodes", []):
        if item.get("node_id") == node_id or item.get("id") == node_id:
            item["output"] = output
            item["status"] = "completed"
            break

    save_session_file(state)
    return state


def build_workflow_orchestration(
    workflow: dict[str, Any], entry_node: str | None = None
) -> StateGraph:
    graph = StateGraph(WorkflowState)

    template = {}
    graph_def = workflow.get("graph", {})
    raw_nodes = graph_def.get("nodes", []) or workflow.get("nodes", [])
    raw_edges = graph_def.get("edges", []) or workflow.get("edges", [])

    all_node_ids = [
        (n.get("id") or n.get("node_id"))
        for n in raw_nodes
        if (n.get("id") or n.get("node_id"))
    ]

    for node in raw_nodes:
        node_id = node.get("id") or node.get("node_id")
        if not node_id:
            continue

        node_type = (node.get("type") or node.get("node_type") or "").lower()

        if node_type in {"validation", "validation_call"}:
            graph.add_node(node_id, create_validation_node(node, workflow))
        elif node_type in {"context_call", "context_engine_call", "context_engine", "context"}:
            graph.add_node(node_id, create_context_node(node, workflow))
        elif node_type in {"skill_call", "skill"}:
            graph.add_node(node_id, create_skill_node(node, workflow))
        elif node_type in {"llm_call", "model_call", "llm", "model"}:
            graph.add_node(node_id, create_llm_node(node, workflow))
        elif node_type in {"artifact_call", "artifact", "artefact_call", "artefact"}:
            graph.add_node(node_id, create_artifact_node(node, workflow))
        elif node_type in {"human_approval", "hitl", "human", "approval"}:
            graph.add_node(node_id, create_hitl_node(node, workflow))
        elif node_type in {"rest_connector_write", "connector"}:
            graph.add_node(node_id, create_connector_node(node, workflow))
        else:
            graph.add_node(
                node_id,
                lambda state, current_node=node: passthrough_node(state, current_node),
            )

    edges_from_map: dict[str, str] = {}
    if raw_edges:
        for edge in raw_edges:
            src = edge.get("from")
            dst = edge.get("to")
            if src and dst:
                edges_from_map[src] = dst
    else:
        for node in raw_nodes:
            src = node.get("id") or node.get("node_id")
            dst = node.get("next_node")
            if src and dst:
                edges_from_map[src] = dst

    for node in raw_nodes:
        node_id = node.get("id") or node.get("node_id")
        if not node_id:
            continue

        node_type = (node.get("type") or node.get("node_type") or "").lower()
        destination = edges_from_map.get(node_id)
        target = destination if destination and destination.lower() != "end" else END

        if node_type in {"human_approval", "hitl", "human", "approval"}:
            configured_rework = node.get("rework_resume_to", "")
            if configured_rework in all_node_ids:
                rework_target = configured_rework
            else:
                candidate = next(
                    (nid for nid in all_node_ids if nid == "test_cases_generation" or "test_case" in nid or "draft" in nid),
                    None,
                )
                if not candidate:
                    for n in raw_nodes:
                        nt = (n.get("type") or n.get("node_type") or "").lower()
                        if nt in {"llm_call", "model_call", "llm", "model"}:
                            candidate = n.get("id") or n.get("node_id")
                            break
                rework_target = candidate if candidate else (all_node_ids[0] if all_node_ids else END)

            graph.add_conditional_edges(
                node_id,
                lambda state, current_node_id=node_id: (
                    "approved"
                    if any(
                        (item.get("node_id") == current_node_id or item.get("id") == current_node_id)
                        and isinstance(item.get("output"), dict)
                        and item["output"].get("approved") is True
                        for item in state.get("nodes", [])
                    )
                    else (
                        "rework"
                        if any(
                            (item.get("node_id") == current_node_id or item.get("id") == current_node_id)
                            and isinstance(item.get("output"), dict)
                            and item["output"].get("rework") is True
                            for item in state.get("nodes", [])
                        )
                        else "rejected"
                    )
                ),
                {
                    "approved": target,
                    "rework": rework_target,
                    "rejected": END,
                },
            )
        elif target != END:
            graph.add_edge(node_id, target)
        else:
            graph.add_edge(node_id, END)

    first_node = (raw_nodes[0].get("id") or raw_nodes[0].get("node_id")) if raw_nodes else None
    chosen_entry = entry_node if (entry_node and entry_node in all_node_ids) else first_node
    if chosen_entry:
        graph.set_entry_point(chosen_entry)

    return graph


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def stream_workflow(
    compiled_graph: Any,
    initial_state: WorkflowState | Command,
    config: dict[str, Any],
):
    final_state: dict[str, Any] = {}
    active_node = ""
    last_completed_node = ""

    try:
        for mode, chunk in compiled_graph.stream(
            initial_state,
            config=config,
            stream_mode=["debug", "values"],
        ):
            if mode == "values":
                final_state = chunk
                continue

            event_type = chunk.get("type")
            payload = chunk.get("payload", {})
            node_id = payload.get("name", "unknown-node")

            if event_type == "task":
                active_node = node_id
                yield sse("node_start", {"node_id": node_id})
            elif event_type == "task_result":
                if payload.get("interrupts"):
                    continue

                error = payload.get("error")
                if error:
                    yield sse("node_error", {"node_id": node_id, "error": str(error)})
                    return

                result = payload.get("result", {})
                node_outputs = result.get("nodes", []) if isinstance(result, dict) else []
                node_output = next(
                    (
                        node.get("output")
                        for node in node_outputs
                        if isinstance(node, dict) and (node.get("node_id") == node_id or node.get("id") == node_id)
                    ),
                    None,
                )
                if node_output is None and isinstance(result, dict):
                    if f"{node_id}_output" in result:
                        node_output = result[f"{node_id}_output"]
                    elif node_id in result:
                        node_output = result[node_id]
                    elif "artifacts" in result and ("artifact" in node_id or "package" in node_id):
                        node_output = result.get("artifacts")
                    elif "drafted_tests" in result and "test" in node_id:
                        node_output = result.get("drafted_tests")
                    elif "output" in result:
                        node_output = result.get("output")

                yield sse("node_complete", {"node_id": node_id, "output": node_output})
                last_completed_node = node_id
                active_node = ""


        snapshot = compiled_graph.get_state(config)

        # 1. Check if paused at an interrupt_after checkpoint
        if snapshot.next:
            final_state = dict(snapshot.values)
            paused_at = last_completed_node or active_node
            next_node = snapshot.next[0]
            final_state["status"] = "waiting_for_human"
            final_state["current_node"] = paused_at
            final_state["next_node"] = next_node
            save_session_file(final_state)
            yield sse(
                "human_input_required",
                {
                    "conversation_id": final_state.get("conversation_id"),
                    "workflow_session_id": final_state.get("workflow_session_id"),
                    "current_node": paused_at,
                    "next_node": next_node,
                    "status": "waiting_for_human",
                    "message": f"Checkpoint reached after node '{paused_at}'. Awaiting human feedback.",
                },
            )
            return

        # 2. Check explicit HITL node interrupts
        interrupts = [
            pending_interrupt.value
            for task in snapshot.tasks
            for pending_interrupt in task.interrupts
        ]
        if interrupts:
            final_state = dict(snapshot.values)
            interrupt_data = interrupts[0]
            final_state["status"] = "waiting_for_human"
            final_state["current_node"] = interrupt_data.get("node_id", active_node or last_completed_node)
            save_session_file(final_state)
            yield sse("human_input_required", interrupt_data)
            return

        # 3. Check rejection
        if final_state.get("status") == "rejected":
            final_state["current_node"] = ""
            save_session_file(final_state)
            yield sse("workflow_rejected", {"status": "rejected", "rework_count": final_state.get("rework_count", 0)})
            return

        # 4. Natural workflow completion
        final_state["status"] = "completed"
        final_state["current_node"] = ""
        save_session_file(final_state)
        yield sse(
            "workflow_complete",
            {
                "status": "completed",
                "conversation_id": final_state.get("conversation_id"),
                "workflow_session_id": final_state.get("workflow_session_id"),
                "publish_result": final_state.get("publish_result"),
                "artifacts_summary": list(final_state.get("artifacts", {}).keys()) if isinstance(final_state.get("artifacts"), dict) else [],
            },
        )
    except Exception as exc:
        yield sse("node_error", {"node_id": active_node or last_completed_node or "unknown-node", "error": str(exc)})
