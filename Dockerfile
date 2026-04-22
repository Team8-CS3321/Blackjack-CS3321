FROM python:3.13-slim

LABEL authors="Carter"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Doppler CLI
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg && \
    curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh | sh && \
    apt-get purge -y --auto-remove curl gnupg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Sync dependencies
RUN uv sync --frozen --no-install-project

COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 3000


ENV PYTHONPATH=/app

# Install the project package
RUN uv pip install -e .

# Doppler runs as the entrypoint and injects secrets before handing off to the app.
# Pass DOPPLER_TOKEN at runtime: -e DOPPLER_TOKEN=dp.st.xxxx
# or via a Docker secret / Compose secrets block.
CMD ["doppler", "run", "--", "uv", "run", "uvicorn", "blackjack.app:asgi_app", "--host", "0.0.0.0", "--port", "3000"]
