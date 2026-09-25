"""Launch configuration for Ollama and approved-source retrieval."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.settings import BackendSettings


def test_backend_settings_use_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "VETAI_OLLAMA_MODEL",
        "OLLAMA_BASE_URL",
        "VETAI_OLLAMA_TIMEOUT_SECONDS",
        "VETAI_SEARCH_TIMEOUT_SECONDS",
        "VETAI_SEARCH_REGION",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = BackendSettings.from_environment()

    assert settings.model == "gpt-oss:20b"
    assert str(settings.base_url) == "http://localhost:11434/"
    assert settings.timeout_seconds == 60.0
    assert settings.search_timeout_seconds == 12.0
    assert settings.search_region == "uk-en"


def test_backend_settings_accept_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VETAI_OLLAMA_MODEL", "gpt-oss:20b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("VETAI_OLLAMA_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("VETAI_SEARCH_TIMEOUT_SECONDS", "8")
    monkeypatch.setenv("VETAI_SEARCH_REGION", "us-en")

    settings = BackendSettings.from_environment()

    assert settings.model == "gpt-oss:20b"
    assert str(settings.base_url) == "http://ollama:11434/"
    assert settings.timeout_seconds == 25.0
    assert settings.search_timeout_seconds == 8.0
    assert settings.search_region == "us-en"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("VETAI_OLLAMA_TIMEOUT_SECONDS", "0"),
        ("VETAI_SEARCH_TIMEOUT_SECONDS", "0"),
        ("VETAI_SEARCH_REGION", ""),
    ],
)
def test_backend_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        BackendSettings.from_environment()
