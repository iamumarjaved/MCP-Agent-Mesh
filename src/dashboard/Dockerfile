# Streamlit dashboard for the MCP Agent Mesh.

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry && \
    poetry export -f requirements.txt --without-hashes --output requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y poetry

COPY src/dashboard/ ./src/dashboard/

# Non-root user for security
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
