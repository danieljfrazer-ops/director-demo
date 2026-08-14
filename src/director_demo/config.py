from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    director_llm_provider: str = "openai"
    director_llm_model: str = "gpt-5-mini"
    director_llm_base_url: str | None = None
    director_llm_api_key: str | None = None
    openai_api_key: str | None = None
    comfyui_base_url: str = "http://127.0.0.1:8188"
    ffmpeg_binary: str = Field(default="ffmpeg", min_length=1)
