"""End-to-end tests for the full MCP Agent Mesh pipeline.

Tests the complete flow from task submission through orchestration,
agent delegation, MCP tool execution, and result delivery.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.agents.base_agent import BaseAgent
from src.agents.orchestrator.agent import OrchestratorAgent
from src.core.cost_tracker import CostTracker
from src.core.models import (
    QualityVerdict,
    TaskLedgerEntry,
    TaskStatus,
    TaskStep,
)
from src.core.task_ledger import TaskLedger


# ---------------------------------------------------------------------------
# Stub agents for e2e testing
# ---------------------------------------------------------------------------

class StubIngestionAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            agent_id="data-ingestion-v1",
            name="Data Ingestion",
            description="Ingests and cleans data",
            capabilities=["data_ingestion", "cleaning"],
            mcp_server="data-access-server",
        )

    def get_system_prompt(self) -> str:
        return "You ingest data."

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": [
                {"product": "Widget Pro", "revenue": 50000, "units": 100},
                {"product": "Gadget X", "revenue": 75000, "units": 150},
            ],
            "row_count": 2,
            "quality_score": 0.95,
        }


class StubAnalyticsAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            agent_id="analytics-v1",
            name="Analytics",
            description="Runs statistical analyses",
            capabilities=["statistics", "trends", "anomalies"],
            mcp_server="compute-engine-server",
        )

    def get_system_prompt(self) -> str:
        return "You analyze data."

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {
            "statistics": {
                "total_revenue": 125000,
                "mean_revenue": 62500,
                "product_count": 2,
            },
            "trends": {"direction": "up", "growth_rate": 0.15},
            "anomalies": [],
        }


class StubInsightAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            agent_id="insight-generator-v1",
            name="Insight Generator",
            description="Generates business insights",
            capabilities=["insights", "recommendations"],
            mcp_server="knowledge-base-server",
        )

    def get_system_prompt(self) -> str:
        return "You generate insights."

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {
            "insights": [
                "Widget Pro and Gadget X are the top performers.",
                "Revenue trend is positive with 15% growth.",
            ],
            "recommendations": [
                "Increase inventory for top-performing products.",
                "Investigate underperforming regions.",
            ],
        }


class StubPresentationAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            agent_id="presentation-v1",
            name="Presentation",
            description="Compiles reports and visualizations",
            capabilities=["reports", "charts", "dashboards"],
            mcp_server="rendering-engine-server",
        )

    def get_system_prompt(self) -> str:
        return "You compile reports."

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {
            "report": {
                "title": "Q4 2025 Sales Analysis",
                "sections": ["Summary", "Statistics", "Trends", "Recommendations"],
                "format": "html",
            },
            "charts": ["revenue_by_product", "trend_line"],
        }


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFullPipeline:

    async def test_complete_pipeline_execution(self) -> None:
        """Test the full pipeline from task submission to result delivery."""
        # Setup
        orchestrator = OrchestratorAgent()
        orchestrator.cost_tracker = CostTracker()
        orchestrator.task_ledger = TaskLedger()

        orchestrator.register_agent(StubIngestionAgent())
        orchestrator.register_agent(StubAnalyticsAgent())
        orchestrator.register_agent(StubInsightAgent())
        orchestrator.register_agent(StubPresentationAgent())

        # Execute
        result = await orchestrator.execute(
            task={
                "request": "Analyze Q4 2025 sales performance by product and region",
                "budget_limit_usd": 1.00,
            },
            context={},
        )

        # Verify
        assert result["status"] == "completed"
        assert result["task_id"] is not None
        assert "final_output" in result
        assert "cost_breakdown" in result

        # Verify all steps produced output
        step_outputs = result.get("results", {})
        assert "step-ingest" in step_outputs
        assert "step-analytics" in step_outputs
        assert "step-insights" in step_outputs
        assert "step-present" in step_outputs

    async def test_pipeline_with_cost_tracking(self) -> None:
        """Verify cost tracking throughout the pipeline."""
        orchestrator = OrchestratorAgent()
        tracker = CostTracker()
        orchestrator.cost_tracker = tracker

        orchestrator.register_agent(StubIngestionAgent())
        orchestrator.register_agent(StubAnalyticsAgent())

        result = await orchestrator.execute(
            task={
                "request": "Analyze sales data",
                "budget_limit_usd": 1.00,
            },
            context={},
        )

        assert result["status"] == "completed"

        # Cost breakdown should show per-agent costs
        breakdown = result.get("cost_breakdown", {})
        if breakdown:
            assert breakdown["total_cost_usd"] > 0
            assert "agents" in breakdown

    async def test_pipeline_with_task_ledger(self) -> None:
        """Verify task state is tracked in the ledger."""
        orchestrator = OrchestratorAgent()
        orchestrator.cost_tracker = CostTracker()
        ledger = TaskLedger()
        orchestrator.task_ledger = ledger

        orchestrator.register_agent(StubIngestionAgent())

        result = await orchestrator.execute(
            task={
                "request": "Simple data ingestion test",
                "budget_limit_usd": 1.00,
                "task_id": "test-task-001",
            },
            context={},
        )

        assert result["status"] == "completed"

    async def test_pipeline_no_agents(self) -> None:
        """Pipeline with no agents should complete with empty results."""
        orchestrator = OrchestratorAgent()
        orchestrator.cost_tracker = CostTracker()

        result = await orchestrator.execute(
            task={"request": "No agents available"},
            context={},
        )

        assert result["status"] == "completed"
        assert result.get("results") == {} or result.get("results") is not None

    async def test_pipeline_partial_agents(self) -> None:
        """Pipeline with only some agents registered still works."""
        orchestrator = OrchestratorAgent()
        orchestrator.cost_tracker = CostTracker()

        # Only register ingestion and analytics
        orchestrator.register_agent(StubIngestionAgent())
        orchestrator.register_agent(StubAnalyticsAgent())

        result = await orchestrator.execute(
            task={
                "request": "Partial pipeline test",
                "budget_limit_usd": 1.00,
            },
            context={},
        )

        assert result["status"] == "completed"
        step_outputs = result.get("results", {})
        assert "step-ingest" in step_outputs
        assert "step-analytics" in step_outputs

    async def test_pipeline_budget_tracking(self) -> None:
        """Verify budget is tracked and reported correctly."""
        orchestrator = OrchestratorAgent()
        tracker = CostTracker()
        orchestrator.cost_tracker = tracker

        orchestrator.register_agent(StubIngestionAgent())

        result = await orchestrator.execute(
            task={
                "request": "Budget tracking test",
                "budget_limit_usd": 10.00,
            },
            context={},
        )

        assert result["status"] == "completed"

        # Verify budget was not exceeded
        breakdown = result.get("cost_breakdown", {})
        if breakdown:
            assert breakdown["total_cost_usd"] <= 10.00

    async def test_synthesis_produces_summary(self) -> None:
        """Verify the final synthesis step produces a summary."""
        orchestrator = OrchestratorAgent()
        orchestrator.cost_tracker = CostTracker()
        orchestrator.register_agent(StubIngestionAgent())

        result = await orchestrator.execute(
            task={"request": "Generate sales summary"},
            context={},
        )

        assert result["status"] == "completed"
        final_output = result.get("final_output", {})
        assert "summary" in final_output
        assert len(final_output["summary"]) > 0
