"""Compute Engine MCP tools."""

from src.mcp_servers.compute_engine.tools.run_statistics import run_statistics
from src.mcp_servers.compute_engine.tools.detect_anomalies import detect_anomalies
from src.mcp_servers.compute_engine.tools.analyze_trends import analyze_trends
from src.mcp_servers.compute_engine.tools.run_regression import run_regression
from src.mcp_servers.compute_engine.tools.cluster_analysis import cluster_analysis
from src.mcp_servers.compute_engine.tools.forecast import forecast

__all__ = [
    "run_statistics",
    "detect_anomalies",
    "analyze_trends",
    "run_regression",
    "cluster_analysis",
    "forecast",
]
