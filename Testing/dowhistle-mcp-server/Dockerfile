# =========================
# Builder stage
# =========================
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency definition files
COPY pyproject.toml uv.lock .python-version ./

# Create virtual environment + install deps
RUN uv sync --frozen --no-dev

# =========================
# Production stage
# =========================
FROM python:3.13-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_VENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && groupadd -r mcpuser \
    && useradd -r -g mcpuser -u 1000 -m -s /bin/bash mcpuser \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment
COPY --from=builder --chown=mcpuser:mcpuser /app/.venv /app/.venv

# Copy application source
COPY --chown=mcpuser:mcpuser . .

RUN mkdir -p /app/logs /app/data && \
    chown -R mcpuser:mcpuser /app

USER mcpuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ⚠️ CHANGE main.py IF YOUR ENTRY FILE NAME IS DIFFERENT
CMD ["python", "main.py"]
