from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class LLMProvider(BaseModel):
    provider: str
class Gemini(BaseModel):
    google_api_key: str | None
    gemini_model: str | None

class AzureOpenAI(BaseModel):
    azure_openai_endpoint: str | None
    azure_openai_api_key: str | None
    azure_openai_deployment: str | None
    azure_openai_api_version: str | None

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="src/.env",   
        env_prefix="",    
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
    )

    app_name: str = "Agentic AI"
    debug: bool = True
    llm: LLMProvider
    gemini: Gemini
    azure_openai: AzureOpenAI

settings = Settings()