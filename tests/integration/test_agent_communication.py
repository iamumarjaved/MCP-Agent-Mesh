"""Integration tests for agent-to-agent communication via context store.

Validates that agents can share data through the Redis-backed context
store, including set/get, multi-key operations, and pub/sub.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.core.context_store import ContextStore


@pytest.mark.asyncio
class TestAgentCommunication:

    async def test_set_and_get_context(self, mock_context_store: ContextStore) -> None:
        """Agent can store data and another can retrieve it."""
        await mock_context_store.set("task-1", "raw_data", {"rows": 100, "columns": 5})

        result = await mock_context_store.get("task-1", "raw_data")
        assert result == {"rows": 100, "columns": 5}

    async def test_multi_step_data_passing(self, mock_context_store: ContextStore) -> None:
        """Data flows through multiple steps via context store."""
        # Step 1: Ingestion agent stores raw data
        await mock_context_store.set("task-1", "output:step-ingest", {
            "data": [{"a": 1}, {"a": 2}],
            "row_count": 2,
        })

        # Step 2: Analytics agent reads ingested data and stores results
        ingest_output = await mock_context_store.get("task-1", "output:step-ingest")
        assert ingest_output is not None
        assert ingest_output["row_count"] == 2

        analytics_result = {
            "statistics": {"mean_a": 1.5},
            "source_row_count": ingest_output["row_count"],
        }
        await mock_context_store.set("task-1", "output:step-analytics", analytics_result)

        # Step 3: Presentation agent reads all outputs
        analytics_output = await mock_context_store.get("task-1", "output:step-analytics")
        assert analytics_output is not None
        assert analytics_output["statistics"]["mean_a"] == 1.5

    async def test_get_all_context_for_task(self, mock_context_store: ContextStore) -> None:
        """Retrieve all context keys for a task."""
        await mock_context_store.set("task-1", "key1", "value1")
        await mock_context_store.set("task-1", "key2", {"nested": True})
        await mock_context_store.set("task-2", "key1", "other_task")

        all_ctx = await mock_context_store.get_all("task-1")
        assert "key1" in all_ctx
        assert "key2" in all_ctx
        assert len(all_ctx) == 2

    async def test_task_isolation(self, mock_context_store: ContextStore) -> None:
        """Context for different tasks is isolated."""
        await mock_context_store.set("task-1", "data", "task1_data")
        await mock_context_store.set("task-2", "data", "task2_data")

        assert await mock_context_store.get("task-1", "data") == "task1_data"
        assert await mock_context_store.get("task-2", "data") == "task2_data"

    async def test_context_cleanup(self, mock_context_store: ContextStore) -> None:
        """Cleanup removes all context for a task."""
        await mock_context_store.set("task-1", "a", 1)
        await mock_context_store.set("task-1", "b", 2)
        await mock_context_store.set("task-2", "a", 3)

        removed = await mock_context_store.cleanup("task-1")
        assert removed == 2

        # task-1 keys are gone
        assert await mock_context_store.get("task-1", "a") is None
        assert await mock_context_store.get("task-1", "b") is None

        # task-2 is unaffected
        assert await mock_context_store.get("task-2", "a") == 3

    async def test_overwrite_context_key(self, mock_context_store: ContextStore) -> None:
        """Overwriting a key updates the value."""
        await mock_context_store.set("task-1", "data", {"version": 1})
        await mock_context_store.set("task-1", "data", {"version": 2})

        result = await mock_context_store.get("task-1", "data")
        assert result["version"] == 2

    async def test_nonexistent_key_returns_none(self, mock_context_store: ContextStore) -> None:
        """Getting a nonexistent key returns None."""
        result = await mock_context_store.get("task-1", "nonexistent")
        assert result is None

    async def test_delete_single_key(self, mock_context_store: ContextStore) -> None:
        """Deleting a single key removes only that key."""
        await mock_context_store.set("task-1", "keep", "yes")
        await mock_context_store.set("task-1", "remove", "bye")

        await mock_context_store.delete("task-1", "remove")

        assert await mock_context_store.get("task-1", "keep") == "yes"
        assert await mock_context_store.get("task-1", "remove") is None

    async def test_complex_data_types(self, mock_context_store: ContextStore) -> None:
        """Complex nested data structures survive serialization roundtrip."""
        complex_data: dict[str, Any] = {
            "statistics": {
                "mean": 42.5,
                "correlations": {"a_b": 0.85, "a_c": -0.32},
            },
            "anomalies": [
                {"index": 5, "value": 999.0, "score": 3.2},
            ],
            "metadata": {
                "agent": "analytics-v1",
                "tokens": {"input": 100, "output": 50},
            },
        }

        await mock_context_store.set("task-1", "output:step-analytics", complex_data)
        result = await mock_context_store.get("task-1", "output:step-analytics")

        assert result["statistics"]["mean"] == 42.5
        assert result["anomalies"][0]["value"] == 999.0
        assert result["metadata"]["tokens"]["input"] == 100
