import os
from pathlib import Path
import tempfile
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent

class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "QE-201 Agent Worker Orchestrator"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8002
    debug: bool = True
    session_dir: str | None = None
    llm_config_path: str | None = None
    mock_input_path: str | None = None
    artifacts_dir: str | None = None
    skills_dir: str | None = None


settings = WorkerSettings()


def get_session_dir() -> Path:
    env_dir = os.getenv("WORKFLOW_SESSION_DIR") or settings.session_dir
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    default_dir = ROOT_DIR / "temp dir"
    try:
        default_dir.mkdir(parents=True, exist_ok=True)
        test_file = default_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
        return default_dir
    except (PermissionError, OSError):
        fallback_dir = Path(tempfile.gettempdir()) / "agent_worker_sessions"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir


SESSION_DIR = get_session_dir()


def get_llm_config_path() -> Path:
    env_path = os.getenv("LLM_CONFIG_PATH") or settings.llm_config_path
    if env_path and Path(env_path).exists():
        return Path(env_path)
    # Check llm-input/llm_model.json first, then root llm_model.json
    p1 = ROOT_DIR / "llm-input" / "llm_model.json"
    if p1.exists():
        return p1
    return ROOT_DIR / "llm_model.json"


def get_mock_input_path() -> Path:
    env_path = os.getenv("MOCK_INPUT_PATH") or settings.mock_input_path
    if env_path and Path(env_path).exists():
        return Path(env_path)
    return ROOT_DIR / "Mock-Input" / "Input-Context.json"


def get_artifacts_dir() -> Path:
    env_dir = os.getenv("WORKFLOW_ARTIFACTS_DIR") or settings.artifacts_dir
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    default_dir = ROOT_DIR / "artifacts"
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir


def get_skills_dir() -> Path:
    env_dir = os.getenv("WORKFLOW_SKILLS_DIR") or settings.skills_dir
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    # Check root skills directory where .skill files reside
    root_skills = ROOT_DIR / "skills"
    if root_skills.exists():
        return root_skills
    src_skills = ROOT_DIR / "src" / "skills"
    if src_skills.exists():
        return src_skills
    root_skills.mkdir(parents=True, exist_ok=True)
    return root_skills
