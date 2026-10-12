import os
import tempfile
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_name: str = "Agent Worker Service"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8002
    debug: bool = True
    session_dir: str | None = None


settings = WorkerSettings()

ROOT_DIR = Path(__file__).resolve().parent.parent


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

