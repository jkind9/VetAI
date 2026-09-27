# Configuration

## Approved sources

`approved_sources.toml` lists the six websites the search may use. It must match the table in
[`documentation/approved-sources.md`](../documentation/approved-sources.md), which explains why each
site is on it. Adding a site changes which outside text can reach the summary, so treat it like a
code change.

## Environment variables

The backend reads these when it starts. None of them are secret.

| Variable | Default | What it sets |
| --- | --- | --- |
| `VETAI_OLLAMA_MODEL` | `gpt-oss:20b` | The Ollama model used for all four model steps |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where Ollama is running |
| `VETAI_OLLAMA_TIMEOUT_SECONDS` | `60` | How long to wait for one model call |
| `VETAI_SEARCH_TIMEOUT_SECONDS` | `12` | How long to wait for each search call and each page download |
| `VETAI_SEARCH_REGION` | `uk-en` | The search region |
| `MLFLOW_TRACKING_URI` | `sqlite:///mlflow.db` | Where MLflow saves its runs |
| `BACKEND_API_URL` | `http://127.0.0.1:8000` | Where the desktop window finds the backend (desktop only) |

For example, in PowerShell:

```powershell
$env:VETAI_OLLAMA_MODEL = "llama3:8b"
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

For any `gpt-oss` model, the backend asks for structured replies through function calling and sets
the model's reasoning effort to "low". Other models use Ollama's JSON-schema mode and their
default reasoning. Only `gpt-oss:20b` has been checked end to end.

Both screens stop waiting for a reply after 65 seconds. That is set in the screens' code, not by a
variable.

Put machine-specific addresses, and any future API keys, in environment variables, never in a
committed file. What owners type, the generated queries and the page text are data, not
configuration, and never belong here.
