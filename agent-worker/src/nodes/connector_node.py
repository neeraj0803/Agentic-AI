import datetime
from typing import Any, Callable


def create_connector_node(
    node_def: dict[str, Any], workflow_spec: dict[str, Any]
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    node_id = node_def.get("id") or node_def.get("node_id") or "publish_to_xray_or_jira"
    connector_ref = node_def.get("connector_ref", "xray_rest_connector")
    execute_only_after_approval = node_def.get("execute_only_after_approval", True)

    def connector_node(state: dict[str, Any]) -> dict[str, Any]:
        state["status"] = "running"
        state["current_node"] = node_id

        # Verify approval if required
        if execute_only_after_approval:
            approval_granted = any(
                isinstance(item.get("output"), dict) and item["output"].get("approved") is True
                for item in state.get("nodes", [])
            )
            if not approval_granted:
                state["status"] = "failed"
                err_msg = f"Cannot execute {node_id}: Approval was not granted."
                state.setdefault("errors", []).append(err_msg)
                output = {"status": "failed", "error": err_msg}
                for item in state.get("nodes", []):
                    if item.get("node_id") == node_id or item.get("id") == node_id:
                        item["output"] = output
                        break
                return state

        validated_inputs = state.get("validated_inputs")
        def _resolve_val(key: str, default: str) -> str:
            if isinstance(validated_inputs, dict):
                return str(validated_inputs.get(key, default))
            elif isinstance(validated_inputs, list) and validated_inputs:
                for it in validated_inputs:
                    if isinstance(it, dict) and it.get(key):
                        return str(it[key])
            return default

        story_id = _resolve_val("jira_story_or_epic_id", state.get("workflow_id", "CHK-100"))
        output_pref = _resolve_val("output_preference", "xray_record")
        artifacts = state.get("artifacts", {})
        test_cases = state.get("drafted_tests", {}).get("manual_test_cases", [])

        # Simulate publishing to Xray REST API & Jira
        published_keys = [f"XRAY-{200 + i}" for i in range(1, len(test_cases) + 1)]
        test_execution_key = f"XRAY-EXEC-{story_id}-101"
        published_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        publish_result = {
            "status": "published",
            "connector_ref": connector_ref,
            "target_system": "Xray Test Management / Jira",
            "jira_story_id": story_id,
            "output_preference": output_pref,
            "published_at": published_at,
            "test_execution_key": test_execution_key,
            "xray_test_issues_created": [
                {"key": key, "summary": tc.get("title"), "priority": tc.get("priority")}
                for key, tc in zip(published_keys, test_cases)
            ],
            "total_tests_published": len(test_cases),
            "excel_export_generated": output_pref in {"excel_export", "xray_and_excel"},
            "excel_file_name": (
                artifacts.get("excel_export_file", {}).get("workbook_name")
                if isinstance(artifacts, dict) and output_pref in {"excel_export", "xray_and_excel"}
                else None
            ),
            "message": (
                f"Successfully published {len(test_cases)} test cases to Xray under {test_execution_key} "
                f"linked to Jira story {story_id}."
            ),
        }

        state["publish_result"] = publish_result

        for item in state.get("nodes", []):
            if item.get("node_id") == node_id or item.get("id") == node_id:
                item["output"] = publish_result
                item["status"] = "completed"
                break

        return state

    return connector_node

