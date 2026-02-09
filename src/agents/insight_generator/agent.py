"""Insight Generator Agent.

Transforms analytical results into business insights, narratives, and
recommendations by combining RAG-retrieved context with the findings
from the Analytics Agent.
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.insight_generator.prompts import INSIGHT_GENERATOR_SYSTEM_PROMPT


class InsightGeneratorAgent(BaseAgent):
    """Specialist agent for turning numbers into business narratives."""

    def __init__(self) -> None:
        super().__init__(
            agent_id="insight-generator-v1",
            name="Insight Generator Agent",
            description=(
                "Transforms analytical results into business insights "
                "and recommendations using RAG-enriched context"
            ),
            capabilities=[
                "insight_generation",
                "recommendations",
                "rag_retrieval",
                "narrative_generation",
                "benchmark_comparison",
            ],
            mcp_server="knowledge-base-server",
            model="gpt-4o",
        )

    def get_system_prompt(self) -> str:
        return INSIGHT_GENERATOR_SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Generate insights from upstream analytical outputs.

        Task parameters:
            action               -- ``"generate_insights"`` (default),
                                    ``"recommendations_only"``,
                                    ``"narrative_only"``.
            detail_level         -- ``"executive"``, ``"detailed"``, or
                                    ``"technical"`` (default ``"executive"``).
            include_benchmarks   -- Whether to retrieve and compare
                                    benchmarks (default ``True``).
            top_k_context        -- Number of RAG results to retrieve
                                    (default ``5``).

        Context parameters:
            results              -- Analytics results dict from the
                                    Analytics Agent.
            data                 -- Raw data if available.
        """
        action: str = task.get("action", "generate_insights")
        detail_level: str = task.get("detail_level", "executive")
        include_benchmarks: bool = task.get("include_benchmarks", True)
        top_k: int = task.get("top_k_context", 5)
        request: str = task.get("request", "")

        # Gather analytical results from context
        analytics_results = self._extract_analytics_results(context)

        self.logger.info(
            "insight_generator.execute",
            action=action,
            detail_level=detail_level,
            has_analytics=bool(analytics_results),
        )

        # ------ Step 1: RAG context retrieval ------
        rag_context = await self._retrieve_context(
            analytics_results, request, top_k
        )

        # ------ Step 2: Benchmark lookup (optional) ------
        benchmarks: dict[str, Any] = {}
        if include_benchmarks:
            benchmarks = await self._retrieve_benchmarks(analytics_results)

        # ------ Step 3: Extract insights ------
        insights = self._extract_insights(analytics_results, rag_context, benchmarks)

        if action == "recommendations_only":
            recommendations = self._generate_recommendations(insights)
            return {
                "action": action,
                "recommendations": recommendations,
                "insight_count": len(insights),
            }

        # ------ Step 4: Generate narrative ------
        narrative_result = await self._generate_narrative(
            analytics_results, insights, detail_level
        )

        if action == "narrative_only":
            return {
                "action": action,
                "narrative": narrative_result,
                "insight_count": len(insights),
            }

        # ------ Step 5: Generate recommendations ------
        recommendations = self._generate_recommendations(insights)

        # ------ Step 6: Benchmark comparison ------
        benchmark_comparison: list[dict[str, Any]] = []
        if benchmarks:
            benchmark_comparison = self._compare_benchmarks(
                analytics_results, benchmarks
            )

        self.logger.info(
            "insight_generator.complete",
            insight_count=len(insights),
            recommendation_count=len(recommendations),
        )

        return {
            "action": action,
            "insights": insights,
            "recommendations": recommendations,
            "narrative": narrative_result,
            "benchmarks": benchmarks,
            "benchmark_comparison": benchmark_comparison,
            "rag_context": rag_context,
            "detail_level": detail_level,
        }

    # ------------------------------------------------------------------
    # RAG retrieval
    # ------------------------------------------------------------------

    async def _retrieve_context(
        self,
        analytics_results: dict[str, Any],
        request: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Fetch relevant knowledge-base passages via RAG."""
        # Build a query from the analytics summary and user request
        summary = ""
        if isinstance(analytics_results.get("summary"), str):
            summary = analytics_results["summary"]

        query = f"{request} {summary}".strip() or "business analysis insights"

        result = await self.call_mcp_tool(
            "retrieve_context",
            {"query": query, "top_k": top_k},
        )

        raw_results = result.get("data", result)
        if isinstance(raw_results, dict) and "results" in raw_results:
            return raw_results["results"]
        return raw_results if isinstance(raw_results, list) else []

    async def _retrieve_benchmarks(
        self,
        analytics_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Look up industry benchmarks for key metrics found in the analysis."""
        benchmark_metrics = self._identify_benchmark_metrics(analytics_results)
        benchmarks: dict[str, Any] = {}

        for metric in benchmark_metrics:
            result = await self.call_mcp_tool(
                "search_benchmarks",
                {"metric": metric, "industry": "technology"},
            )
            benchmarks[metric] = result.get("data", result)

        return benchmarks

    # ------------------------------------------------------------------
    # Insight extraction
    # ------------------------------------------------------------------

    def _extract_insights(
        self,
        analytics_results: dict[str, Any],
        rag_context: list[dict[str, Any]],
        benchmarks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Derive business insights from analytics + context + benchmarks.

        In production this would be an LLM call.  The current
        implementation uses rule-based heuristics.
        """
        insights: list[dict[str, Any]] = []

        results = analytics_results.get("results", analytics_results)

        # --- Insights from statistics ---
        stats = results.get("statistics", {})
        if isinstance(stats, dict):
            descriptive = stats.get("descriptive", {})
            for col, col_stats in descriptive.items():
                if not isinstance(col_stats, dict):
                    continue
                if col_stats.get("type") == "numeric":
                    std = col_stats.get("std")
                    mean = col_stats.get("mean")
                    if std is not None and mean is not None and mean != 0:
                        cv = abs(std / mean)
                        if cv > 0.5:
                            insights.append({
                                "title": f"High variability in {col}",
                                "description": (
                                    f"The coefficient of variation for '{col}' is "
                                    f"{cv:.2f}, indicating substantial spread relative "
                                    f"to the mean ({mean:.2f}). This warrants investigation "
                                    f"into the drivers of this volatility."
                                ),
                                "evidence": {
                                    "column": col,
                                    "mean": mean,
                                    "std": std,
                                    "cv": round(cv, 4),
                                },
                                "impact": "medium" if cv < 1.0 else "high",
                                "confidence": 0.85,
                                "category": "variability",
                            })

            # Correlation-based insights
            correlations = stats.get("correlations", {})
            reported_pairs: set[tuple[str, str]] = set()
            for c1, corr_map in correlations.items():
                if not isinstance(corr_map, dict):
                    continue
                for c2, val in corr_map.items():
                    if c1 == c2:
                        continue
                    pair = tuple(sorted([c1, c2]))
                    if pair in reported_pairs:
                        continue
                    reported_pairs.add(pair)
                    if isinstance(val, (int, float)) and abs(val) >= 0.7:
                        direction = "positive" if val > 0 else "negative"
                        insights.append({
                            "title": f"Strong {direction} correlation: {c1} and {c2}",
                            "description": (
                                f"A strong {direction} correlation (r={val:.2f}) exists "
                                f"between '{c1}' and '{c2}'. Note that correlation does "
                                f"not imply causation -- further analysis is recommended."
                            ),
                            "evidence": {
                                "columns": [c1, c2],
                                "correlation": val,
                            },
                            "impact": "high" if abs(val) >= 0.85 else "medium",
                            "confidence": min(abs(val), 0.95),
                            "category": "correlation",
                        })

        # --- Insights from trends ---
        trends = results.get("trends", {})
        if isinstance(trends, dict) and "trend_direction" in trends:
            insights.append({
                "title": f"Overall trend is {trends['trend_direction']}",
                "description": (
                    f"The data shows a {trends['trend_direction']} trend. "
                    f"This should be considered when making forward-looking decisions."
                ),
                "evidence": trends,
                "impact": "high",
                "confidence": 0.75,
                "category": "trend",
            })

        # --- Insights from anomalies ---
        anomalies = results.get("anomalies", {})
        if isinstance(anomalies, dict) and anomalies.get("anomaly_count", 0) > 0:
            count = anomalies["anomaly_count"]
            insights.append({
                "title": f"{count} anomalous data point(s) detected",
                "description": (
                    f"{count} data points fall significantly outside expected ranges. "
                    f"These may represent errors, special events, or genuine outliers "
                    f"that require attention."
                ),
                "evidence": {
                    "anomaly_count": count,
                    "method": anomalies.get("method", "z-score"),
                },
                "impact": "high" if count > 5 else "medium",
                "confidence": 0.80,
                "category": "anomaly",
            })

        # --- Insights from benchmarks ---
        for metric, bench in benchmarks.items():
            if isinstance(bench, dict) and "benchmark_value" in bench:
                insights.append({
                    "title": f"Benchmark comparison: {metric}",
                    "description": (
                        f"Industry benchmark for '{metric}' is {bench['benchmark_value']}. "
                        f"Compare this with your actual metric to assess performance."
                    ),
                    "evidence": bench,
                    "impact": "medium",
                    "confidence": 0.70,
                    "category": "benchmark",
                })

        # --- Enrich insights with RAG context ---
        for ctx_item in rag_context[:3]:
            if isinstance(ctx_item, dict) and "content" in ctx_item:
                insights.append({
                    "title": f"Contextual insight from {ctx_item.get('source', 'knowledge base')}",
                    "description": ctx_item["content"],
                    "evidence": {"source": ctx_item.get("source", "knowledge_base")},
                    "impact": "low",
                    "confidence": ctx_item.get("relevance_score", 0.5),
                    "category": "contextual",
                })

        # Sort by impact (high > medium > low)
        impact_order = {"high": 0, "medium": 1, "low": 2}
        insights.sort(key=lambda i: impact_order.get(i.get("impact", "low"), 3))

        return insights

    # ------------------------------------------------------------------
    # Narrative generation
    # ------------------------------------------------------------------

    async def _generate_narrative(
        self,
        analytics_results: dict[str, Any],
        insights: list[dict[str, Any]],
        detail_level: str,
    ) -> dict[str, Any]:
        """Generate a structured narrative from insights.

        Calls the ``generate_narrative`` MCP tool for formatting.
        """
        findings: dict[str, Any] = {
            "insight_count": len(insights),
            "insights": insights[:10],  # Cap for narrative length
            "analytics_summary": analytics_results.get("summary", ""),
            "detail_level": detail_level,
        }

        result = await self.call_mcp_tool(
            "generate_narrative",
            {
                "findings": findings,
                "detail_level": detail_level,
                "include_recommendations": True,
            },
        )

        raw = result.get("data", result)
        if isinstance(raw, dict):
            return raw

        # Fallback: produce a simple narrative
        sections: list[str] = ["# Analysis Summary\n"]
        sections.append(analytics_results.get("summary", "Analysis complete."))
        sections.append("\n## Key Insights\n")
        for i, insight in enumerate(insights[:5], start=1):
            sections.append(f"{i}. **{insight.get('title', 'Insight')}** -- {insight.get('description', '')}")
        sections.append("\n---")

        return {
            "narrative_text": "\n".join(sections),
            "detail_level": detail_level,
            "section_count": 2,
        }

    # ------------------------------------------------------------------
    # Recommendation generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_recommendations(
        insights: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Derive prioritised recommendations from insights.

        In production this would be an LLM call.  The current
        implementation applies simple rules.
        """
        recommendations: list[dict[str, Any]] = []

        for idx, insight in enumerate(insights):
            category = insight.get("category", "general")
            impact = insight.get("impact", "low")
            title = insight.get("title", "")

            if category == "variability" and impact in ("high", "medium"):
                recommendations.append({
                    "title": f"Investigate drivers of variability in {insight.get('evidence', {}).get('column', 'metric')}",
                    "rationale": title,
                    "expected_impact": "Reduced risk and more predictable outcomes",
                    "effort": "medium",
                    "priority": 1 if impact == "high" else 2,
                })

            elif category == "correlation":
                recommendations.append({
                    "title": f"Explore causal relationship: {title}",
                    "rationale": "Strong statistical correlation warrants deeper investigation",
                    "expected_impact": "Better understanding of key drivers",
                    "effort": "medium",
                    "priority": 2,
                })

            elif category == "anomaly":
                recommendations.append({
                    "title": "Review anomalous data points",
                    "rationale": title,
                    "expected_impact": "Early detection of issues or opportunities",
                    "effort": "low",
                    "priority": 1,
                })

            elif category == "trend" and impact == "high":
                recommendations.append({
                    "title": "Align strategy with observed trend",
                    "rationale": title,
                    "expected_impact": "Proactive positioning based on data-driven trends",
                    "effort": "high",
                    "priority": 2,
                })

        # Deduplicate by title
        seen_titles: set[str] = set()
        unique: list[dict[str, Any]] = []
        for rec in recommendations:
            if rec["title"] not in seen_titles:
                seen_titles.add(rec["title"])
                unique.append(rec)

        unique.sort(key=lambda r: r.get("priority", 5))
        return unique

    # ------------------------------------------------------------------
    # Benchmark comparison
    # ------------------------------------------------------------------

    @staticmethod
    def _compare_benchmarks(
        analytics_results: dict[str, Any],
        benchmarks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Compare analytical findings against retrieved benchmarks."""
        comparisons: list[dict[str, Any]] = []

        for metric, bench in benchmarks.items():
            if not isinstance(bench, dict):
                continue
            bench_value = bench.get("benchmark_value")
            if bench_value is None:
                continue

            comparisons.append({
                "metric": metric,
                "benchmark_value": bench_value,
                "source": bench.get("source", "industry"),
                "assessment": "Benchmark data retrieved; compare with your actual metric.",
            })

        return comparisons

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_benchmark_metrics(
        analytics_results: dict[str, Any],
    ) -> list[str]:
        """Identify metric names suitable for benchmark lookup."""
        metrics: list[str] = []
        results = analytics_results.get("results", analytics_results)

        stats = results.get("statistics", {})
        if isinstance(stats, dict):
            descriptive = stats.get("descriptive", {})
            for col in descriptive:
                canonical = col.lower().replace(" ", "_")
                if any(kw in canonical for kw in (
                    "revenue", "cost", "margin", "churn", "growth",
                    "conversion", "retention", "acquisition", "ltv", "cac",
                    "satisfaction", "nps",
                )):
                    metrics.append(canonical)

        # Cap at 5 to avoid excessive benchmark calls
        return metrics[:5]

    @staticmethod
    def _extract_analytics_results(context: dict[str, Any]) -> dict[str, Any]:
        """Unwrap analytics results from the shared context."""
        # Direct results key
        if "results" in context and isinstance(context["results"], dict):
            return context

        # Wrapped in a step output
        for key in ("step-analytics", "analytics"):
            upstream = context.get(key, {})
            if isinstance(upstream, dict) and ("results" in upstream or "summary" in upstream):
                return upstream

        return context
