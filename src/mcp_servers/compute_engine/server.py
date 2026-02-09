"""Compute Engine MCP Server.

Exposes statistical, analytical, and machine-learning tools over the MCP
protocol.  Each tool is implemented in a dedicated module under
``tools/`` and registered during server initialisation.
"""

from __future__ import annotations

from src.mcp_servers.base_server import BaseMCPServer
from src.mcp_servers.compute_engine.tools.analyze_trends import (
    analyze_trends,
)
from src.mcp_servers.compute_engine.tools.cluster_analysis import (
    cluster_analysis,
)
from src.mcp_servers.compute_engine.tools.detect_anomalies import (
    detect_anomalies,
)
from src.mcp_servers.compute_engine.tools.forecast import forecast
from src.mcp_servers.compute_engine.tools.run_regression import (
    run_regression,
)
from src.mcp_servers.compute_engine.tools.run_statistics import (
    run_statistics,
)


class ComputeEngineServer(BaseMCPServer):
    """MCP server providing data analytics and computation tools.

    Registered tools
    ----------------
    * **run_statistics** -- descriptive statistics, correlations
    * **detect_anomalies** -- Z-score / IQR / Isolation Forest outlier detection
    * **analyze_trends** -- time-series trend & seasonality analysis
    * **run_regression** -- linear / logistic regression
    * **cluster_analysis** -- KMeans / DBSCAN clustering
    * **forecast** -- linear-trend + seasonal forecasting
    """

    def __init__(self) -> None:
        super().__init__(name="compute-engine-server", version="1.0.0")
        self._register_compute_tools()

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_compute_tools(self) -> None:
        """Wire each tool module into the MCP tool registry."""

        self.register_tool(
            name="run_statistics",
            description=(
                "Compute descriptive statistics (mean, median, std, quartiles, "
                "skewness, kurtosis) for numeric columns and value counts / mode "
                "for categorical columns.  Also returns a correlation matrix."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of row-dicts representing the dataset.",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional subset of columns to analyse.",
                        "default": None,
                    },
                },
                "required": ["data"],
            },
            handler=_dispatch_run_statistics,
        )

        self.register_tool(
            name="detect_anomalies",
            description=(
                "Detect anomalies / outliers in a numeric column using Z-score, "
                "IQR, or Isolation Forest methods."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of row-dicts.",
                    },
                    "column": {
                        "type": "string",
                        "description": "Numeric column to check for anomalies.",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["zscore", "iqr", "isolation_forest"],
                        "default": "zscore",
                    },
                    "threshold": {
                        "type": "number",
                        "default": 3.0,
                        "description": (
                            "Sensitivity threshold.  Z-score: number of std devs; "
                            "IQR: multiplier (commonly 1.5).  Ignored for isolation_forest."
                        ),
                    },
                },
                "required": ["data", "column"],
            },
            handler=_dispatch_detect_anomalies,
        )

        self.register_tool(
            name="analyze_trends",
            description=(
                "Analyse time-series trends: moving averages, period-over-period "
                "change, trend direction, and basic seasonality."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of row-dicts.",
                    },
                    "date_column": {
                        "type": "string",
                        "description": "Column containing date / datetime values.",
                    },
                    "value_column": {
                        "type": "string",
                        "description": "Numeric column to analyse.",
                    },
                    "period": {
                        "type": "string",
                        "enum": ["daily", "weekly", "monthly", "quarterly", "yearly"],
                        "default": "monthly",
                    },
                },
                "required": ["data", "date_column", "value_column"],
            },
            handler=_dispatch_analyze_trends,
        )

        self.register_tool(
            name="run_regression",
            description=(
                "Fit a linear or logistic regression model and return "
                "coefficients, R-squared, and feature importance."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of row-dicts.",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target (dependent) column.",
                    },
                    "features": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Feature (independent) columns.",
                    },
                    "model_type": {
                        "type": "string",
                        "enum": ["linear", "logistic"],
                        "default": "linear",
                    },
                },
                "required": ["data", "target", "features"],
            },
            handler=_dispatch_run_regression,
        )

        self.register_tool(
            name="cluster_analysis",
            description=(
                "Cluster data points using KMeans or DBSCAN.  Returns cluster "
                "assignments, silhouette score, sizes, and centroids."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of row-dicts.",
                    },
                    "features": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns to use as clustering features.",
                    },
                    "n_clusters": {
                        "type": "integer",
                        "default": 3,
                        "description": "Desired number of clusters (KMeans only).",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["kmeans", "dbscan"],
                        "default": "kmeans",
                    },
                },
                "required": ["data", "features"],
            },
            handler=_dispatch_cluster_analysis,
        )

        self.register_tool(
            name="forecast",
            description=(
                "Produce a simple forecast using linear trend extrapolation "
                "combined with monthly seasonal averages.  Returns predicted "
                "values with confidence intervals."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of row-dicts.",
                    },
                    "date_column": {
                        "type": "string",
                        "description": "Column containing date / datetime values.",
                    },
                    "value_column": {
                        "type": "string",
                        "description": "Numeric column to forecast.",
                    },
                    "periods": {
                        "type": "integer",
                        "default": 12,
                        "description": "Number of future months to forecast.",
                    },
                },
                "required": ["data", "date_column", "value_column"],
            },
            handler=_dispatch_forecast,
        )


# ------------------------------------------------------------------
# Dispatch wrappers
#
# The MCP SDK calls handlers with a single ``arguments: dict`` parameter.
# These thin wrappers unpack the dict into the tool function's kwargs.
# ------------------------------------------------------------------


async def _dispatch_run_statistics(arguments: dict) -> dict:
    return await run_statistics(
        data=arguments["data"],
        columns=arguments.get("columns"),
    )


async def _dispatch_detect_anomalies(arguments: dict) -> dict:
    return await detect_anomalies(
        data=arguments["data"],
        column=arguments["column"],
        method=arguments.get("method", "zscore"),
        threshold=arguments.get("threshold", 3.0),
    )


async def _dispatch_analyze_trends(arguments: dict) -> dict:
    return await analyze_trends(
        data=arguments["data"],
        date_column=arguments["date_column"],
        value_column=arguments["value_column"],
        period=arguments.get("period", "monthly"),
    )


async def _dispatch_run_regression(arguments: dict) -> dict:
    return await run_regression(
        data=arguments["data"],
        target=arguments["target"],
        features=arguments["features"],
        model_type=arguments.get("model_type", "linear"),
    )


async def _dispatch_cluster_analysis(arguments: dict) -> dict:
    return await cluster_analysis(
        data=arguments["data"],
        features=arguments["features"],
        n_clusters=arguments.get("n_clusters", 3),
        method=arguments.get("method", "kmeans"),
    )


async def _dispatch_forecast(arguments: dict) -> dict:
    return await forecast(
        data=arguments["data"],
        date_column=arguments["date_column"],
        value_column=arguments["value_column"],
        periods=arguments.get("periods", 12),
    )
