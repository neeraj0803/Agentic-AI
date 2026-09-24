from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(BaseModel):
    provider: str = "azure"


class Gemini(BaseModel):
    google_api_key: str | None = None
    gemini_model: str | None = "gemini-2.0-flash"


class AzureOpenAI(BaseModel):
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = "gpt-4o-mini"
    azure_openai_api_version: str | None = "2024-02-01"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="src/.env",
        env_prefix="",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Agentic AI"
    debug: bool = True
    llm: LLMProvider = Field(default_factory=LLMProvider)
    gemini: Gemini = Field(default_factory=Gemini)
    azure_openai: AzureOpenAI = Field(default_factory=AzureOpenAI)


settings = Settings()