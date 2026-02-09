"""Tests for the Orchestrator agent -- planning and delegation logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.agents.base_agent import BaseAgent
from src.agents.orchestrator.agent import OrchestratorAgent
from src.core.cost_tracker import CostTracker
from src.core.models import (
    QualityVerdict,
    StepStatus,
    TaskLedgerEntry,
    TaskStatus,
    TaskStep,
)


# ---------------------------------------------------------------------------
# Helper: stub specialist agent
# ---------------------------------------------------------------------------

class StubAgent(BaseAgent):
    """Minimal agent for testing delegation."""

    def __init__(self, agent_id: str, return_value: dict | None = None) -> None:
        super().__init__(
            agent_id=agent_id,
            name=f"Stub {agent_id}",
            description="Test stub",
            capabilities=["testing"],
            mcp_server="none",
        )
        self._return_value = return_value or {"status": "ok"}

    def get_system_prompt(self) -> str:
        return "You are a test stub."

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return self._return_value


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOrchestratorInit:

    def test_basic_attributes(self) -> None:
        orch = OrchestratorAgent()
        assert orch.agent_id == "orchestrator-v1"
        assert orch.name == "Orchestrator Agent"
        assert "task_planning" in orch.capabilities

    def test_no_mcp_server(self) -> None:
        orch = OrchestratorAgent()
        assert orch.mcp_server == "none"


class TestOrchestratorPlanning:

    @pytest.mark.asyncio
    async def test_plan_with_no_agents(self) -> None:
        orch = OrchestratorAgent()
        steps = await orch.plan_task("Analyze sales data")
        assert steps == []  # No agents registered

    @pytest.mark.asyncio
    async def test_plan_with_agents(self) -> None:
        orch = OrchestratorAgent()
        orch.register_agent(StubAgent("data-ingestion-v1"))
        orch.register_agent(StubAgent("analytics-v1"))
        orch.register_agent(StubAgent("insight-generator-v1"))
        orch.register_agent(StubAgent("presentation-v1"))

        steps = await orch.plan_task("Analyze Q4 sales")
        assert len(steps) == 4

        # Verify step IDs and dependency chain
        step_ids = [s.step_id for s in steps]
        assert "step-ingest" in step_ids
        assert "step-analytics" in step_ids
        assert "step-insights" in step_ids
        assert "step-present" in step_ids

    @pytest.mark.asyncio
    async def test_plan_dependency_chain(self) -> None:
        orch = OrchestratorAgent()
        orch.register_agent(StubAgent("data-ingestion-v1"))
        orch.register_agent(StubAgent("analytics-v1"))

        steps = await orch.plan_task("Analyze data")
        assert steps[0].depends_on == []
        assert steps[1].depends_on == ["step-ingest"]


class TestOrchestratorDelegation:

    @pytest.mark.asyncio
    async def test_delegate_step_success(self) -> None:
        orch = OrchestratorAgent()
        agent = StubAgent("data-ingestion-v1", return_value={"data": [1, 2, 3]})
        orch.register_agent(agent)

        step = TaskStep(
            step_id="s1",
            agent="data-ingestion-v1",
            action="ingest",
        )
        result = await orch.delegate_step(step, context={})
        assert result == {"data": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_delegate_step_unknown_agent(self) -> None:
        orch = OrchestratorAgent()
        step = TaskStep(
            step_id="s1",
            agent="nonexistent-agent",
            action="do_something",
        )
        with pytest.raises(Exception):
            await orch.delegate_step(step, context={})


class TestOrchestratorExecution:

    @pytest.mark.asyncio
    async def test_full_execute(self) -> None:
        orch = OrchestratorAgent()
        orch.cost_tracker = CostTracker()
        orch.register_agent(StubAgent("data-ingestion-v1"))

        result = await orch.execute(
            task={"request": "Test query", "budget_limit_usd": 1.00},
            context={},
        )
        assert result["status"] == "completed"
        assert "task_id" in result
        assert "final_output" in result

    @pytest.mark.asyncio
    async def test_execute_with_cost_tracking(self) -> None:
        orch = OrchestratorAgent()
        tracker = CostTracker()
        orch.cost_tracker = tracker

        orch.register_agent(StubAgent("data-ingestion-v1"))
        orch.register_agent(StubAgent("analytics-v1"))

        result = await orch.execute(
            task={"request": "Analyze data", "budget_limit_usd": 1.00},
            context={},
        )
        assert result["status"] == "completed"
        assert result.get("cost_breakdown") is not None

    @pytest.mark.asyncio
    async def test_execute_no_agents_still_completes(self) -> None:
        orch = OrchestratorAgent()
        result = await orch.execute(
            task={"request": "Empty pipeline test"},
            context={},
        )
        assert result["status"] == "completed"


class TestOrchestratorAgentRegistration:

    def test_register_agent(self) -> None:
        orch = OrchestratorAgent()
        agent = StubAgent("test-v1")
        orch.register_agent(agent)
        assert orch._has_agent("test-v1")

    def test_has_agent_false(self) -> None:
        orch = OrchestratorAgent()
        assert not orch._has_agent("nonexistent")

    def test_describe_agents_empty(self) -> None:
        orch = OrchestratorAgent()
        desc = orch._describe_available_agents()
        assert "no agents" in desc.lower()

    def test_describe_agents_with_registered(self) -> None:
        orch = OrchestratorAgent()
        orch.register_agent(StubAgent("test-v1"))
        desc = orch._describe_available_agents()
        assert "test-v1" in desc
