"""Analytics Agent.

Performs statistical analysis, anomaly detection, trend analysis,
regression, clustering, and forecasting by invoking tools on the
Compute Engine MCP server.
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.analytics.prompts import ANALYTICS_SYSTEM_PROMPT


class AnalyticsAgent(BaseAgent):
    """Specialist agent for quantitative analysis and statistical computation."""

    def __init__(self) -> None:
        super().__init__(
            agent_id="analytics-v1",
            name="Analytics Agent",
            description=(
                "Performs statistical analysis, anomaly detection, "
                "trend analysis, and forecasting"
            ),
            capabilities=[
                "statistics",
                "anomaly_detection",
                "trend_analysis",
                "regression",
                "clustering",
                "forecasting",
            ],
            mcp_server="compute-engine-server",
            model="gpt-4o",
        )

    def get_system_prompt(self) -> str:
        return ANALYTICS_SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Run one or more analytical operations on the supplied data.

        Task parameters:
            analyses  -- List of analysis names to run.  Defaults to
                         ``["statistics"]``.  Valid names: ``statistics``,
                         ``trend``, ``anomaly``, ``regression``,
                         ``clustering``, ``forecasting``.
            columns   -- Optional column subset to analyse.
            target    -- Target column for regression / forecasting.
            n_clusters -- Number of clusters for clustering (auto if omitted).
            forecast_periods -- Number of periods to forecast.

        Context parameters:
            data      -- List of row dicts (records orientation) from the
                         Data Ingestion Agent.
            columns   -- Column names present in the data.
        """
        analyses: list[str] = task.get("analyses", ["statistics"])
        data: list[dict[str, Any]] = context.get("data", [])
        columns: list[str] | None = task.get("columns") or context.get("columns")
        target: str | None = task.get("target")
        n_clusters: int | None = task.get("n_clusters")
        forecast_periods: int = task.get("forecast_periods", 6)

        self.logger.info(
            "analytics.execute",
            analyses=analyses,
            row_count=len(data),
        )

        # If upstream data came wrapped in a step output, unwrap it
        if not data:
            for key in ("step-ingest", "data_ingestion"):
                upstream = context.get(key, {})
                if isinstance(upstream, dict) and "data" in upstream:
                    data = upstream["data"]
                    columns = columns or upstream.get("columns")
                    break

        if not data:
            self.logger.warning("analytics.no_data")
            return {
                "analyses_requested": analyses,
                "error": "No input data available for analysis.",
                "results": {},
            }

        results: dict[str, Any] = {}

        for analysis in analyses:
            self.logger.info("analytics.run", analysis=analysis)

            if analysis == "statistics":
                results["statistics"] = await self._run_statistics(data, columns)

            elif analysis == "trend":
                results["trends"] = await self._run_trend_analysis(data, columns, target)

            elif analysis == "anomaly":
                results["anomalies"] = await self._run_anomaly_detection(data, columns)

            elif analysis == "regression":
                results["regression"] = await self._run_regression(data, columns, target)

            elif analysis == "clustering":
                results["clustering"] = await self._run_clustering(data, columns, n_clusters)

            elif analysis == "forecasting":
                results["forecasting"] = await self._run_forecasting(
                    data, target, forecast_periods
                )
            else:
                self.logger.warning("analytics.unknown_analysis", analysis=analysis)
                results[analysis] = {"error": f"Unknown analysis type: {analysis}"}

        # Build a top-level summary
        summary = self._build_summary(results, analyses)

        self.logger.info(
            "analytics.complete",
            analyses_run=list(results.keys()),
        )

        return {
            "analyses_requested": analyses,
            "results": results,
            "summary": summary,
            "row_count": len(data),
        }

    # ------------------------------------------------------------------
    # Individual analysis methods
    # ------------------------------------------------------------------

    async def _run_statistics(
        self,
        data: list[dict[str, Any]],
        columns: list[str] | None,
    ) -> dict[str, Any]:
        """Compute descriptive statistics via the run_statistics MCP tool."""
        result = await self.call_mcp_tool(
            "run_statistics",
            {"data": data, "columns": columns},
        )
        return result.get("data", result)

    async def _run_trend_analysis(
        self,
        data: list[dict[str, Any]],
        columns: list[str] | None,
        target: str | None,
    ) -> dict[str, Any]:
        """Detect temporal trends via the analyze_trends MCP tool."""
        # Identify a plausible time column and value column
        time_col, value_col = self._infer_time_value_columns(data, target)

        result = await self.call_mcp_tool(
            "analyze_trends",
            {
                "data": data,
                "time_column": time_col,
                "value_column": value_col,
            },
        )
        return result.get("data", result)

    async def _run_anomaly_detection(
        self,
        data: list[dict[str, Any]],
        columns: list[str] | None,
    ) -> dict[str, Any]:
        """Flag anomalous rows via the detect_anomalies MCP tool."""
        # Select numeric columns for anomaly detection
        numeric_columns = self._get_numeric_columns(data, columns)

        result = await self.call_mcp_tool(
            "detect_anomalies",
            {
                "data": data,
                "columns": numeric_columns,
                "method": "zscore",
                "threshold": 3.0,
            },
        )
        return result.get("data", result)

    async def _run_regression(
        self,
        data: list[dict[str, Any]],
        columns: list[str] | None,
        target: str | None,
    ) -> dict[str, Any]:
        """Run linear regression via the run_regression MCP tool."""
        numeric_cols = self._get_numeric_columns(data, columns)

        if not target and numeric_cols:
            target = numeric_cols[-1]  # Last numeric column as target
        features = [c for c in numeric_cols if c != target]

        result = await self.call_mcp_tool(
            "run_regression",
            {
                "data": data,
                "target": target or "",
                "features": features,
            },
        )
        return result.get("data", result)

    async def _run_clustering(
        self,
        data: list[dict[str, Any]],
        columns: list[str] | None,
        n_clusters: int | None,
    ) -> dict[str, Any]:
        """Segment data via the cluster_analysis MCP tool."""
        numeric_cols = self._get_numeric_columns(data, columns)

        result = await self.call_mcp_tool(
            "cluster_analysis",
            {
                "data": data,
                "columns": numeric_cols,
                "n_clusters": n_clusters or 3,
            },
        )
        return result.get("data", result)

    async def _run_forecasting(
        self,
        data: list[dict[str, Any]],
        target: str | None,
        periods: int,
    ) -> dict[str, Any]:
        """Generate forecasts via the forecast MCP tool."""
        time_col, value_col = self._infer_time_value_columns(data, target)

        result = await self.call_mcp_tool(
            "forecast",
            {
                "data": data,
                "time_column": time_col,
                "value_column": value_col,
                "periods": periods,
            },
        )
        return result.get("data", result)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_numeric_columns(
        data: list[dict[str, Any]],
        columns: list[str] | None,
    ) -> list[str]:
        """Return column names whose values are predominantly numeric."""
        if not data:
            return []

        candidate_cols = columns or list(data[0].keys())
        numeric: list[str] = []

        for col in candidate_cols:
            sample_values = [row.get(col) for row in data[:50] if row.get(col) is not None]
            if not sample_values:
                continue
            numeric_count = 0
            for v in sample_values:
                try:
                    float(v)
                    numeric_count += 1
                except (TypeError, ValueError):
                    pass
            if numeric_count / max(len(sample_values), 1) > 0.8:
                numeric.append(col)

        return numeric

    @staticmethod
    def _infer_time_value_columns(
        data: list[dict[str, Any]],
        target: str | None,
    ) -> tuple[str, str]:
        """Heuristically pick a time column and a value column.

        The time column is the first column whose name contains common
        temporal keywords.  The value column is ``target`` if provided,
        otherwise the first numeric-looking column that is not the time
        column.
        """
        if not data:
            return ("", target or "")

        cols = list(data[0].keys())
        time_keywords = {"date", "time", "timestamp", "created", "period", "month", "year", "day"}
        time_col = ""
        for c in cols:
            if any(kw in c.lower() for kw in time_keywords):
                time_col = c
                break
        if not time_col and cols:
            time_col = cols[0]

        if target:
            return (time_col, target)

        # Pick first numeric non-time column
        for c in cols:
            if c == time_col:
                continue
            sample = [row.get(c) for row in data[:10] if row.get(c) is not None]
            try:
                [float(v) for v in sample]
                return (time_col, c)
            except (TypeError, ValueError):
                continue

        return (time_col, cols[-1] if cols else "")

    @staticmethod
    def _build_summary(results: dict[str, Any], analyses: list[str]) -> str:
        """Produce a human-readable summary of the completed analyses."""
        parts: list[str] = [f"Completed {len(results)} of {len(analyses)} requested analyses."]

        if "statistics" in results:
            stats = results["statistics"]
            if isinstance(stats, dict) and "summary" in stats:
                parts.append(f"Statistics: {stats['summary']}")

        if "trends" in results:
            trends = results["trends"]
            if isinstance(trends, dict) and "trend_direction" in trends:
                parts.append(f"Trend direction: {trends['trend_direction']}.")

        if "anomalies" in results:
            anomalies = results["anomalies"]
            if isinstance(anomalies, dict):
                count = anomalies.get("anomaly_count", 0)
                parts.append(f"Anomalies detected: {count}.")

        if "regression" in results:
            reg = results["regression"]
            if isinstance(reg, dict) and "r_squared" in reg:
                parts.append(f"Regression R-squared: {reg['r_squared']:.4f}.")

        if "clustering" in results:
            clust = results["clustering"]
            if isinstance(clust, dict) and "n_clusters" in clust:
                parts.append(f"Clusters identified: {clust['n_clusters']}.")

        if "forecasting" in results:
            fc = results["forecasting"]
            if isinstance(fc, dict) and "forecast" in fc:
                parts.append(f"Forecast generated for {len(fc['forecast'])} periods.")

        return " ".join(parts)
