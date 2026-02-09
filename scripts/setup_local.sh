#!/bin/bash
# Local development environment setup for MCP Agent Mesh.
#
# This script checks prerequisites, installs dependencies, starts
# infrastructure services, seeds sample data, and prints a summary
# of accessible URLs.
#
# Usage:
#   chmod +x scripts/setup_local.sh
#   ./scripts/setup_local.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# 1. Check prerequisites
# ---------------------------------------------------------------------------

log_info "Checking prerequisites..."

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        return 1
    fi
    log_ok "$1 found: $($1 --version 2>&1 | head -1)"
}

check_command python3
check_command docker
check_command poetry

# Verify Python version is 3.12+
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 12 ]; }; then
    log_error "Python 3.12+ is required (found $PYTHON_VERSION)"
    exit 1
fi
log_ok "Python version $PYTHON_VERSION meets requirement (>= 3.12)"

# Verify Docker daemon is running
if ! docker info &> /dev/null; then
    log_error "Docker daemon is not running. Please start Docker Desktop."
    exit 1
fi
log_ok "Docker daemon is running"

# ---------------------------------------------------------------------------
# 2. Environment file
# ---------------------------------------------------------------------------

log_info "Setting up environment configuration..."

cd "$PROJECT_ROOT"

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        log_ok "Created .env from .env.example"
        log_warn "Please review .env and add your API keys before running the full stack."
    else
        log_warn ".env.example not found -- skipping .env creation"
    fi
else
    log_ok ".env already exists"
fi

# ---------------------------------------------------------------------------
# 3. Install Python dependencies
# ---------------------------------------------------------------------------

log_info "Installing Python dependencies via Poetry..."

poetry install --with dev --no-interaction
log_ok "Python dependencies installed"

# ---------------------------------------------------------------------------
# 4. Install pre-commit hooks
# ---------------------------------------------------------------------------

if [ -f .pre-commit-config.yaml ]; then
    log_info "Installing pre-commit hooks..."
    poetry run pre-commit install
    log_ok "Pre-commit hooks installed"
fi

# ---------------------------------------------------------------------------
# 5. Start infrastructure services
# ---------------------------------------------------------------------------

log_info "Starting infrastructure services (Redis, Qdrant, Langfuse)..."

docker compose up -d redis qdrant langfuse langfuse-db
log_ok "Infrastructure services started"

# Wait for Redis to be ready
log_info "Waiting for Redis to be ready..."
for i in $(seq 1 30); do
    if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        log_ok "Redis is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        log_warn "Redis did not become ready in time -- continuing anyway"
    fi
    sleep 1
done

# Wait for Qdrant to be ready
log_info "Waiting for Qdrant to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:6333/readyz &>/dev/null; then
        log_ok "Qdrant is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        log_warn "Qdrant did not become ready in time -- continuing anyway"
    fi
    sleep 1
done

# ---------------------------------------------------------------------------
# 6. Seed sample data
# ---------------------------------------------------------------------------

log_info "Seeding sample data..."

poetry run python scripts/seed_data.py
log_ok "Sample data seeded"

if curl -sf http://localhost:6333/readyz &>/dev/null; then
    log_info "Seeding knowledge base..."
    poetry run python scripts/seed_knowledge_base.py
    log_ok "Knowledge base seeded"
else
    log_warn "Qdrant not available -- skipping knowledge base seeding"
fi

# ---------------------------------------------------------------------------
# 7. Summary
# ---------------------------------------------------------------------------

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  MCP Agent Mesh -- Setup Complete          ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  ${BLUE}API Server:${NC}       http://localhost:8000"
echo -e "  ${BLUE}Dashboard:${NC}        http://localhost:8501"
echo -e "  ${BLUE}Redis:${NC}            localhost:6379"
echo -e "  ${BLUE}Qdrant:${NC}           http://localhost:6333"
echo -e "  ${BLUE}Langfuse:${NC}         http://localhost:3000"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo -e "    1. Review .env and add your Azure OpenAI API key"
echo -e "    2. Start all services:  make docker-up"
echo -e "    3. Run the demo:        make demo"
echo -e "    4. Run tests:           make test"
echo ""
