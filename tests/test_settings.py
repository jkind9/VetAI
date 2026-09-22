"""Launch configuration for the independently started backend."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.settings import BackendSettings


def test_backend_settings_use_local_ollama_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VETAI_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("VETAI_OLLAMA_TIMEOUT_SECONDS", raising=False)

    settings = BackendSettings.from_environment()

    assert settings.model == "llama3:latest"
    assert str(settings.base_url) == "http://localhost:11434/"
    assert settings.timeout_seconds == 60.0


def test_backend_settings_accept_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VETAI_OLLAMA_MODEL", "gpt-oss:20b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("VETAI_OLLAMA_TIMEOUT_SECONDS", "25")

    settings = BackendSettings.from_environment()

    assert settings.model == "gpt-oss:20b"
    assert str(settings.base_url) == "http://ollama:11434/"
    assert settings.timeout_seconds == 25.0


def test_backend_settings_reject_an_invalid_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VETAI_OLLAMA_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        BackendSettings.from_environment()
