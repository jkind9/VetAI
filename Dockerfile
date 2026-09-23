# syntax=docker/dockerfile:1
FROM python:3.12.10-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.0 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project


FROM python:3.12.10-slim

WORKDIR /app
RUN useradd --create-home --uid 10001 vetai

COPY --from=builder /app/.venv /app/.venv
COPY --chown=vetai:vetai src/backend ./src/backend
COPY --chown=vetai:vetai src/mlflow_tracking ./src/mlflow_tracking
COPY --chown=vetai:vetai prompts ./prompts
COPY --chown=vetai:vetai config ./config

# The vetai user cannot write to /app, so MLflow keeps its database in the user's home folder.
# It is lost when the container is removed.
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    MLFLOW_TRACKING_URI=sqlite:////home/vetai/mlflow.db

USER vetai
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

CMD ["uvicorn", "--app-dir", "src", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
