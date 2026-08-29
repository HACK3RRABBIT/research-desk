# research-desk — single-image container (backend + built web UI).
# The FastAPI server serves both the API and the static SPA, so one container
# is enough: `docker compose up -d` is the whole launch.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Where the desk stores its SQLite vault + briefs (mount a volume here).
    DATA_DIR=/app/data \
    # Build the SPA against the API served from the same origin (no proxy needed).
    VITE_API_BASE=""

WORKDIR /app

# ---- system deps for building the React UI (node) ----
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- Python deps (pinned from pyproject) ----
COPY pyproject.toml README.md ./
COPY research_desk ./research_desk
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn>=0.27" \
    "python-multipart>=0.0.9" "requests>=2.28" \
    "tomli>=2.0; python_version < '3.11'" "tomli_w>=1.0"

# ---- Frontend: build the SPA into webui/dist (served by the backend) ----
COPY webui ./webui
RUN cd webui \
    && npm install --no-audit --no-fund \
    && npm run build \
    && rm -rf node_modules

# Config lives in the image; runtime state (llm creds, learned sources,
# profile, vault) is written to DATA_DIR and persisted via the volume.
COPY config.toml ./config.toml

EXPOSE 8088
VOLUME ["/app/data"]

CMD ["uvicorn", "research_desk.server:app", "--host", "0.0.0.0", "--port", "8088"]
