"""Token usage and cost tracking for the MCP Agent Mesh.

Records per-call usage (model, tokens, cost) scoped to task/agent pairs
and provides aggregation queries for budget enforcement and reporting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.core.models import CostRecord, TokenUsage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing table  (USD per token)
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {
        "input": 2.50 / 1_000_000,   # $2.50 per 1M input tokens
        "output": 10.00 / 1_000_000,  # $10.00 per 1M output tokens
    },
    "gpt-4o-mini": {
        "input": 0.15 / 1_000_000,    # $0.15 per 1M input tokens
        "output": 0.60 / 1_000_000,   # $0.60 per 1M output tokens
    },
}


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the USD cost for a single call.

    Falls back to the ``gpt-4o`` pricing when the model is not in the
    pricing table, and logs a warning.
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        logger.warning(
            "No pricing data for model '%s'; falling back to gpt-4o rates",
            model,
        )
        pricing = MODEL_PRICING["gpt-4o"]

    return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])


# ---------------------------------------------------------------------------
# In-memory record store
# ---------------------------------------------------------------------------

@dataclass
class _UsageRecord:
    """Internal record for a single model invocation."""

    task_id: str
    agent_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: datetime


class CostTracker:
    """In-memory token-usage and cost tracker.

    Usage records are stored in a list and indexed by task ID for fast
    lookups.  The interface is intentionally async-friendly so it can be
    swapped for a persistent backend (e.g. Cosmos DB or PostgreSQL)
    without changing callers.
    """

    def __init__(self) -> None:
        # task_id -> list of records
        self._records: dict[str, list[_UsageRecord]] = {}

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_usage(
        self,
        task_id: str,
        agent_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> CostRecord:
        """Record a single model invocation and return the ``CostRecord``.

        The cost is calculated automatically from the pricing table.
        """
        cost = _compute_cost(model, input_tokens, output_tokens)

        record = _UsageRecord(
            task_id=task_id,
            agent_id=agent_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=datetime.now(timezone.utc),
        )

        self._records.setdefault(task_id, []).append(record)

        logger.debug(
            "Recorded usage: task=%s agent=%s model=%s in=%d out=%d cost=$%.6f",
            task_id,
            agent_id,
            model,
            input_tokens,
            output_tokens,
            cost,
        )

        return CostRecord(
            agent_id=agent_id,
            model=model,
            tokens=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            cost_usd=cost,
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_task_cost(self, task_id: str) -> float:
        """Return the total USD cost accumulated for a task."""
        records = self._records.get(task_id, [])
        return sum(r.cost_usd for r in records)

    def get_agent_cost(self, task_id: str, agent_id: str) -> float:
        """Return the total USD cost for a specific agent within a task."""
        records = self._records.get(task_id, [])
        return sum(r.cost_usd for r in records if r.agent_id == agent_id)

    def check_budget(
        self,
        task_id: str,
        budget: float,
    ) -> tuple[bool, float]:
        """Check whether a task is still within its budget.

        Returns:
            A ``(within_budget, spent)`` tuple where *within_budget* is
            ``True`` if the total spend is less than or equal to *budget*
            and *spent* is the current accumulated cost.
        """
        spent = self.get_task_cost(task_id)
        return (spent <= budget, spent)

    def get_cost_breakdown(self, task_id: str) -> dict[str, Any]:
        """Return a detailed cost breakdown for a task.

        The returned dict has the shape::

            {
                "task_id": "...",
                "total_cost_usd": 0.0123,
                "total_input_tokens": 500,
                "total_output_tokens": 200,
                "agents": {
                    "researcher": {
                        "cost_usd": 0.0100,
                        "input_tokens": 400,
                        "output_tokens": 150,
                        "calls": 2,
                        "models_used": ["gpt-4o"],
                    },
                    ...
                },
                "records": [ <list of per-call dicts> ],
            }
        """
        records = self._records.get(task_id, [])

        total_cost = 0.0
        total_input = 0
        total_output = 0
        agents: dict[str, dict[str, Any]] = {}

        per_call: list[dict[str, Any]] = []

        for r in records:
            total_cost += r.cost_usd
            total_input += r.input_tokens
            total_output += r.output_tokens

            if r.agent_id not in agents:
                agents[r.agent_id] = {
                    "cost_usd": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "calls": 0,
                    "models_used": set(),
                }

            agent_data = agents[r.agent_id]
            agent_data["cost_usd"] += r.cost_usd
            agent_data["input_tokens"] += r.input_tokens
            agent_data["output_tokens"] += r.output_tokens
            agent_data["calls"] += 1
            agent_data["models_used"].add(r.model)

            per_call.append(
                {
                    "agent_id": r.agent_id,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cost_usd": r.cost_usd,
                    "timestamp": r.timestamp.isoformat(),
                }
            )

        # Convert sets to sorted lists for JSON serialisation.
        for agent_data in agents.values():
            agent_data["models_used"] = sorted(agent_data["models_used"])

        return {
            "task_id": task_id,
            "total_cost_usd": total_cost,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "agents": agents,
            "records": per_call,
        }

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def clear_task(self, task_id: str) -> None:
        """Remove all usage records for a task."""
        self._records.pop(task_id, None)

    def clear_all(self) -> None:
        """Remove every record (useful in tests)."""
        self._records.clear()
