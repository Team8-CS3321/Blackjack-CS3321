FROM python:3.13-slim

LABEL authors="Carter"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Sync dependencies
RUN uv sync --frozen --no-install-project

COPY src/ ./src/
COPY public/ ./public/

EXPOSE 3000

ENV PYTHONPATH=/app/src
CMD ["uv", "run", "uvicorn", "src.app:asgi_app", "--host", "0.0.0.0", "--port", "3000"]
