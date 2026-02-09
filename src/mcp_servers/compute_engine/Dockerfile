# Compute Engine MCP Server
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry && \
    poetry export -f requirements.txt --without-hashes --output requirements.txt

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 9002

CMD ["python", "-m", "src.mcp_servers.compute_engine.server"]
