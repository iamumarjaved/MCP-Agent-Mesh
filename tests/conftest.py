"""Shared test fixtures for the MCP Agent Mesh test suite.

Provides mock Redis clients, context stores, sample data, cost tracker
instances, and factory helpers used across unit, integration, and e2e tests.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Environment overrides for testing
# ---------------------------------------------------------------------------

os.environ.setdefault("ENV", "test")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------

class MockRedis:
    """In-memory Redis mock that supports basic get/set/delete/scan/mget/publish."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._channels: dict[str, list] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
        return count

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self._store.get(k) for k in keys]

    async def scan_iter(self, match: str = "*") -> Any:
        """Yield keys matching a glob pattern (simplified)."""
        import fnmatch
        for key in list(self._store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key

    async def publish(self, channel: str, message: str) -> int:
        self._channels.setdefault(channel, []).append(message)
        return 1

    def pubsub(self) -> MagicMock:
        ps = MagicMock()
        ps.subscribe = AsyncMock()
        ps.aclose = AsyncMock()
        return ps

    async def aclose(self) -> None:
        pass


@pytest.fixture
def mock_redis() -> MockRedis:
    """Provide a fresh MockRedis instance."""
    return MockRedis()


# ---------------------------------------------------------------------------
# Context store with mock Redis
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_context_store(mock_redis: MockRedis):
    """Provide a ContextStore backed by MockRedis."""
    from src.core.context_store import ContextStore
    store = ContextStore(redis_client=mock_redis)  # type: ignore[arg-type]
    return store


# ---------------------------------------------------------------------------
# Cost tracker
# ---------------------------------------------------------------------------

@pytest.fixture
def cost_tracker():
    """Provide a fresh CostTracker instance."""
    from src.core.cost_tracker import CostTracker
    tracker = CostTracker()
    yield tracker
    tracker.clear_all()


# ---------------------------------------------------------------------------
# Task ledger
# ---------------------------------------------------------------------------

@pytest.fixture
def task_ledger():
    """Provide a fresh TaskLedger instance."""
    from src.core.task_ledger import TaskLedger
    return TaskLedger()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_sales_data() -> list[dict]:
    """Return a small sample sales dataset for testing."""
    import random
    random.seed(42)

    products = ["Widget Pro", "Widget Lite", "Gadget X"]
    regions = ["North America", "Europe", "Asia Pacific"]
    segments = ["Enterprise", "SMB", "Startup"]

    rows = []
    start = date(2025, 10, 1)
    for i in range(20):
        sale_date = start + timedelta(days=i * 4)
        rows.append({
            "date": sale_date.isoformat(),
            "product": products[i % len(products)],
            "region": regions[i % len(regions)],
            "revenue": round(random.uniform(1000, 50000), 2),
            "units_sold": random.randint(1, 200),
            "discount": round(random.choice([0.0, 0.05, 0.10, 0.15]), 2),
            "customer_segment": segments[i % len(segments)],
        })
    return rows


@pytest.fixture
def sample_numeric_data() -> list[dict]:
    """Return a simple numeric dataset for statistical tests."""
    return [
        {"a": 10, "b": 100, "c": "x"},
        {"a": 20, "b": 200, "c": "y"},
        {"a": 30, "b": 150, "c": "x"},
        {"a": 40, "b": 250, "c": "z"},
        {"a": 50, "b": 300, "c": "x"},
        {"a": 15, "b": 120, "c": "y"},
        {"a": 25, "b": 180, "c": "z"},
        {"a": 35, "b": 220, "c": "x"},
        {"a": 45, "b": 280, "c": "y"},
        {"a": 55, "b": 350, "c": "z"},
    ]


@pytest.fixture
def sample_data_with_nulls() -> list[dict]:
    """Return a dataset with null values for cleaning tests."""
    return [
        {"name": "Alice", "age": 30, "score": 85.0},
        {"name": "Bob", "age": None, "score": 92.0},
        {"name": "Charlie", "age": 25, "score": None},
        {"name": None, "age": 35, "score": 78.0},
        {"name": "Alice", "age": 30, "score": 85.0},  # duplicate
        {"name": "Eve", "age": 28, "score": 90.0},
    ]


@pytest.fixture
def sample_claims() -> list[str]:
    """Return sample textual claims for hallucination detection tests."""
    return [
        "Revenue increased by 25% in Q4 2025.",
        "The top-selling product was Widget Pro with 1500 units.",
        "Customer retention rate reached 95%.",
    ]


@pytest.fixture
def sample_task_request() -> dict:
    """Return a sample task submission payload."""
    return {
        "query": "Analyze Q4 2025 sales performance by region and product",
        "workflow": "sales_analysis",
        "sources": ["data/sample/sales_q4_2025.csv"],
        "params": {},
        "budget_limit_usd": 1.00,
    }


# ---------------------------------------------------------------------------
# Workflow fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_workflow_yaml(tmp_path) -> str:
    """Create a temporary workflow YAML file and return its path."""
    content = """
name: test_workflow
description: A test workflow for unit testing
version: "1.0"
triggers:
  - keywords: ["test", "analyze"]
steps:
  - id: step-ingest
    agent: data-ingestion-v1
    action: ingest_and_clean
    params:
      source: test.csv
    depends_on: []
    timeout: "30s"
    retry: 2

  - id: step-analyze
    agent: analytics-v1
    action: run_analyses
    params:
      analyses: ["statistics"]
    depends_on: ["step-ingest"]
    timeout: "2m"
    retry: 3

  - id: step-report
    agent: presentation-v1
    action: compile_report
    params: {}
    depends_on: ["step-analyze"]
    timeout: "1m"
    retry: 1

approval_gates:
  - after: step-analyze
    condition: "quality_score < 0.7"

notifications:
  on_complete: webhook
"""
    filepath = tmp_path / "test_workflow.yaml"
    filepath.write_text(content)
    return str(filepath)
