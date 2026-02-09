# Multi-stage build for the MCP Agent Mesh API server.
# Stage 1: Export Poetry dependencies to requirements.txt
# Stage 2: Lean production image with only runtime dependencies

FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry && \
    poetry export -f requirements.txt --without-hashes --output requirements.txt

# ---- Production image ----
FROM python:3.12-slim

WORKDIR /app

# Install only the runtime system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY workflows/ ./workflows/
COPY data/ ./data/

# Non-root user for security
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
