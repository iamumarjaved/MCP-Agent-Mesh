"""Task submission and management routes.

Exposes endpoints for creating, listing, inspecting, cancelling tasks
and querying cost breakdowns.  All persistent state is accessed through
``request.app.state`` singletons (task ledger, cost tracker, etc.).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from src.api.routes.auth import verify_token
from src.core.models import (
    TaskLedgerEntry,
    TaskStatus,
    TaskSubmitRequest,
    TaskSubmitResponse,
    WSEvent,
)
from src.core.task_ledger import TaskNotFoundError

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_task_ledger(request: Request):
    """Retrieve the TaskLedger from application state."""
    ledger = request.app.state.task_ledger
    if ledger is None:
        raise HTTPException(
            status_code=503,
            detail="Task ledger is not initialised.",
        )
    return ledger


def _get_cost_tracker(request: Request):
    """Retrieve the CostTracker from application state."""
    tracker = request.app.state.cost_tracker
    if tracker is None:
        raise HTTPException(
            status_code=503,
            detail="Cost tracker is not initialised.",
        )
    return tracker


async def _run_orchestrator_pipeline(
    request: Request,
    task_id: str,
) -> None:
    """Background task that hands a submitted task to the orchestrator.

    If no orchestrator is configured (e.g. during development), the task
    status is moved to PLANNING and a log message is emitted.
    """
    import structlog

    logger = structlog.get_logger(__name__)
    ledger = request.app.state.task_ledger
    orchestrator = request.app.state.orchestrator

    if orchestrator is not None:
        try:
            await orchestrator.run(task_id)
        except Exception as exc:
            logger.error("orchestrator_pipeline_failed", task_id=task_id, error=str(exc))
            try:
                await ledger.update_task(task_id, status=TaskStatus.FAILED)
            except Exception:
                pass
    else:
        # No orchestrator configured -- move to PLANNING as a placeholder.
        logger.info(
            "no_orchestrator_configured",
            task_id=task_id,
            message="Orchestrator not initialised; task left in PLANNING state.",
        )
        try:
            await ledger.update_task(task_id, status=TaskStatus.PLANNING)
        except Exception:
            pass

    # Broadcast a WebSocket event if the connection manager is available.
    try:
        from src.api.routes.websocket import manager

        task = await ledger.get_task(task_id)
        await manager.broadcast(
            WSEvent(
                event_type="task_update",
                task_id=task_id,
                data={"status": task.status.value},
            )
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=TaskSubmitResponse)
async def submit_task(
    task_request: TaskSubmitRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> TaskSubmitResponse:
    """Submit a new analysis task.

    Creates a ledger entry, launches the orchestrator pipeline in the
    background, and returns a ``task_id`` for tracking.
    """
    ledger = _get_task_ledger(request)
    user_id: str = payload.get("sub", "anonymous")

    entry = await ledger.create_task(task_request, user_id=user_id)

    background_tasks.add_task(_run_orchestrator_pipeline, request, entry.task_id)

    return TaskSubmitResponse(
        task_id=entry.task_id,
        status=entry.status,
        message=f"Task '{entry.task_id}' submitted successfully. "
                f"Use GET /tasks/{entry.task_id} to track progress.",
    )


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """Get task status, plan, cost, and result details."""
    ledger = _get_task_ledger(request)

    try:
        entry: TaskLedgerEntry = await ledger.get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    return {
        "task_id": entry.task_id,
        "user_id": entry.user_id,
        "status": entry.status.value,
        "original_request": entry.original_request,
        "plan": [step.model_dump(mode="json") for step in entry.plan],
        "total_cost_usd": entry.total_cost_usd,
        "total_tokens": entry.total_tokens.model_dump(),
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
        "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
        "result_ref": entry.result_ref,
        "metadata": entry.metadata,
    }


@router.get("/")
async def list_tasks(
    request: Request,
    status: TaskStatus | None = None,
    limit: int = 20,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """List all tasks with optional status filter.

    Supports pagination via ``limit``.  Tasks are returned newest-first.
    """
    ledger = _get_task_ledger(request)
    user_role: str = payload.get("role", "viewer")
    user_id: str = payload.get("sub", "")

    # Admins see all tasks; others see only their own.
    filter_user: str | None = None if user_role == "admin" else user_id

    entries = await ledger.list_tasks(user_id=filter_user, status=status)

    # Sort newest first and apply limit.
    entries.sort(key=lambda e: e.created_at, reverse=True)
    entries = entries[:limit]

    return {
        "count": len(entries),
        "tasks": [
            {
                "task_id": e.task_id,
                "status": e.status.value,
                "original_request": e.original_request[:120],
                "total_cost_usd": e.total_cost_usd,
                "created_at": e.created_at.isoformat(),
                "updated_at": e.updated_at.isoformat(),
            }
            for e in entries
        ],
    }


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, str]:
    """Cancel a running task.

    Only tasks with a non-terminal status can be cancelled.  Terminal
    statuses are COMPLETED, FAILED, and CANCELLED.
    """
    ledger = _get_task_ledger(request)

    try:
        entry = await ledger.get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    if entry.status in terminal_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Task '{task_id}' is already in terminal state '{entry.status.value}'.",
        )

    await ledger.update_task(
        task_id,
        status=TaskStatus.CANCELLED,
        completed_at=datetime.now(timezone.utc),
    )

    # Broadcast cancellation event.
    try:
        from src.api.routes.websocket import manager

        await manager.send_to_task(
            task_id,
            WSEvent(
                event_type="task_cancelled",
                task_id=task_id,
                data={"status": TaskStatus.CANCELLED.value},
            ),
        )
    except Exception:
        pass

    return {"task_id": task_id, "status": "cancelled", "message": "Task cancelled successfully."}


@router.get("/{task_id}/cost")
async def get_task_cost(
    task_id: str,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """Get a detailed cost breakdown for a task.

    Returns per-agent token usage, model information, and total spend.
    """
    ledger = _get_task_ledger(request)
    cost_tracker = _get_cost_tracker(request)

    # Verify the task exists.
    try:
        await ledger.get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    breakdown = cost_tracker.get_cost_breakdown(task_id)
    return breakdown
