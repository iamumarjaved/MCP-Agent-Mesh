"""Global error handling middleware.

Catches all exceptions raised during request processing and maps them
to structured JSON error responses with appropriate HTTP status codes.
Custom ``AgentMeshError`` subclasses are handled with specific codes;
unexpected errors return a generic 500 response.
"""

from __future__ import annotations

import traceback

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.core.exceptions import (
    AgentMeshError,
    AgentRegistrationError,
    AgentTimeoutError,
    BudgetExceededError,
    ContextStoreError,
    GuardianRejectionError,
    HITLTimeoutError,
    MCPToolError,
    WorkflowError,
)

logger = structlog.get_logger(__name__)

# Map specific exception types to HTTP status codes.
_STATUS_MAP: dict[type[AgentMeshError], int] = {
    BudgetExceededError: 402,        # Payment Required
    AgentTimeoutError: 504,          # Gateway Timeout
    MCPToolError: 502,               # Bad Gateway (upstream tool failure)
    GuardianRejectionError: 422,     # Unprocessable Entity
    WorkflowError: 400,              # Bad Request
    AgentRegistrationError: 503,     # Service Unavailable
    ContextStoreError: 503,          # Service Unavailable
    HITLTimeoutError: 408,           # Request Timeout
}


def _status_for(exc: AgentMeshError) -> int:
    """Resolve the HTTP status code for a given exception instance."""
    for exc_type, status in _STATUS_MAP.items():
        if isinstance(exc, exc_type):
            return status
    # Fallback for the base AgentMeshError or unknown sub-classes.
    return 500


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catches exceptions and returns structured JSON error responses."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        try:
            response = await call_next(request)
            return response

        except AgentMeshError as exc:
            status_code = _status_for(exc)
            logger.warning(
                "agent_mesh_error",
                error_type=type(exc).__name__,
                message=str(exc),
                details=exc.details,
                status_code=status_code,
                path=str(request.url.path),
                method=request.method,
            )
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": type(exc).__name__,
                    "message": str(exc),
                    "details": exc.details,
                },
            )

        except Exception as exc:
            logger.error(
                "unhandled_error",
                error_type=type(exc).__name__,
                message=str(exc),
                traceback=traceback.format_exc(),
                path=str(request.url.path),
                method=request.method,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred. Please try again later.",
                },
            )


async def error_handler_middleware(request: Request, call_next) -> Response:
    """Functional middleware wrapper for use with ``app.middleware("http")``.

    This provides an alternative to the class-based middleware above,
    allowing usage via::

        app.middleware("http")(error_handler_middleware)
    """
    try:
        response = await call_next(request)
        return response
    except AgentMeshError as exc:
        status_code = _status_for(exc)
        logger.warning(
            "agent_mesh_error",
            error_type=type(exc).__name__,
            message=str(exc),
            details=exc.details,
            status_code=status_code,
            path=str(request.url.path),
            method=request.method,
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "error": type(exc).__name__,
                "message": str(exc),
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error(
            "unhandled_error",
            error_type=type(exc).__name__,
            message=str(exc),
            traceback=traceback.format_exc(),
            path=str(request.url.path),
            method=request.method,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )
