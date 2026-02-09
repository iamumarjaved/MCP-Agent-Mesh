"""Tests for compute engine MCP server tools: statistics, anomalies, trends."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from src.mcp_servers.compute_engine.tools.run_statistics import run_statistics
from src.mcp_servers.compute_engine.tools.detect_anomalies import detect_anomalies
from src.mcp_servers.compute_engine.tools.analyze_trends import analyze_trends


# ---------------------------------------------------------------------------
# run_statistics
# ---------------------------------------------------------------------------

class TestRunStatistics:

    @pytest.mark.asyncio
    async def test_basic_statistics(self, sample_numeric_data: list[dict]) -> None:
        result = await run_statistics(sample_numeric_data)
        assert result["error"] is None
        assert "a" in result["descriptive"]
        assert "b" in result["descriptive"]

        desc_a = result["descriptive"]["a"]
        assert desc_a["type"] == "numeric"
        assert desc_a["count"] == 10
        assert desc_a["min"] == 10
        assert desc_a["max"] == 55
        assert desc_a["mean"] is not None
        assert desc_a["std"] is not None

    @pytest.mark.asyncio
    async def test_categorical_stats(self, sample_numeric_data: list[dict]) -> None:
        result = await run_statistics(sample_numeric_data)
        desc_c = result["descriptive"]["c"]
        assert desc_c["type"] == "categorical"
        assert desc_c["unique"] == 3

    @pytest.mark.asyncio
    async def test_correlations(self, sample_numeric_data: list[dict]) -> None:
        result = await run_statistics(sample_numeric_data)
        assert "a" in result["correlations"]
        # Diagonal should be 1.0
        assert result["correlations"]["a"]["a"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_column_subset(self, sample_numeric_data: list[dict]) -> None:
        result = await run_statistics(sample_numeric_data, columns=["a", "b"])
        assert "a" in result["descriptive"]
        assert "b" in result["descriptive"]
        assert "c" not in result["descriptive"]

    @pytest.mark.asyncio
    async def test_missing_column(self, sample_numeric_data: list[dict]) -> None:
        result = await run_statistics(sample_numeric_data, columns=["nonexistent"])
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_empty_data(self) -> None:
        result = await run_statistics([])
        assert result["summary"] == "No data provided."

    @pytest.mark.asyncio
    async def test_summary_includes_dataset_info(self, sample_numeric_data: list[dict]) -> None:
        result = await run_statistics(sample_numeric_data)
        assert "10 rows" in result["summary"]
        assert "3 columns" in result["summary"]


# ---------------------------------------------------------------------------
# detect_anomalies
# ---------------------------------------------------------------------------

class TestDetectAnomalies:

    @pytest.fixture
    def data_with_outlier(self) -> list[dict]:
        """Dataset with a clear outlier."""
        normal = [{"value": float(i)} for i in range(10, 20)]
        outlier = [{"value": 1000.0}]
        return normal + outlier

    @pytest.mark.asyncio
    async def test_zscore_detects_outlier(self, data_with_outlier: list[dict]) -> None:
        result = await detect_anomalies(
            data_with_outlier, column="value", method="zscore", threshold=2.0,
        )
        assert result["error"] is None
        assert result["anomaly_count"] >= 1
        anomaly_values = [a["value"] for a in result["anomalies"]]
        assert 1000.0 in anomaly_values

    @pytest.mark.asyncio
    async def test_iqr_detects_outlier(self, data_with_outlier: list[dict]) -> None:
        result = await detect_anomalies(
            data_with_outlier, column="value", method="iqr", threshold=1.5,
        )
        assert result["error"] is None
        assert result["anomaly_count"] >= 1

    @pytest.mark.asyncio
    async def test_no_anomalies_in_uniform_data(self) -> None:
        data = [{"value": 10.0} for _ in range(20)]
        result = await detect_anomalies(data, column="value", method="zscore")
        assert result["anomaly_count"] == 0

    @pytest.mark.asyncio
    async def test_missing_column(self) -> None:
        data = [{"a": 1}, {"a": 2}]
        result = await detect_anomalies(data, column="nonexistent")
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_method(self) -> None:
        data = [{"value": 1}]
        result = await detect_anomalies(data, column="value", method="invalid")
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_empty_data(self) -> None:
        result = await detect_anomalies([], column="value")
        assert result["anomaly_count"] == 0
        assert result["total_count"] == 0

    @pytest.mark.asyncio
    async def test_anomaly_rate_calculation(self, data_with_outlier: list[dict]) -> None:
        result = await detect_anomalies(
            data_with_outlier, column="value", method="zscore", threshold=2.0,
        )
        expected_rate = result["anomaly_count"] / result["total_count"]
        assert abs(result["anomaly_rate"] - expected_rate) < 0.01


# ---------------------------------------------------------------------------
# analyze_trends
# ---------------------------------------------------------------------------

class TestAnalyzeTrends:

    @pytest.fixture
    def time_series_data(self) -> list[dict]:
        """Generate upward-trending time series data."""
        base = date(2025, 1, 1)
        return [
            {"date": (base + timedelta(days=i * 7)).isoformat(), "value": 100 + i * 5 + (i % 3)}
            for i in range(52)
        ]

    @pytest.mark.asyncio
    async def test_basic_trend_analysis(self, time_series_data: list[dict]) -> None:
        result = await analyze_trends(
            time_series_data,
            date_column="date",
            value_column="value",
            period="monthly",
        )
        assert result["error"] is None
        assert result["trend_direction"] == "up"
        assert len(result["period_changes"]) > 0
        assert "moving_averages" in result

    @pytest.mark.asyncio
    async def test_moving_averages(self, time_series_data: list[dict]) -> None:
        result = await analyze_trends(
            time_series_data, date_column="date", value_column="value",
        )
        assert "ma_7" in result["moving_averages"]
        assert "ma_30" in result["moving_averages"]
        assert len(result["moving_averages"]["ma_7"]) > 0

    @pytest.mark.asyncio
    async def test_seasonality_detection(self, time_series_data: list[dict]) -> None:
        result = await analyze_trends(
            time_series_data, date_column="date", value_column="value",
        )
        if result["seasonality"]:
            assert "peak_month" in result["seasonality"]
            assert "trough_month" in result["seasonality"]

    @pytest.mark.asyncio
    async def test_missing_date_column(self) -> None:
        data = [{"value": 10}]
        result = await analyze_trends(data, date_column="missing", value_column="value")
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_missing_value_column(self) -> None:
        data = [{"date": "2025-01-01"}]
        result = await analyze_trends(data, date_column="date", value_column="missing")
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_empty_data(self) -> None:
        result = await analyze_trends([], date_column="date", value_column="value")
        assert result["error"] is not None
        assert result["trend_direction"] == "unknown"

    @pytest.mark.asyncio
    async def test_invalid_period(self) -> None:
        data = [{"date": "2025-01-01", "value": 10}]
        result = await analyze_trends(
            data, date_column="date", value_column="value", period="biweekly",
        )
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_summary_text(self, time_series_data: list[dict]) -> None:
        result = await analyze_trends(
            time_series_data, date_column="date", value_column="value",
        )
        assert "Analysed" in result["summary"]
        assert "Trend direction" in result["summary"]
