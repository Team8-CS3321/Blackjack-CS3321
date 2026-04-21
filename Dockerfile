FROM python:3.13-slim

LABEL authors="Carter"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Sync dependencies
RUN uv sync --frozen --no-install-project

COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 3000

ENV PYTHONPATH=/app/backend
CMD ["uv", "run", "uvicorn", "backend.app:asgi_app", "--host", "0.0.0.0", "--port", "3000"]
