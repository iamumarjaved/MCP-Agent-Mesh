"""Presentation Agent.

Creates charts, compiles reports, and generates dashboard specifications
by invoking tools on the Rendering Engine MCP server.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.presentation.prompts import PRESENTATION_SYSTEM_PROMPT


class PresentationAgent(BaseAgent):
    """Specialist agent for visual communication and report assembly."""

    def __init__(self) -> None:
        super().__init__(
            agent_id="presentation-v1",
            name="Presentation Agent",
            description=(
                "Creates charts, compiles reports, and generates "
                "interactive dashboards"
            ),
            capabilities=[
                "chart_generation",
                "report_compilation",
                "dashboard_creation",
            ],
            mcp_server="rendering-engine-server",
            model="gpt-4o-mini",
        )

    def get_system_prompt(self) -> str:
        return PRESENTATION_SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Produce charts, reports, or dashboards from upstream outputs.

        Task parameters:
            action      -- ``"compile_report"`` (default), ``"charts_only"``,
                           ``"dashboard"``.
            format      -- ``"html"``, ``"markdown"``, ``"json"``
                           (default ``"markdown"``).
            audience    -- ``"executive"``, ``"analyst"``, ``"engineering"``
                           (default ``"executive"``).

        Context parameters:
            data        -- Raw data rows (optional; used for chart data).
            insights    -- List of insight dicts from the Insight Generator.
            narrative   -- Narrative dict from the Insight Generator.
            recommendations -- List of recommendation dicts.
            results     -- Analytics results (statistics, trends, etc.).
        """
        action: str = task.get("action", "compile_report")
        output_format: str = task.get("format", "markdown")
        audience: str = task.get("audience", "executive")

        # Gather upstream artefacts
        data = self._gather_data(context)
        insights = self._gather_insights(context)
        narrative = self._gather_narrative(context)
        recommendations = self._gather_recommendations(context)
        analytics_results = self._gather_analytics(context)

        self.logger.info(
            "presentation.execute",
            action=action,
            format=output_format,
            insight_count=len(insights),
        )

        # ------ Charts ------
        chart_specs = self._plan_charts(data, insights, analytics_results)
        rendered_charts: list[dict[str, Any]] = []
        for spec in chart_specs:
            chart = await self._render_chart(spec)
            rendered_charts.append(chart)

        if action == "charts_only":
            return {
                "action": action,
                "charts": rendered_charts,
                "chart_count": len(rendered_charts),
            }

        # ------ Dashboard ------
        if action == "dashboard":
            dashboard = self._build_dashboard(
                insights, rendered_charts, analytics_results, recommendations
            )
            return {
                "action": action,
                "dashboard": dashboard,
                "chart_count": len(rendered_charts),
            }

        # ------ Full report ------
        report = self._compile_report(
            narrative=narrative,
            insights=insights,
            charts=rendered_charts,
            recommendations=recommendations,
            analytics=analytics_results,
            output_format=output_format,
            audience=audience,
        )

        # Persist report via MCP tool
        await self.call_mcp_tool(
            "save_report",
            {"report": report, "format": output_format},
        )

        self.logger.info(
            "presentation.complete",
            action=action,
            chart_count=len(rendered_charts),
        )

        return {
            "action": action,
            "report": report,
            "charts": rendered_charts,
            "chart_count": len(rendered_charts),
            "format": output_format,
        }

    # ------------------------------------------------------------------
    # Chart planning and rendering
    # ------------------------------------------------------------------

    def _plan_charts(
        self,
        data: list[dict[str, Any]],
        insights: list[dict[str, Any]],
        analytics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Determine which charts to create based on available data and insights."""
        specs: list[dict[str, Any]] = []

        columns = list(data[0].keys()) if data else []

        # Detect numeric and categorical columns
        numeric_cols: list[str] = []
        categorical_cols: list[str] = []
        time_cols: list[str] = []
        time_keywords = {"date", "time", "timestamp", "created", "period", "month", "year"}

        for col in columns:
            if any(kw in col.lower() for kw in time_keywords):
                time_cols.append(col)
                continue
            sample_values = [row.get(col) for row in data[:20] if row.get(col) is not None]
            numeric_count = 0
            for v in sample_values:
                try:
                    float(v)
                    numeric_count += 1
                except (TypeError, ValueError):
                    pass
            if sample_values and numeric_count / len(sample_values) > 0.8:
                numeric_cols.append(col)
            elif sample_values:
                categorical_cols.append(col)

        # Chart 1: Time series line chart if time column exists
        if time_cols and numeric_cols:
            specs.append({
                "chart_type": "line",
                "title": f"{numeric_cols[0]} over time",
                "x": time_cols[0],
                "y": numeric_cols[0],
                "data": data,
            })

        # Chart 2: Bar chart for categorical breakdown
        if categorical_cols and numeric_cols:
            specs.append({
                "chart_type": "bar",
                "title": f"{numeric_cols[0]} by {categorical_cols[0]}",
                "x": categorical_cols[0],
                "y": numeric_cols[0],
                "data": data,
            })

        # Chart 3: Scatter plot for correlated numerics
        if len(numeric_cols) >= 2:
            specs.append({
                "chart_type": "scatter",
                "title": f"{numeric_cols[0]} vs {numeric_cols[1]}",
                "x": numeric_cols[0],
                "y": numeric_cols[1],
                "data": data,
            })

        # Chart 4: Histogram for distribution
        if numeric_cols:
            specs.append({
                "chart_type": "histogram",
                "title": f"Distribution of {numeric_cols[0]}",
                "x": numeric_cols[0],
                "bins": 20,
                "data": data,
            })

        # Chart 5: Insight-driven charts
        for insight in insights[:3]:
            evidence = insight.get("evidence", {})
            if isinstance(evidence, dict) and "columns" in evidence:
                cols = evidence["columns"]
                if len(cols) == 2 and all(c in columns for c in cols):
                    specs.append({
                        "chart_type": "scatter",
                        "title": insight.get("title", "Correlation"),
                        "x": cols[0],
                        "y": cols[1],
                        "data": data,
                    })

        return specs

    async def _render_chart(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Render a single chart via the rendering engine MCP tool."""
        result = await self.call_mcp_tool(
            "render_chart",
            {
                "chart_type": spec.get("chart_type", "bar"),
                "title": spec.get("title", "Chart"),
                "x": spec.get("x", ""),
                "y": spec.get("y", ""),
                "data": spec.get("data", [])[:200],  # Cap rows for rendering
                "options": {
                    "bins": spec.get("bins"),
                },
            },
        )

        return {
            "chart_type": spec.get("chart_type"),
            "title": spec.get("title"),
            "rendered": result.get("data", result),
            "status": "rendered",
        }

    # ------------------------------------------------------------------
    # Report compilation
    # ------------------------------------------------------------------

    def _compile_report(
        self,
        narrative: dict[str, Any],
        insights: list[dict[str, Any]],
        charts: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
        analytics: dict[str, Any],
        output_format: str,
        audience: str,
    ) -> dict[str, Any]:
        """Assemble a structured report from all available artefacts."""
        # Executive summary
        exec_summary = self._build_executive_summary(insights, audience)

        # Key metrics
        key_metrics = self._extract_key_metrics(analytics)

        # Structure the report
        report: dict[str, Any] = {
            "title": "Analysis Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "audience": audience,
            "format": output_format,
            "sections": [],
        }

        # Section 1: Executive Summary
        report["sections"].append({
            "heading": "Executive Summary",
            "content": exec_summary,
            "order": 1,
        })

        # Section 2: Key Metrics
        if key_metrics:
            report["sections"].append({
                "heading": "Key Metrics",
                "content": key_metrics,
                "order": 2,
            })

        # Section 3: Detailed Findings / Narrative
        narrative_text = narrative.get("narrative_text", "")
        if narrative_text:
            report["sections"].append({
                "heading": "Detailed Findings",
                "content": narrative_text,
                "order": 3,
            })

        # Section 4: Charts
        if charts:
            report["sections"].append({
                "heading": "Visualisations",
                "content": [
                    {"title": c.get("title", ""), "type": c.get("chart_type", "")}
                    for c in charts
                ],
                "chart_refs": [c.get("title", "") for c in charts],
                "order": 4,
            })

        # Section 5: Insights
        if insights:
            report["sections"].append({
                "heading": "Insights",
                "content": [
                    {
                        "title": i.get("title", ""),
                        "description": i.get("description", ""),
                        "impact": i.get("impact", ""),
                    }
                    for i in insights[:10]
                ],
                "order": 5,
            })

        # Section 6: Recommendations
        if recommendations:
            report["sections"].append({
                "heading": "Recommendations",
                "content": [
                    {
                        "title": r.get("title", ""),
                        "rationale": r.get("rationale", ""),
                        "priority": r.get("priority", 5),
                        "effort": r.get("effort", "medium"),
                    }
                    for r in recommendations
                ],
                "order": 6,
            })

        # Render to markdown if requested
        if output_format == "markdown":
            report["markdown"] = self._render_markdown(report)

        return report

    # ------------------------------------------------------------------
    # Dashboard specification
    # ------------------------------------------------------------------

    @staticmethod
    def _build_dashboard(
        insights: list[dict[str, Any]],
        charts: list[dict[str, Any]],
        analytics: dict[str, Any],
        recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a dashboard widget specification."""
        widgets: list[dict[str, Any]] = []

        # KPI cards from analytics summary
        results = analytics.get("results", analytics)
        stats = results.get("statistics", {})
        if isinstance(stats, dict):
            descriptive = stats.get("descriptive", {})
            for col, col_stats in list(descriptive.items())[:4]:
                if isinstance(col_stats, dict) and col_stats.get("type") == "numeric":
                    widgets.append({
                        "type": "kpi_card",
                        "title": col,
                        "value": col_stats.get("mean", 0),
                        "subtitle": f"Mean (n={col_stats.get('count', 0)})",
                    })

        # Chart widgets
        for chart in charts:
            widgets.append({
                "type": "chart",
                "chart_type": chart.get("chart_type", "bar"),
                "title": chart.get("title", "Chart"),
                "data_ref": chart.get("title", ""),
            })

        # Insight list widget
        if insights:
            widgets.append({
                "type": "insight_list",
                "title": "Key Insights",
                "items": [
                    {"title": i.get("title", ""), "impact": i.get("impact", "")}
                    for i in insights[:5]
                ],
            })

        # Recommendations widget
        if recommendations:
            widgets.append({
                "type": "action_items",
                "title": "Recommendations",
                "items": [
                    {"title": r.get("title", ""), "priority": r.get("priority", 5)}
                    for r in recommendations[:5]
                ],
            })

        return {
            "layout": "responsive_grid",
            "columns": 2,
            "widgets": widgets,
            "widget_count": len(widgets),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_executive_summary(
        insights: list[dict[str, Any]],
        audience: str,
    ) -> str:
        """Compose a 2-3 sentence executive summary from top insights."""
        if not insights:
            return "Analysis complete. No significant findings to report."

        high_impact = [i for i in insights if i.get("impact") == "high"]
        top = high_impact[:3] if high_impact else insights[:3]

        sentences: list[str] = []
        for insight in top:
            title = insight.get("title", "")
            desc = insight.get("description", "")
            # Take the first sentence of the description
            first_sentence = desc.split(". ")[0] + "." if desc else title + "."
            sentences.append(first_sentence)

        if audience == "executive":
            return " ".join(sentences[:3])
        return " ".join(sentences)

    @staticmethod
    def _extract_key_metrics(analytics: dict[str, Any]) -> list[dict[str, Any]]:
        """Pull headline metrics from analytics results for the KPI section."""
        metrics: list[dict[str, Any]] = []
        results = analytics.get("results", analytics)

        stats = results.get("statistics", {})
        if isinstance(stats, dict):
            descriptive = stats.get("descriptive", {})
            for col, col_stats in list(descriptive.items())[:6]:
                if isinstance(col_stats, dict) and col_stats.get("type") == "numeric":
                    metrics.append({
                        "name": col,
                        "value": col_stats.get("mean"),
                        "min": col_stats.get("min"),
                        "max": col_stats.get("max"),
                        "trend": None,
                    })

        return metrics

    @staticmethod
    def _render_markdown(report: dict[str, Any]) -> str:
        """Render the structured report as markdown text."""
        lines: list[str] = [f"# {report.get('title', 'Report')}\n"]
        lines.append(f"*Generated: {report.get('generated_at', '')}*\n")
        lines.append(f"*Audience: {report.get('audience', 'general')}*\n")
        lines.append("---\n")

        for section in sorted(report.get("sections", []), key=lambda s: s.get("order", 99)):
            heading = section.get("heading", "")
            content = section.get("content", "")
            lines.append(f"## {heading}\n")

            if isinstance(content, str):
                lines.append(content + "\n")
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        title = item.get("title", "")
                        desc = item.get("description", item.get("rationale", ""))
                        if title:
                            lines.append(f"- **{title}**")
                            if desc:
                                lines.append(f"  {desc}")
                    else:
                        lines.append(f"- {item}")
                lines.append("")
            elif isinstance(content, dict):
                for k, v in content.items():
                    lines.append(f"- **{k}:** {v}")
                lines.append("")

            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Context gathering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gather_data(context: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract raw data rows from context."""
        if "data" in context and isinstance(context["data"], list):
            return context["data"]
        for key in ("step-ingest", "data_ingestion"):
            upstream = context.get(key, {})
            if isinstance(upstream, dict) and "data" in upstream:
                return upstream["data"]
        return []

    @staticmethod
    def _gather_insights(context: dict[str, Any]) -> list[dict[str, Any]]:
        if "insights" in context and isinstance(context["insights"], list):
            return context["insights"]
        for key in ("step-insights", "insight_generator"):
            upstream = context.get(key, {})
            if isinstance(upstream, dict) and "insights" in upstream:
                return upstream["insights"]
        return []

    @staticmethod
    def _gather_narrative(context: dict[str, Any]) -> dict[str, Any]:
        if "narrative" in context and isinstance(context["narrative"], dict):
            return context["narrative"]
        for key in ("step-insights", "insight_generator"):
            upstream = context.get(key, {})
            if isinstance(upstream, dict) and "narrative" in upstream:
                return upstream["narrative"]
        return {}

    @staticmethod
    def _gather_recommendations(context: dict[str, Any]) -> list[dict[str, Any]]:
        if "recommendations" in context and isinstance(context["recommendations"], list):
            return context["recommendations"]
        for key in ("step-insights", "insight_generator"):
            upstream = context.get(key, {})
            if isinstance(upstream, dict) and "recommendations" in upstream:
                return upstream["recommendations"]
        return []

    @staticmethod
    def _gather_analytics(context: dict[str, Any]) -> dict[str, Any]:
        if "results" in context and isinstance(context["results"], dict):
            return context
        for key in ("step-analytics", "analytics"):
            upstream = context.get(key, {})
            if isinstance(upstream, dict) and "results" in upstream:
                return upstream
        return {}
