"""Configuration used when the backend process is launched."""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PositiveFloat


class BackendSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(default="gpt-oss:20b", min_length=1)
    base_url: HttpUrl = "http://localhost:11434"
    timeout_seconds: PositiveFloat = 60.0
    search_timeout_seconds: PositiveFloat = 12.0
    search_region: str = Field(default="uk-en", min_length=1, max_length=20)

    @classmethod
    def from_environment(cls) -> BackendSettings:
        return cls(
            model=os.environ.get("VETAI_OLLAMA_MODEL", "gpt-oss:20b"),
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            timeout_seconds=os.environ.get("VETAI_OLLAMA_TIMEOUT_SECONDS", "60"),
            search_timeout_seconds=os.environ.get("VETAI_SEARCH_TIMEOUT_SECONDS", "12"),
            search_region=os.environ.get("VETAI_SEARCH_REGION", "uk-en"),
        )
