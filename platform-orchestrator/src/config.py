from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_name: str = "Platform Orchestrator Service"
    version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8001

    # Storage settings
    db_type: str = "sqlite"  # "sqlite" or "mysql"
    db_path: str = str(Path(__file__).resolve().parent.parent / "orchestrator_local.db")
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "agentic_orchestrator"

    # Worker dispatch settings
    worker_service_url: str = "http://localhost:8002"
    worker_timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0

    # Policy snapshot version default
    default_policy_version: str = "2026.Q3"
    default_timeout_seconds: int = 300


settings = OrchestratorSettings()

