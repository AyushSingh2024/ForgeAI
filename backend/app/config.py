"""Web-layer settings. Engine settings (models, budgets, thresholds) come from forge.config.load_config(),
which reads the same environment variables, so the CLI and the API always agree."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from forge.config import BACKEND_DIR, ForgeConfig, load_config


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    runs_dir: Path = BACKEND_DIR / "runs"
    demos_dir: Path = BACKEND_DIR / "demos"
    max_upload_mb: int = 25
    cors_origins: str = "http://localhost:3000"
    api_key: str = ""
    interview_timeout_min: int = 30
    chat_rate_per_min: int = 20
    llm_provider: str = "ollama"
    groq_api_key: str = ""
    hf_api_token: str = ""
    openai_api_key: str = ""

    @field_validator("runs_dir", "demos_dir", mode="after")
    @classmethod
    def _abs(cls, v: Path) -> Path:
        return v if v.is_absolute() else (BACKEND_DIR / v).resolve()

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def check(self) -> list[str]:
        problems = []
        if self.llm_provider == "groq" and not self.groq_api_key:
            problems.append("LLM_PROVIDER=groq but GROQ_API_KEY is empty")
        if self.llm_provider == "openai" and not self.openai_api_key:
            problems.append("LLM_PROVIDER=openai but OPENAI_API_KEY is empty")
        if self.llm_provider == "hf" and not self.hf_api_token:
            problems.append("LLM_PROVIDER=hf but HF_API_TOKEN is empty")
        return problems

    def to_forge_config(self) -> ForgeConfig:
        return load_config()


@lru_cache
def get_settings() -> Settings:
    return Settings()
