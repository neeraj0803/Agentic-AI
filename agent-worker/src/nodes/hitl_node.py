from typing import Any, Callable

from langgraph.types import interrupt


def create_hitl_node(
    node_def: dict[str, Any], workflow_spec: dict[str, Any] | None = None
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    node_id = node_def.get("id") or node_def.get("node_id") or "qe_review_and_approval"
    node_name = node_def.get("node_name") or "QE Review and Approval"
    reviewer = node_def.get("reviewer", "initiating_user")
    additional_reviewers = node_def.get("additional_reviewers", ["qe_lead"])
    max_rework = int(node_def.get("max_rework", 3))

    def hitl_node(state: dict[str, Any]) -> dict[str, Any]:
        state["status"] = "waiting_for_human"
        state["current_node"] = node_id

        rework_count = state.get("rework_count", 0)
        artifacts = state.get("artifacts", {})
        drafted = state.get("drafted_tests", {})
        validated_inputs = state.get("validated_inputs", {})
        story_id = validated_inputs.get("jira_story_or_epic_id", "CHK-100")

        review_package = {
            "story_id": story_id,
            "test_cases_count": len(drafted.get("manual_test_cases", [])),
            "test_cases": drafted.get("manual_test_cases", []),
            "rtm_matrix": drafted.get("requirement_traceability_matrix", []),
            "regression_matrix": drafted.get("coverage_and_regression_matrix", []),
            "assumptions_and_gaps": drafted.get("assumptions_and_gaps", []),
            "artifacts_summary": list(artifacts.keys()) if isinstance(artifacts, dict) else [],
            "rework_count": rework_count,
            "max_rework": max_rework,
        }

        # Pause execution using LangGraph interrupt
        decision_response = interrupt(
            {
                "workflow_session_id": state.get("workflow_session_id"),
                "node_id": node_id,
                "node_name": node_name,
                "reviewer": reviewer,
                "additional_reviewers": additional_reviewers,
                "rework_count": rework_count,
                "max_rework": max_rework,
                "message": (
                    f"Review drafted test package for {story_id}. "
                    "Submit decision as 'approve', 'rework', or 'reject'."
                ),
                "review_data": review_package,
            }
        )

        if not isinstance(decision_response, dict):
            raise ValueError("Human decision must be a dictionary object.")

        decision = str(decision_response.get("decision", "")).lower()
        if decision not in {"approve", "approved", "rework", "reject", "rejected"}:
            raise ValueError("Human decision must be 'approve', 'rework', or 'reject'.")

        feedback = decision_response.get("feedback", "")
        reviewed_by = decision_response.get("reviewed_by") or reviewer

        review_record = {
            "decision": decision,
            "feedback": feedback,
            "reviewed_by": reviewed_by,
            "iteration": rework_count,
        }
        state.setdefault("review_history", []).append(review_record)

        if decision in {"approve", "approved"}:
            output = {
                "status": "approved",
                "approved": True,
                "rework": False,
                "decision": "approve",
                "feedback": feedback,
                "reviewed_by": reviewed_by,
            }
            state["status"] = "running"
        elif decision == "rework":
            if rework_count >= max_rework:
                output = {
                    "status": "rejected",
                    "approved": False,
                    "rework": False,
                    "decision": "reject",
                    "feedback": f"Max rework limit of {max_rework} reached. {feedback}",
                    "reviewed_by": reviewed_by,
                }
                state["status"] = "rejected"
            else:
                state["rework_count"] = rework_count + 1
                state["rework_feedback"] = feedback
                output = {
                    "status": "rework_requested",
                    "approved": False,
                    "rework": True,
                    "decision": "rework",
                    "feedback": feedback,
                    "rework_count": state["rework_count"],
                    "reviewed_by": reviewed_by,
                }
                state["status"] = "running"
        else:
            output = {
                "status": "rejected",
                "approved": False,
                "rework": False,
                "decision": "reject",
                "feedback": feedback,
                "reviewed_by": reviewed_by,
            }
            state["status"] = "rejected"

        for item in state.get("nodes", []):
            if item.get("node_id") == node_id or item.get("id") == node_id:
                item["output"] = output
                item["status"] = "completed"
                break

        return state

    return hitl_node
