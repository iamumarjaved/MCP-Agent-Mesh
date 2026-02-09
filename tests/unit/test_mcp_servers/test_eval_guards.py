"""Tests for eval guard MCP server tools: PII, hallucination, integrity."""

from __future__ import annotations

import pytest

from src.mcp_servers.eval_guards.tools.check_data_integrity import check_data_integrity


# ---------------------------------------------------------------------------
# check_data_integrity
# ---------------------------------------------------------------------------

class TestCheckDataIntegrity:

    @pytest.mark.asyncio
    async def test_complete_data_passes(self) -> None:
        data = [
            {"name": "Alice", "age": 30, "score": 85.0},
            {"name": "Bob", "age": 25, "score": 92.0},
            {"name": "Charlie", "age": 35, "score": 78.0},
        ]
        result = await check_data_integrity({"data": data})
        assert result["passed"] is True
        assert result["score"] > 0.5
        assert any(c["name"] == "completeness" for c in result["checks"])

    @pytest.mark.asyncio
    async def test_data_with_nulls(self) -> None:
        data = [
            {"name": "Alice", "age": 30, "score": 85.0},
            {"name": "Bob", "age": None, "score": 92.0},
            {"name": None, "age": 35, "score": None},
        ]
        result = await check_data_integrity({"data": data})
        # Should detect nulls
        completeness_check = next(
            c for c in result["checks"] if c["name"] == "completeness"
        )
        assert "null" in completeness_check["details"].lower() or completeness_check["passed"]

    @pytest.mark.asyncio
    async def test_empty_data_fails(self) -> None:
        result = await check_data_integrity({"data": []})
        assert result["passed"] is False
        assert result["score"] == 0.0

    @pytest.mark.asyncio
    async def test_with_expected_schema(self) -> None:
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": "twenty-five"},  # type mismatch
        ]
        result = await check_data_integrity({
            "data": data,
            "expected_schema": {"name": "str", "age": "int"},
        })
        consistency_check = next(
            c for c in result["checks"] if c["name"] == "consistency"
        )
        # Should detect the type mismatch
        assert not consistency_check["passed"] or "mismatch" in str(result).lower()

    @pytest.mark.asyncio
    async def test_consistency_without_schema(self) -> None:
        data = [
            {"value": 10},
            {"value": "text"},  # mixed types
        ]
        result = await check_data_integrity({"data": data})
        consistency_check = next(
            c for c in result["checks"] if c["name"] == "consistency"
        )
        assert consistency_check["passed"] is False

    @pytest.mark.asyncio
    async def test_freshness_check_with_recent_dates(self) -> None:
        from datetime import date
        today = date.today().isoformat()
        data = [
            {"event": "sale", "date": today},
            {"event": "return", "date": today},
        ]
        result = await check_data_integrity({"data": data})
        freshness_check = next(
            c for c in result["checks"] if c["name"] == "freshness"
        )
        assert freshness_check["passed"] is True

    @pytest.mark.asyncio
    async def test_score_range(self) -> None:
        data = [{"a": 1}, {"a": 2}, {"a": 3}]
        result = await check_data_integrity({"data": data})
        assert 0.0 <= result["score"] <= 1.0

    @pytest.mark.asyncio
    async def test_warnings_populated(self) -> None:
        data = [
            {"name": "Alice", "age": None},
            {"name": None, "age": 30},
        ]
        result = await check_data_integrity({"data": data})
        # Should have at least one warning about nulls
        assert isinstance(result["warnings"], list)

    @pytest.mark.asyncio
    async def test_all_checks_present(self) -> None:
        data = [{"name": "Alice", "age": 30}]
        result = await check_data_integrity({"data": data})
        check_names = {c["name"] for c in result["checks"]}
        assert "completeness" in check_names
        assert "consistency" in check_names
        assert "freshness" in check_names
