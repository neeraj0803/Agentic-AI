from typing import Any, Callable

from langgraph.types import interrupt


def create_hitl_node(node: dict[str, Any]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def hitl_node(state: dict[str, Any]) -> dict[str, Any]:
        node_id = node["node_id"]
        variables = node.get("variables", {})
        review_data = variables.get("review_data")
        if review_data is None:
            review_data = [
                {
                    "node_id": item.get("node_id"),
                    "node_name": item.get("node_name"),
                    "output": item.get("output"),
                }
                for item in state.get("nodes", [])
                if item.get("output") is not None
            ]

        response = interrupt(
            {
                "workflow_session_id": state.get("workflow_session_id"),
                "node_id": node_id,
                "node_name": node.get("node_name", node_id),
                "message": variables.get(
                    "message",
                    "Review the provided information and approve or reject this workflow.",
                ),
                "review_data": review_data,
            }
        )

        if not isinstance(response, dict):
            raise ValueError("Human decision must be an object.")

        decision = response.get("decision")
        if decision not in {"approve", "reject"}:
            raise ValueError("Human decision must be 'approve' or 'reject'.")

        approved = decision == "approve"
        output = {
            "status": "approved" if approved else "rejected",
            "approved": approved,
            "feedback": response.get("feedback", ""),
            "reviewed_by": response.get("reviewed_by"),
        }
        updated_nodes = []
        for item in state.get("nodes", []):
            if item.get("node_id") == node_id:
                updated_nodes.append({**item, "output": output})
            else:
                updated_nodes.append(item)

        return {
            "nodes": updated_nodes,
            "status": "running" if approved else "rejected",
            "current_node": node_id,
        }

    return hitl_node

