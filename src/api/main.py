"""FastAPI application for MCP Agent Mesh API Gateway.

Configures the ASGI app with all middleware (CORS, rate limiting, error
handling), mounts API routers, and manages the application lifespan
(initialising shared resources on startup, cleaning up on shutdown).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.middleware.error_handler import ErrorHandlerMiddleware
from src.api.middleware.rate_limiter import RateLimiterMiddleware
from src.api.routes import agents, auth, tasks, websocket, workflows
from src.core.agent_registry import AgentRegistry
from src.core.config import settings
from src.core.context_store import ContextStore
from src.core.cost_tracker import CostTracker
from src.core.task_ledger import TaskLedger
from src.core.workflow_engine import WorkflowEngine

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    On startup, initialise all shared resources and attach them to
    ``app.state`` so that route handlers can access them via
    ``request.app.state``.

    On shutdown, gracefully close all connections and release resources.
    """
    logger.info(
        "startup",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    # --- Startup -----------------------------------------------------------

    # Task ledger (in-memory; swap with Cosmos DB backend for production).
    task_ledger = TaskLedger()
    app.state.task_ledger = task_ledger

    # Cost tracker.
    cost_tracker = CostTracker()
    app.state.cost_tracker = cost_tracker

    # Agent registry (Redis-backed).
    agent_registry = AgentRegistry()
    app.state.agent_registry = agent_registry

    # Shared context store (Redis-backed).
    context_store = ContextStore()
    app.state.context_store = context_store

    # Workflow engine -- load workflow definitions from disk if available.
    workflow_engine = WorkflowEngine()
    workflows_dir = os.path.join(os.path.dirname(__file__), "..", "..", "workflows")
    if os.path.isdir(workflows_dir):
        try:
            workflow_engine.load_workflows_dir(workflows_dir)
            logger.info("workflows_loaded", directory=workflows_dir)
        except Exception as exc:
            logger.warning("workflows_load_failed", error=str(exc))
    app.state.workflow_engine = workflow_engine

    # Orchestrator placeholder -- will be set by the orchestrator module.
    app.state.orchestrator = None

    logger.info("startup_complete", message="All resources initialised.")

    yield

    # --- Shutdown ----------------------------------------------------------

    logger.info("shutdown", message="Cleaning up resources.")

    try:
        await agent_registry.close()
    except Exception as exc:
        logger.warning("agent_registry_close_failed", error=str(exc))

    try:
        await context_store.close()
    except Exception as exc:
        logger.warning("context_store_close_failed", error=str(exc))

    logger.info("shutdown_complete")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered Business Analyst API -- MCP Agent Mesh orchestrates "
                "specialised AI agents to deliver data retrieval, statistical "
                "analysis, forecasting, and report generation.",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware (applied in reverse order -- last added runs first)
# ---------------------------------------------------------------------------

# 1. Error handler -- outermost layer catches all exceptions.
app.add_middleware(ErrorHandlerMiddleware)

# 2. Rate limiter.
app.add_middleware(RateLimiterMiddleware, requests_per_minute=60)

# 3. CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(agents.router)
app.include_router(workflows.router)
app.include_router(websocket.router)


# ---------------------------------------------------------------------------
# Root endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check(request: Request) -> dict:
    """Health check endpoint for load balancers and monitoring.

    Returns 200 with component status.  Individual component failures
    degrade the overall status to ``degraded`` rather than returning 5xx,
    so the gateway itself remains reachable for diagnostics.
    """
    components: dict[str, str] = {}
    overall = "healthy"

    # Task ledger.
    if request.app.state.task_ledger is not None:
        components["task_ledger"] = "healthy"
    else:
        components["task_ledger"] = "unavailable"
        overall = "degraded"

    # Cost tracker.
    if request.app.state.cost_tracker is not None:
        components["cost_tracker"] = "healthy"
    else:
        components["cost_tracker"] = "unavailable"
        overall = "degraded"

    # Agent registry -- attempt a lightweight check.
    if request.app.state.agent_registry is not None:
        try:
            await request.app.state.agent_registry.list_all()
            components["agent_registry"] = "healthy"
        except Exception:
            components["agent_registry"] = "degraded"
            overall = "degraded"
    else:
        components["agent_registry"] = "unavailable"
        overall = "degraded"

    # Context store.
    if request.app.state.context_store is not None:
        components["context_store"] = "healthy"
    else:
        components["context_store"] = "unavailable"
        overall = "degraded"

    # Orchestrator.
    if request.app.state.orchestrator is not None:
        components["orchestrator"] = "healthy"
    else:
        components["orchestrator"] = "not_configured"

    return {
        "status": overall,
        "version": settings.app_version,
        "environment": settings.environment,
        "components": components,
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint with API information and navigation links."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "AI-Powered Business Analyst API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "endpoints": {
            "auth": "/auth",
            "tasks": "/tasks",
            "agents": "/agents",
            "workflows": "/workflows",
            "websocket": "/ws",
        },
    }
