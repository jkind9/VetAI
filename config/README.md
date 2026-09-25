# Configuration

`approved_sources.toml` is the reviewed machine-readable source allowlist. Its organisations and
domains must match [`documentation/approved-sources.md`](../documentation/approved-sources.md).
Source changes are code-review changes: adding a domain expands which external text can influence a
result.

The launched backend reads these non-secret environment values:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VETAI_OLLAMA_MODEL` | `gpt-oss:20b` | Installed Ollama model used by all four chains |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL |
| `VETAI_OLLAMA_TIMEOUT_SECONDS` | `60` | Per-model-call timeout |
| `VETAI_SEARCH_TIMEOUT_SECONDS` | `12` | Overall approved-source search/fetch budget |
| `VETAI_SEARCH_REGION` | `uk-en` | Search-provider region |
| `BACKEND_API_URL` | `http://127.0.0.1:8000` | Desktop-only backend URL |

The desktop transfer timeout is longer than one model call because a final request performs query
generation, search, and synthesis. Individual stages remain bounded and are not automatically
retried.

Machine-specific URLs and any future provider credentials belong in environment variables. Do not
commit them. Generated queries, owner transcripts, and retrieved excerpts are not configuration and
must not be written here.
