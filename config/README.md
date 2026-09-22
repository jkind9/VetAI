# Configuration

This folder has no configuration files. The launched backend reads and validates these non-secret
environment values in `src/backend/settings.py`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VETAI_OLLAMA_MODEL` | `llama3:latest` | Installed Ollama model tag. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL. |
| `VETAI_OLLAMA_TIMEOUT_SECONDS` | `60` | One model-call timeout. |
| `BACKEND_API_URL` | `http://127.0.0.1:8000` | Desktop-only backend URL. |

Machine-specific URLs and any future provider credentials belong in environment variables, never
committed YAML. Maximum history length remains derived from the two-question cap rather than made
configurable.
