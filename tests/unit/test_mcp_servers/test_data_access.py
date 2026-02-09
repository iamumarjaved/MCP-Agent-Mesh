"""Tests for data access MCP server tools: fetch_csv, profile, clean, transform."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import pytest

from src.mcp_servers.data_access.tools.clean_data import clean_data
from src.mcp_servers.data_access.tools.profile_data import profile_data
from src.mcp_servers.data_access.tools.transform_data import transform_data


# ---------------------------------------------------------------------------
# profile_data
# ---------------------------------------------------------------------------

class TestProfileData:

    @pytest.mark.asyncio
    async def test_profile_basic(self, sample_numeric_data: list[dict]) -> None:
        result = await profile_data(sample_numeric_data)
        assert result["row_count"] == 10
        assert result["column_count"] == 3
        assert "a" in result["columns"]
        assert "b" in result["columns"]
        assert "c" in result["columns"]
        assert 0 <= result["quality_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_profile_empty_data(self) -> None:
        result = await profile_data([])
        assert result["row_count"] == 0
        assert result["column_count"] == 0
        assert result["quality_score"] == 0.0

    @pytest.mark.asyncio
    async def test_profile_numeric_stats(self, sample_numeric_data: list[dict]) -> None:
        result = await profile_data(sample_numeric_data)
        col_a = result["columns"]["a"]
        assert col_a["dtype"] == "int64"
        assert col_a["null_count"] == 0
        assert col_a["min"] is not None
        assert col_a["max"] is not None
        assert col_a["mean"] is not None

    @pytest.mark.asyncio
    async def test_profile_categorical_stats(self, sample_numeric_data: list[dict]) -> None:
        result = await profile_data(sample_numeric_data)
        col_c = result["columns"]["c"]
        assert "top_values" in col_c
        assert col_c["unique_count"] == 3

    @pytest.mark.asyncio
    async def test_profile_with_nulls(self, sample_data_with_nulls: list[dict]) -> None:
        result = await profile_data(sample_data_with_nulls)
        assert result["columns"]["age"]["null_count"] == 1
        assert result["columns"]["score"]["null_count"] == 1
        assert result["quality_score"] < 1.0


# ---------------------------------------------------------------------------
# clean_data
# ---------------------------------------------------------------------------

class TestCleanData:

    @pytest.mark.asyncio
    async def test_dedup(self, sample_data_with_nulls: list[dict]) -> None:
        result = await clean_data(sample_data_with_nulls, operations=["dedup"])
        assert result["rows_after"] <= result["rows_before"]
        assert "dedup" in result["operations_applied"]

    @pytest.mark.asyncio
    async def test_impute(self, sample_data_with_nulls: list[dict]) -> None:
        result = await clean_data(sample_data_with_nulls, operations=["impute"])
        # After imputation, no null values should remain in numeric columns
        for row in result["data"]:
            assert row.get("age") is not None
            assert row.get("score") is not None

    @pytest.mark.asyncio
    async def test_normalize(self, sample_numeric_data: list[dict]) -> None:
        result = await clean_data(sample_numeric_data, operations=["normalize"])
        for row in result["data"]:
            assert 0.0 <= row["a"] <= 1.0
            assert 0.0 <= row["b"] <= 1.0

    @pytest.mark.asyncio
    async def test_pipeline_order(self, sample_data_with_nulls: list[dict]) -> None:
        result = await clean_data(
            sample_data_with_nulls,
            operations=["dedup", "impute"],
        )
        assert result["operations_applied"] == ["dedup", "impute"]
        assert result["rows_after"] <= result["rows_before"]

    @pytest.mark.asyncio
    async def test_unsupported_operation(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            await clean_data([{"a": 1}], operations=["magic"])

    @pytest.mark.asyncio
    async def test_empty_data(self) -> None:
        result = await clean_data([], operations=["dedup"])
        assert result["data"] == []
        assert result["rows_before"] == 0
        assert result["rows_after"] == 0


# ---------------------------------------------------------------------------
# transform_data
# ---------------------------------------------------------------------------

class TestTransformData:

    @pytest.mark.asyncio
    async def test_filter_eq(self, sample_numeric_data: list[dict]) -> None:
        result = await transform_data(
            sample_numeric_data,
            operation="filter",
            params={"column": "c", "operator": "eq", "value": "x"},
        )
        assert all(row["c"] == "x" for row in result["data"])
        assert result["row_count"] > 0

    @pytest.mark.asyncio
    async def test_filter_gt(self, sample_numeric_data: list[dict]) -> None:
        result = await transform_data(
            sample_numeric_data,
            operation="filter",
            params={"column": "a", "operator": "gt", "value": 30},
        )
        assert all(row["a"] > 30 for row in result["data"])

    @pytest.mark.asyncio
    async def test_aggregate_sum(self, sample_numeric_data: list[dict]) -> None:
        result = await transform_data(
            sample_numeric_data,
            operation="aggregate",
            params={"group_by": "c", "agg_func": "sum"},
        )
        assert result["row_count"] == 3  # x, y, z
        assert all("a" in row for row in result["data"])

    @pytest.mark.asyncio
    async def test_aggregate_mean(self, sample_numeric_data: list[dict]) -> None:
        result = await transform_data(
            sample_numeric_data,
            operation="aggregate",
            params={"group_by": "c", "agg_func": "mean"},
        )
        assert result["row_count"] == 3

    @pytest.mark.asyncio
    async def test_sort_ascending(self, sample_numeric_data: list[dict]) -> None:
        result = await transform_data(
            sample_numeric_data,
            operation="sort",
            params={"column": "a", "ascending": True},
        )
        values = [row["a"] for row in result["data"]]
        assert values == sorted(values)

    @pytest.mark.asyncio
    async def test_sort_descending(self, sample_numeric_data: list[dict]) -> None:
        result = await transform_data(
            sample_numeric_data,
            operation="sort",
            params={"column": "a", "ascending": False},
        )
        values = [row["a"] for row in result["data"]]
        assert values == sorted(values, reverse=True)

    @pytest.mark.asyncio
    async def test_select_columns(self, sample_numeric_data: list[dict]) -> None:
        result = await transform_data(
            sample_numeric_data,
            operation="select",
            params={"columns": ["a", "c"]},
        )
        assert all(set(row.keys()) == {"a", "c"} for row in result["data"])

    @pytest.mark.asyncio
    async def test_unsupported_operation(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            await transform_data([{"a": 1}], operation="pivot", params={})

    @pytest.mark.asyncio
    async def test_empty_data(self) -> None:
        result = await transform_data([], operation="filter", params={"column": "a"})
        assert result["data"] == []
        assert result["row_count"] == 0

    @pytest.mark.asyncio
    async def test_filter_missing_column(self, sample_numeric_data: list[dict]) -> None:
        with pytest.raises(ValueError, match="not found"):
            await transform_data(
                sample_numeric_data,
                operation="filter",
                params={"column": "nonexistent", "operator": "eq", "value": 1},
            )


# ---------------------------------------------------------------------------
# fetch_csv (requires temp file)
# ---------------------------------------------------------------------------

class TestFetchCSV:

    @pytest.mark.asyncio
    async def test_fetch_csv_basic(self, tmp_path: Path) -> None:
        from src.mcp_servers.data_access.tools.fetch_csv import fetch_csv

        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["a", "b", "c"])
            writer.writeheader()
            writer.writerow({"a": 1, "b": 2, "c": "x"})
            writer.writerow({"a": 3, "b": 4, "c": "y"})

        result = await fetch_csv(str(csv_path))
        assert result["row_count"] == 2
        assert result["columns"] == ["a", "b", "c"]
        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_fetch_csv_not_found(self) -> None:
        from src.mcp_servers.data_access.tools.fetch_csv import fetch_csv

        with pytest.raises(FileNotFoundError):
            await fetch_csv("/nonexistent/file.csv")
