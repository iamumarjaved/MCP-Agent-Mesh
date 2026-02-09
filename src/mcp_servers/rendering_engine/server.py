"""Rendering Engine MCP Server.

Provides chart generation, report compilation, and dashboard creation
tools for the Agent Mesh.  Uses Plotly for chart rendering and produces
Markdown, HTML, or interactive dashboard output.
"""

from __future__ import annotations

from src.mcp_servers.base_server import BaseMCPServer
from src.mcp_servers.rendering_engine.tools.generate_chart import generate_chart
from src.mcp_servers.rendering_engine.tools.compile_report import compile_report
from src.mcp_servers.rendering_engine.tools.create_dashboard import create_dashboard


class RenderingEngineServer(BaseMCPServer):
    """MCP server that exposes visualisation and report rendering tools."""

    def __init__(self) -> None:
        super().__init__(name="rendering-engine-server", version="1.0.0")
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all rendering-engine tools with the MCP server."""

        self.register_tool(
            name="generate_chart",
            description=(
                "Generate a Plotly chart from tabular data. Supports bar, "
                "line, scatter, heatmap, pie, and histogram chart types. "
                "Returns the chart as a serialised Plotly JSON string."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of row objects (column-name -> value).",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "scatter", "heatmap", "pie", "histogram"],
                        "description": "Type of chart to generate.",
                    },
                    "x_column": {
                        "type": "string",
                        "description": "Column name for the x-axis.",
                    },
                    "y_column": {
                        "type": "string",
                        "description": "Column name for the y-axis.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Chart title.",
                        "default": "",
                    },
                    "color_column": {
                        "type": "string",
                        "description": "Optional column for colour grouping.",
                        "default": None,
                    },
                },
                "required": ["data", "chart_type", "x_column", "y_column"],
            },
            handler=generate_chart,
        )

        self.register_tool(
            name="compile_report",
            description=(
                "Compile text sections and optional charts into a formatted "
                "report. Supports Markdown and HTML output formats."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Report title.",
                    },
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["heading", "content"],
                        },
                        "description": "Ordered list of report sections.",
                    },
                    "charts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "chart_json": {"type": "string"},
                            },
                            "required": ["title", "chart_json"],
                        },
                        "description": "Optional list of charts to embed.",
                        "default": None,
                    },
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "html"],
                        "description": "Output format for the compiled report.",
                        "default": "markdown",
                    },
                },
                "required": ["title", "sections"],
            },
            handler=compile_report,
        )

        self.register_tool(
            name="create_dashboard",
            description=(
                "Create an interactive HTML dashboard with embedded Plotly "
                "charts and optional KPI metric cards."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Dashboard title.",
                    },
                    "charts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "chart_json": {"type": "string"},
                            },
                            "required": ["title", "chart_json"],
                        },
                        "description": "Charts to include in the dashboard.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Summary text displayed at the top of the dashboard.",
                    },
                    "metrics": {
                        "type": "object",
                        "description": "Key-value pairs rendered as KPI cards.",
                        "default": None,
                    },
                },
                "required": ["title", "charts", "summary"],
            },
            handler=create_dashboard,
        )


if __name__ == "__main__":
    server = RenderingEngineServer()
    server.run_stdio()
