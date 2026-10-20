"""Application configuration using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for Ask-the-Business."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider Selection
    llm_provider: Literal["gemini", "groq"] = "gemini"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    # DuckDB
    duckdb_path: Path = Path("data/analytics.duckdb")
    duckdb_read_only: bool = True

    # Caching & Evaluation
    enable_llm_cache: bool = True
    eval_cache_dir: Path = Path(".eval_cache")


settings = Settings()
