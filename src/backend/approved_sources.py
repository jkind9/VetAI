"""Load and enforce the reviewed evidence-source catalog."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_SOURCE_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "approved_sources.toml"
)


@dataclass(frozen=True)
class ApprovedSource:
    organisation: str
    domain: str


@dataclass(frozen=True)
class ApprovedSourceCatalog:
    sources: tuple[ApprovedSource, ...]

    @classmethod
    def load(cls, path: Path | str = DEFAULT_SOURCE_CATALOG_PATH) -> ApprovedSourceCatalog:
        payload = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        sources = tuple(
            ApprovedSource(organisation=item["organisation"], domain=item["domain"].lower())
            for item in payload["sources"]
        )
        if not sources:
            raise ValueError("approved source catalog cannot be empty")
        if len({source.domain for source in sources}) != len(sources):
            raise ValueError("approved source domains must be unique")
        return cls(sources=sources)

    @property
    def domains(self) -> set[str]:
        return {source.domain for source in self.sources}

    def match(self, url: str) -> ApprovedSource | None:
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError:
            return None
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return None
        for source in self.sources:
            if host == source.domain or host.endswith(f".{source.domain}"):
                return source
        return None
