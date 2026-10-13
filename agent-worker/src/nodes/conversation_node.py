import logging
from ..session_manager import load_workflow_session
from .agent_node import call_llm

logger = logging.getLogger(__name__)


def conversation_node(workflow_session_id: str, user_query: str) -> str:
    workflow = load_workflow_session(workflow_session_id)
    story_id = workflow.get("validated_inputs", {}).get("jira_story_or_epic_id", "CHK-100")
    status = workflow.get("status", "unknown")
    tests = workflow.get("drafted_tests", {}).get("manual_test_cases", [])
    artifacts = workflow.get("artifacts", {})
    query_lower = user_query.lower()

    if "test case" in query_lower or "list" in query_lower or "show" in query_lower:
        if tests:
            lines = [f"Found {len(tests)} test cases for {story_id}:"]
            for tc in tests:
                lines.append(f"- **{tc.get('test_id')}**: {tc.get('title')} [{tc.get('type')}, {tc.get('priority')}]")
            return "\n".join(lines)
        return f"No test cases have been drafted yet for session {workflow_session_id} (Status: {status})."

    if "rtm" in query_lower or "traceability" in query_lower:
        rtm = workflow.get("drafted_tests", {}).get("requirement_traceability_matrix", [])
        if rtm:
            lines = [f"Requirement Traceability Matrix for {story_id}:"]
            for row in rtm:
                test_ids = row.get('test_case_ids') or row.get('test_ids', [])
                lines.append(f"- **{row.get('ac_id')}** ({row.get('ac_title', 'Requirement')}): {', '.join(test_ids)}")
            return "\n".join(lines)
        return "RTM matrix has not been generated yet."

    # If call_llm is mocked or functional, invoke it
    try:
        sys_msg = "You are an assistant answering questions about workflow execution state."
        user_prompt = f"Workflow Session: {workflow_session_id}\nState: {workflow}\nUser Question: {user_query}"
        llm_reply = call_llm(sys_msg, user_prompt)
        if llm_reply:
            return llm_reply
    except Exception as exc:
        logger.debug("call_llm fallback: %s", exc)

    if "status" in query_lower or "review" in query_lower:
        current_node = workflow.get("current_node", "")
        rework_count = workflow.get("rework_count", 0)
        art_keys = list(artifacts.keys()) if isinstance(artifacts, dict) else []
        return (
            f"Workflow Session: `{workflow_session_id}`\n"
            f"- Status: **{status}**\n"
            f"- Current Node: `{current_node}`\n"
            f"- Rework Iterations: {rework_count}\n"
            f"- Artifacts Available: {', '.join(art_keys) if art_keys else 'None'}"
        )

    if "artifact" in query_lower or "xray" in query_lower or "excel" in query_lower:
        publish = workflow.get("publish_result", {})
        if publish:
            return (
                f"Publishing Results for {story_id}:\n"
                f"- System: {publish.get('target_system')}\n"
                f"- Execution Key: {publish.get('test_execution_key')}\n"
                f"- Tests Created: {len(publish.get('xray_test_issues_created', []))}\n"
                f"- Excel Export: {publish.get('excel_file_name') or 'N/A'}"
            )
        art_keys = list(artifacts.keys()) if isinstance(artifacts, dict) else []
        return f"Artifacts available: {art_keys}. Publishing is pending review approval."

    # General workflow summary
    return (
        f"Workflow `{workflow.get('workflow_id', 'QE-201')}` for Jira story **{story_id}** is currently **{status}**. "
        f"{len(tests)} test cases generated. How can I help you with this session?"
    )
