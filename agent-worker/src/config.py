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


settings = WorkerSettings()
