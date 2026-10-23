# Multi-stage production build using Astral UV
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copy project source and install project
COPY src/ src/
COPY data/ data/
COPY README.md ./
RUN uv sync --frozen

# Production Runtime Stage
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

# Create non-root system user
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Copy virtual environment and project code from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/data /app/data
COPY --from=builder /app/pyproject.toml /app/pyproject.toml
COPY --from=builder /app/README.md /app/README.md

# Set environment PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create persistence directories with proper permissions
RUN mkdir -p /app/.chromadb /app/reports && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Health check against rules API endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/rules')" || exit 1

# Default: Launch Interactive Web Operations Portal
CMD ["safety-graph-orchestrator", "serve", "--host", "0.0.0.0", "--port", "8000"]
