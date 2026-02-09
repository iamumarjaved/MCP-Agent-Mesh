"""API route modules."""

from src.api.routes.auth import router as auth_router
from src.api.routes.tasks import router as tasks_router
from src.api.routes.agents import router as agents_router
from src.api.routes.workflows import router as workflows_router
from src.api.routes.websocket import router as websocket_router

__all__ = [
    "auth_router",
    "tasks_router",
    "agents_router",
    "workflows_router",
    "websocket_router",
]
