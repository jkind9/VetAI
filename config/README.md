# Configuration

This folder has no configuration files yet. The planned `defaults.yaml` contains non-secret backend
settings: Ollama model and URL, temperature, seed, prompt path, two-question cap, and local MLflow
URI. Maximum history length is derived from the cap, not configured separately.

Machine-specific URLs and any future provider credentials belong in environment variables, never
committed YAML. A future `src/backend/settings.py` would validate these values and support a local
Ollama URL override. The frontend reads `BACKEND_API_URL` separately. See the
[plan](../documentation/implementation-plan.md) for the proposed shape.
