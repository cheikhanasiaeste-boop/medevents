# syntax=docker/dockerfile:1.7
#
# Multi-stage image for the medevents-ingest service.
#
# IMPORTANT — build context must be the REPO ROOT, not services/ingest/.
# The repo uses a uv workspace config (see root pyproject.toml + root
# uv.lock); the Dockerfile copies BOTH the workspace root manifest AND
# the service-specific manifest + source. fly.toml sits at the repo root
# (build.dockerfile = "services/ingest/Dockerfile") for this reason.
#
# To build manually: `docker build -f services/ingest/Dockerfile -t medevents-ingest:dev .`
# (run from repo root, not services/ingest/).
#
# Target: Fly.io scheduled machines (see docs/superpowers/specs/
# 2026-04-23-medevents-w3-2d-fly-scheduled-machines.md). Matches W1 §324
# architecture: machine wakes hourly, runs `run --all`, exits.

# ---------- Stage 1: build ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# uv is distributed as a standalone binary; install from the official release.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

# Install build-time system packages. lxml needs libxml2/libxslt dev headers
# for any wheels that compile from source; psycopg[binary] ships precompiled.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy workspace-root manifest + lockfile first so they layer-cache when
# service source changes.
COPY pyproject.toml uv.lock ./

# Copy the service-specific manifest so `uv sync --package medevents-ingest`
# can resolve the workspace member's deps.
COPY services/ingest/pyproject.toml ./services/ingest/pyproject.toml

# Install deps into /opt/venv for the medevents-ingest workspace member.
# `--frozen` fails loudly if uv.lock disagrees with pyproject.toml — we'd
# rather fail the build than silently re-resolve. `--no-install-project`
# defers installing our own source until the next COPY layer so source
# changes don't invalidate the deps layer.
RUN uv sync --frozen --no-install-project --no-dev --package medevents-ingest

# Now copy the service source and install the project itself.
COPY services/ingest/medevents_ingest ./services/ingest/medevents_ingest
RUN uv sync --frozen --no-dev --package medevents-ingest

# Also copy the repo's config/ directory so the image contains config/sources.yaml
# for the `medevents-ingest seed-sources --path config/sources.yaml` invocation
# documented in the deploy runbook (Step 6).
COPY config ./config

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Runtime deps: lxml needs the shared libs at runtime (dev headers aren't needed).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — Fly doesn't require this, but it's good hygiene.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home /home/app --shell /bin/bash app \
    && mkdir -p /home/app \
    && chown -R app:app /home/app

WORKDIR /app

# Bring the built virtualenv + source + config from the builder stage.
COPY --from=builder --chown=app:app /opt/venv /opt/venv
COPY --from=builder --chown=app:app /app/services/ingest/medevents_ingest /app/medevents_ingest
COPY --from=builder --chown=app:app /app/config /app/config

USER app

# Default command runs the scheduled batch. Fly's scheduled machines invoke
# whatever the image's CMD is on each wake.
ENTRYPOINT ["medevents-ingest"]
CMD ["run", "--all"]
