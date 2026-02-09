"""LangGraph state definitions for the Orchestrator Agent.

The :class:`OrchestratorGraphState` TypedDict is the single state object
that flows through every node in the orchestrator's LangGraph.  Keeping
all mutable data in one flat dict makes it straightforward to serialise
for checkpointing and to inspect during debugging.
"""

from __future__ import annotations

from typing import TypedDict

from src.core.models import (
    GuardianReport,
    OrchestratorState,
    TaskLedgerEntry,
)


class OrchestratorGraphState(TypedDict):
    """State carried through the orchestrator's LangGraph execution.

    Attributes
    ----------
    task:
        The full task ledger entry including the plan and metadata.
    current_state:
        Which orchestrator phase is currently active (planning,
        delegating, monitoring, etc.).
    current_step_index:
        Zero-based index into ``task.plan`` indicating which step
        is being executed right now.
    agent_outputs:
        Mapping of ``step_id -> output dict`` collected as steps
        complete successfully.
    guardian_reports:
        Mapping of ``step_id -> GuardianReport`` from validation
        passes.
    error_log:
        Chronological list of error messages encountered during
        execution (useful for debugging and replanning).
    replan_count:
        Number of times the orchestrator has replanned so far.
        Capped to prevent infinite replan loops.
    total_cost:
        Running total USD cost accumulated across all steps.
    """

    task: TaskLedgerEntry
    current_state: OrchestratorState
    current_step_index: int
    agent_outputs: dict[str, dict]
    guardian_reports: dict[str, GuardianReport]
    error_log: list[str]
    replan_count: int
    total_cost: float
