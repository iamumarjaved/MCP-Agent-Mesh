"""Task state management for the MCP Agent Mesh.

Provides an in-memory task ledger suitable for development and testing.
The class interface is designed to be swapped with a Cosmos DB-backed
implementation in production without changing callers.
"""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from datetime import datetime, timezone

from src.core.exceptions import AgentMeshError
from src.core.models import (
    TaskLedgerEntry,
    TaskStatus,
    TaskStep,
    TaskSubmitRequest,
    _new_id,
    _utcnow,
)

logger = logging.getLogger(__name__)


class TaskNotFoundError(AgentMeshError):
    """Raised when a task ID cannot be resolved in the ledger."""

    def __init__(self, task_id: str) -> None:
        super().__init__(
            f"Task '{task_id}' not found in ledger",
            details={"task_id": task_id},
        )


class TaskLedger:
    """Async, dict-backed task ledger.

    Stores ``TaskLedgerEntry`` objects keyed by ``task_id``.  All public
    methods are coroutines so the interface is compatible with an async
    database backend (e.g. Cosmos DB) without changes at the call site.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, TaskLedgerEntry] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_task(
        self,
        request: TaskSubmitRequest,
        user_id: str,
    ) -> TaskLedgerEntry:
        """Create a new task from a submission request.

        Returns the freshly-created :class:`TaskLedgerEntry` with a unique
        ``task_id`` already assigned.
        """
        entry = TaskLedgerEntry(
            task_id=_new_id(),
            user_id=user_id,
            original_request=request.query,
            metadata={
                "workflow": request.workflow,
                "sources": request.sources,
                "params": request.params,
                "budget_limit_usd": request.budget_limit_usd,
            },
        )

        async with self._lock:
            self._tasks[entry.task_id] = entry

        logger.info(
            "Created task %s for user %s: %s",
            entry.task_id,
            user_id,
            request.query[:80],
        )
        return deepcopy(entry)

    async def get_task(self, task_id: str) -> TaskLedgerEntry:
        """Retrieve a task by ID.

        Raises:
            TaskNotFoundError: If no task with *task_id* exists.
        """
        async with self._lock:
            entry = self._tasks.get(task_id)

        if entry is None:
            raise TaskNotFoundError(task_id)

        return deepcopy(entry)

    async def update_task(self, task_id: str, **updates: object) -> TaskLedgerEntry:
        """Apply arbitrary field updates to an existing task.

        Only fields present on ``TaskLedgerEntry`` are accepted.  The
        ``updated_at`` timestamp is refreshed automatically.

        Returns the updated entry.

        Raises:
            TaskNotFoundError: If no task with *task_id* exists.
            ValueError: If an unknown field name is supplied.
        """
        valid_fields = set(TaskLedgerEntry.model_fields.keys())
        invalid = set(updates.keys()) - valid_fields
        if invalid:
            raise ValueError(
                f"Unknown TaskLedgerEntry field(s): {', '.join(sorted(invalid))}"
            )

        async with self._lock:
            entry = self._tasks.get(task_id)
            if entry is None:
                raise TaskNotFoundError(task_id)

            for field, value in updates.items():
                setattr(entry, field, value)
            entry.updated_at = _utcnow()

        logger.debug("Updated task %s: %s", task_id, list(updates.keys()))
        return deepcopy(entry)

    async def update_step(
        self,
        task_id: str,
        step_id: str,
        **updates: object,
    ) -> TaskStep:
        """Update fields on a specific step within a task.

        Returns the updated :class:`TaskStep`.

        Raises:
            TaskNotFoundError: If the task does not exist.
            ValueError: If the step or a field name is not found.
        """
        valid_fields = set(TaskStep.model_fields.keys())
        invalid = set(updates.keys()) - valid_fields
        if invalid:
            raise ValueError(
                f"Unknown TaskStep field(s): {', '.join(sorted(invalid))}"
            )

        async with self._lock:
            entry = self._tasks.get(task_id)
            if entry is None:
                raise TaskNotFoundError(task_id)

            target_step: TaskStep | None = None
            for step in entry.plan:
                if step.step_id == step_id:
                    target_step = step
                    break

            if target_step is None:
                raise ValueError(
                    f"Step '{step_id}' not found in task '{task_id}'"
                )

            for field, value in updates.items():
                setattr(target_step, field, value)

            entry.updated_at = _utcnow()

        logger.debug(
            "Updated step %s in task %s: %s",
            step_id,
            task_id,
            list(updates.keys()),
        )
        return deepcopy(target_step)

    async def add_step(self, task_id: str, step: TaskStep) -> None:
        """Append a new step to a task's plan.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        async with self._lock:
            entry = self._tasks.get(task_id)
            if entry is None:
                raise TaskNotFoundError(task_id)

            entry.plan.append(step)
            entry.updated_at = _utcnow()

        logger.debug("Added step %s to task %s", step.step_id, task_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_tasks(
        self,
        user_id: str | None = None,
        status: TaskStatus | None = None,
    ) -> list[TaskLedgerEntry]:
        """List tasks with optional filtering by *user_id* and/or *status*.

        Returns a list of deep-copied entries so callers cannot mutate
        the internal store.
        """
        async with self._lock:
            results: list[TaskLedgerEntry] = []
            for entry in self._tasks.values():
                if user_id is not None and entry.user_id != user_id:
                    continue
                if status is not None and entry.status != status:
                    continue
                results.append(deepcopy(entry))

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def count(self) -> int:
        """Return the total number of tasks in the ledger."""
        async with self._lock:
            return len(self._tasks)

    async def delete_task(self, task_id: str) -> None:
        """Remove a task from the ledger entirely.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        async with self._lock:
            if task_id not in self._tasks:
                raise TaskNotFoundError(task_id)
            del self._tasks[task_id]

        logger.info("Deleted task %s", task_id)
