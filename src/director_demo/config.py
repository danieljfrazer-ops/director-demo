from __future__ import annotations

from pathlib import Path

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
    ffprobe_binary: str = Field(default="ffprobe", min_length=1)
    ltx_runtime_root: Path = Path(".runtime/LTX-2")
    ltx_models_root: Path = Path("models")
    ltx_default_width: int = Field(default=1024, gt=0, multiple_of=64)
    ltx_default_height: int = Field(default=576, gt=0, multiple_of=64)
    ltx_default_frames: int = Field(default=121, gt=0)
    ltx_default_frame_rate: float = Field(default=24.0, gt=0)
    ltx_default_offload: str = "disk"
    ltx_default_max_batch_size: int = Field(default=1, gt=0)
    ltx_minimum_free_gib: float = Field(default=20.0, gt=0)
