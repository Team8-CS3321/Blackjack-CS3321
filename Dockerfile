FROM python:3.13-slim

LABEL authors="Carter"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system dependencies + Doppler CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
    && curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' \
        | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" \
        | tee /etc/apt/sources.list.d/doppler-cli.list \
    && apt-get update && apt-get install -y doppler \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Copy backend and frontend assets
COPY backend/ ./backend/

# Sync and build the project
RUN uv sync --frozen --no-install-project \
    && uv build

# Install the built wheel (includes frontend as build artifact)
RUN uv pip install dist/*.whl --no-deps

EXPOSE 3000

ENV PYTHONPATH=/app

# ── Runtime Configuration ────────────────────────────────────────────
# Doppler CLI injects all secrets at runtime.
#
# Required (passed in by GitHub Actions):
#   - DOPPLER_TOKEN: Doppler service token

CMD ["sh", "-c", "doppler run -- uv run uvicorn blackjack.app:asgi_app --host ${HOST:-0.0.0.0} --port ${PORT:-3000}"]
