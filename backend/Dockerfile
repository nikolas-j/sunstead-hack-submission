# Backend container for Render (long-running uvicorn Web Service).
# Build context / Render Root Directory = backend/, so profile_output/*.json
# content pools are copied into the image and served on first boot.
FROM python:3.13-slim

# uv for fast, reproducible installs from the committed uv.lock.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first so this layer caches unless pyproject/uv.lock change.
# No [build-system] in pyproject => application layout; --no-install-project keeps
# uv from trying to build the repo itself.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App code (includes profile_output/*.json). .dockerignore keeps .env/.venv out.
COPY . .

ENV PORT=8000
# Exec form (JSON) so signals reach the process cleanly on Render redeploys;
# sh -c expands ${PORT} (injected by Render). --no-sync starts straight from the
# venv built above instead of re-checking the environment.
CMD ["sh", "-c", "uv run --no-sync uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
