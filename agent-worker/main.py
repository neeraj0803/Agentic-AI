import sys
from pathlib import Path

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.main import app
from src.graph.state import WorkflowNode, WorkflowState
from src.graph.workflow_orchestrator import (
    CHECKPOINTER,
    normalize_workflow_state,
    get_checkpoint_nodes,
    _heuristic_feedback_interpretation,
    interpret_human_feedback,
    passthrough_node,
    build_workflow_orchestration,
    sse,
    stream_workflow,
)
from src.session_manager import (
    BASE_DIR,
    SESSION_DIR,
    capture_workflow_snapshot,
    get_session_file_path,
    init_workflow_session,
    load_default_workflow_template,
    load_workflow_session,
    load_workflow_session_yaml,
    record_feedback_to_session,
    save_session_file,
)
from src.api.workflow_api import (
    WorkflowPayload,
    HumanFeedbackRequest,
    HumanDecisionRequest,
    ConversationRequest,
    run_workflow,
    submit_workflow_feedback,
    submit_human_decision,
    workflow_conversation,
    get_workflow_session,
    health,
)

# Backward-compatibility aliases
load_or_create_session_file = init_workflow_session
session_file_path = get_session_file_path

if __name__ == "__main__":
    import uvicorn
    from src.config import settings
    port = getattr(settings, "port", 8002)
    host = getattr(settings, "host", "0.0.0.0")
    print(f"Starting QE-201 Agent Worker Orchestrator on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)

