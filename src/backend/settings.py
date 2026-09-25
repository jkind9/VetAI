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

    @property
    def structured_output_method(self) -> str:
        """Use the structured-output transport supported by the selected Ollama model."""
        model_family = self.model.casefold().split(":", maxsplit=1)[0]
        return "function_calling" if model_family == "gpt-oss" else "json_schema"

    @property
    def reasoning(self) -> str | None:
        """Keep gpt-oss's bounded generation budget available for its typed answer."""
        model_family = self.model.casefold().split(":", maxsplit=1)[0]
        return "low" if model_family == "gpt-oss" else None

    @classmethod
    def from_environment(cls) -> BackendSettings:
        return cls(
            model=os.environ.get("VETAI_OLLAMA_MODEL", "gpt-oss:20b"),
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            timeout_seconds=os.environ.get("VETAI_OLLAMA_TIMEOUT_SECONDS", "60"),
            search_timeout_seconds=os.environ.get("VETAI_SEARCH_TIMEOUT_SECONDS", "12"),
            search_region=os.environ.get("VETAI_SEARCH_REGION", "uk-en"),
        )
