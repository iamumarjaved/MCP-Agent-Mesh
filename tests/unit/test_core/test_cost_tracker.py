"""Tests for src.core.cost_tracker -- cost tracking logic."""

from __future__ import annotations

import pytest

from src.core.cost_tracker import (
    MODEL_PRICING,
    CostTracker,
    _compute_cost,
)


class TestComputeCost:

    def test_gpt4o_pricing(self) -> None:
        cost = _compute_cost("gpt-4o", input_tokens=1000, output_tokens=500)
        expected = (1000 * 2.50 / 1_000_000) + (500 * 10.00 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_gpt4o_mini_pricing(self) -> None:
        cost = _compute_cost("gpt-4o-mini", input_tokens=1000, output_tokens=500)
        expected = (1000 * 0.15 / 1_000_000) + (500 * 0.60 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_unknown_model_falls_back_to_gpt4o(self) -> None:
        cost = _compute_cost("unknown-model", input_tokens=1000, output_tokens=500)
        expected = _compute_cost("gpt-4o", input_tokens=1000, output_tokens=500)
        assert cost == expected

    def test_zero_tokens(self) -> None:
        cost = _compute_cost("gpt-4o", input_tokens=0, output_tokens=0)
        assert cost == 0.0


class TestCostTracker:

    def test_record_usage_returns_cost_record(self, cost_tracker: CostTracker) -> None:
        record = cost_tracker.record_usage(
            task_id="t1", agent_id="a1", model="gpt-4o",
            input_tokens=100, output_tokens=50,
        )
        assert record.agent_id == "a1"
        assert record.model == "gpt-4o"
        assert record.tokens.input_tokens == 100
        assert record.tokens.output_tokens == 50
        assert record.cost_usd > 0

    def test_get_task_cost(self, cost_tracker: CostTracker) -> None:
        cost_tracker.record_usage("t1", "a1", "gpt-4o", 100, 50)
        cost_tracker.record_usage("t1", "a2", "gpt-4o-mini", 200, 100)

        total = cost_tracker.get_task_cost("t1")
        assert total > 0

    def test_get_task_cost_nonexistent(self, cost_tracker: CostTracker) -> None:
        assert cost_tracker.get_task_cost("nonexistent") == 0.0

    def test_get_agent_cost(self, cost_tracker: CostTracker) -> None:
        cost_tracker.record_usage("t1", "a1", "gpt-4o", 100, 50)
        cost_tracker.record_usage("t1", "a2", "gpt-4o", 200, 100)
        cost_tracker.record_usage("t1", "a1", "gpt-4o", 50, 25)

        a1_cost = cost_tracker.get_agent_cost("t1", "a1")
        a2_cost = cost_tracker.get_agent_cost("t1", "a2")

        assert a1_cost > a2_cost  # a1 has two records
        assert a1_cost + a2_cost == pytest.approx(cost_tracker.get_task_cost("t1"))

    def test_check_budget_within(self, cost_tracker: CostTracker) -> None:
        cost_tracker.record_usage("t1", "a1", "gpt-4o-mini", 100, 50)
        within, spent = cost_tracker.check_budget("t1", budget=1.00)
        assert within is True
        assert spent > 0
        assert spent < 1.00

    def test_check_budget_exceeded(self, cost_tracker: CostTracker) -> None:
        # Record enough usage to exceed a tiny budget
        cost_tracker.record_usage("t1", "a1", "gpt-4o", 100_000, 50_000)
        within, spent = cost_tracker.check_budget("t1", budget=0.001)
        assert within is False
        assert spent > 0.001

    def test_get_cost_breakdown(self, cost_tracker: CostTracker) -> None:
        cost_tracker.record_usage("t1", "a1", "gpt-4o", 100, 50)
        cost_tracker.record_usage("t1", "a2", "gpt-4o-mini", 200, 100)

        breakdown = cost_tracker.get_cost_breakdown("t1")

        assert breakdown["task_id"] == "t1"
        assert breakdown["total_cost_usd"] > 0
        assert breakdown["total_input_tokens"] == 300
        assert breakdown["total_output_tokens"] == 150
        assert "a1" in breakdown["agents"]
        assert "a2" in breakdown["agents"]
        assert breakdown["agents"]["a1"]["calls"] == 1
        assert breakdown["agents"]["a2"]["calls"] == 1
        assert "gpt-4o" in breakdown["agents"]["a1"]["models_used"]
        assert len(breakdown["records"]) == 2

    def test_clear_task(self, cost_tracker: CostTracker) -> None:
        cost_tracker.record_usage("t1", "a1", "gpt-4o", 100, 50)
        assert cost_tracker.get_task_cost("t1") > 0

        cost_tracker.clear_task("t1")
        assert cost_tracker.get_task_cost("t1") == 0.0

    def test_clear_all(self, cost_tracker: CostTracker) -> None:
        cost_tracker.record_usage("t1", "a1", "gpt-4o", 100, 50)
        cost_tracker.record_usage("t2", "a1", "gpt-4o", 100, 50)

        cost_tracker.clear_all()
        assert cost_tracker.get_task_cost("t1") == 0.0
        assert cost_tracker.get_task_cost("t2") == 0.0

    def test_multiple_tasks_isolated(self, cost_tracker: CostTracker) -> None:
        cost_tracker.record_usage("t1", "a1", "gpt-4o", 100, 50)
        cost_tracker.record_usage("t2", "a1", "gpt-4o", 200, 100)

        t1_cost = cost_tracker.get_task_cost("t1")
        t2_cost = cost_tracker.get_task_cost("t2")
        assert t1_cost != t2_cost
        assert t2_cost > t1_cost
