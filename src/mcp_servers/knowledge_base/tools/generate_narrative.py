"""Narrative generation tool.

Takes structured analytical findings and formats them into a
business-ready narrative document with sections, key points, and
optional recommendations.  This is a template-based formatter --
the wrapping agent is responsible for any LLM-based elaboration.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_value(value: Any) -> str:
    """Produce a human-friendly string for a metric value."""
    if isinstance(value, float):
        if abs(value) < 1:
            return f"{value:.2%}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _extract_key_points(findings: dict[str, Any]) -> list[str]:
    """Derive key points from the findings dictionary."""
    key_points: list[str] = []

    # If findings contain explicit key_points, pass them through
    if "key_points" in findings:
        return [str(kp) for kp in findings["key_points"]]

    # Otherwise synthesise from metrics / trends
    metrics: dict[str, Any] = findings.get("metrics", {})
    for name, value in metrics.items():
        label = name.replace("_", " ").title()
        key_points.append(f"{label}: {_format_value(value)}")

    trends: list[dict[str, Any]] = findings.get("trends", [])
    for trend in trends:
        direction = trend.get("direction", "stable")
        metric_name = trend.get("metric", "metric").replace("_", " ").title()
        change = trend.get("change")
        if change is not None:
            key_points.append(
                f"{metric_name} is trending {direction} ({_format_value(change)} change)"
            )
        else:
            key_points.append(f"{metric_name} is trending {direction}")

    if not key_points:
        key_points.append("No specific key points could be extracted from the findings.")

    return key_points


def _build_recommendations(findings: dict[str, Any]) -> list[str]:
    """Generate actionable recommendations from findings."""
    recommendations: list[str] = []

    # Pass through explicit recommendations
    if "recommendations" in findings:
        return [str(r) for r in findings["recommendations"]]

    # Derive from trends and thresholds
    trends: list[dict[str, Any]] = findings.get("trends", [])
    for trend in trends:
        direction = trend.get("direction", "stable")
        metric_name = trend.get("metric", "metric").replace("_", " ").title()
        if direction == "declining":
            recommendations.append(
                f"Investigate drivers behind declining {metric_name} and develop "
                f"a remediation plan."
            )
        elif direction == "improving":
            recommendations.append(
                f"Continue current strategy for {metric_name}; identify factors "
                f"driving improvement to replicate elsewhere."
            )

    alerts: list[str] = findings.get("alerts", [])
    for alert in alerts:
        recommendations.append(f"Address alert: {alert}")

    if not recommendations:
        recommendations.append(
            "Conduct a deeper review of the underlying data to identify "
            "actionable optimisation opportunities."
        )

    return recommendations


def _build_sections_executive(
    findings: dict[str, Any],
    key_points: list[str],
) -> list[dict[str, str]]:
    """Build narrative sections at executive (brief) level."""
    summary = findings.get("summary", "")
    if not summary:
        summary = ". ".join(key_points[:3]) + "."

    sections: list[dict[str, str]] = [
        {
            "heading": "Executive Summary",
            "content": summary,
        },
        {
            "heading": "Key Highlights",
            "content": "\n".join(f"- {kp}" for kp in key_points),
        },
    ]
    return sections


def _build_sections_detailed(
    findings: dict[str, Any],
    key_points: list[str],
) -> list[dict[str, str]]:
    """Build narrative sections at detailed (comprehensive) level."""
    sections = _build_sections_executive(findings, key_points)

    # Metrics breakdown
    metrics: dict[str, Any] = findings.get("metrics", {})
    if metrics:
        rows = "\n".join(
            f"- **{name.replace('_', ' ').title()}**: {_format_value(val)}"
            for name, val in metrics.items()
        )
        sections.append({"heading": "Metrics Breakdown", "content": rows})

    # Trends analysis
    trends: list[dict[str, Any]] = findings.get("trends", [])
    if trends:
        trend_lines: list[str] = []
        for trend in trends:
            metric = trend.get("metric", "Unknown").replace("_", " ").title()
            direction = trend.get("direction", "stable")
            change = trend.get("change")
            line = f"- **{metric}**: trending {direction}"
            if change is not None:
                line += f" ({_format_value(change)} change)"
            trend_lines.append(line)
        sections.append({"heading": "Trend Analysis", "content": "\n".join(trend_lines)})

    # Context / notes
    context: str = findings.get("context", "")
    if context:
        sections.append({"heading": "Additional Context", "content": context})

    return sections


def _build_sections_technical(
    findings: dict[str, Any],
    key_points: list[str],
) -> list[dict[str, str]]:
    """Build narrative sections at technical (full stats) level."""
    sections = _build_sections_detailed(findings, key_points)

    # Raw data summary
    raw_data = findings.get("raw_data_summary", findings.get("data_summary"))
    if raw_data:
        if isinstance(raw_data, dict):
            rows = "\n".join(f"- {k}: {v}" for k, v in raw_data.items())
        else:
            rows = str(raw_data)
        sections.append({"heading": "Data Summary", "content": rows})

    # Methodology notes
    methodology: str = findings.get("methodology", "")
    if methodology:
        sections.append({"heading": "Methodology", "content": methodology})

    # Statistical notes
    stats: dict[str, Any] = findings.get("statistics", {})
    if stats:
        stat_lines = "\n".join(
            f"- {k.replace('_', ' ').title()}: {_format_value(v)}" for k, v in stats.items()
        )
        sections.append({"heading": "Statistical Details", "content": stat_lines})

    # Confidence / caveats
    caveats: list[str] = findings.get("caveats", [])
    if caveats:
        sections.append({
            "heading": "Caveats & Limitations",
            "content": "\n".join(f"- {c}" for c in caveats),
        })

    return sections


# ---------------------------------------------------------------------------
# Public tool handler
# ---------------------------------------------------------------------------

_SECTION_BUILDERS = {
    "executive": _build_sections_executive,
    "detailed": _build_sections_detailed,
    "technical": _build_sections_technical,
}


async def generate_narrative(arguments: dict) -> dict:
    """Generate a formatted business narrative from structured findings.

    Parameters (via *arguments* dict)
    ----------------------------------
    findings : dict
        Structured findings.  Recognised keys include ``summary``,
        ``metrics``, ``trends``, ``key_points``, ``recommendations``,
        ``alerts``, ``context``, ``raw_data_summary``, ``methodology``,
        ``statistics``, and ``caveats``.
    detail_level : str
        One of ``"executive"`` (brief), ``"detailed"`` (comprehensive),
        or ``"technical"`` (full stats).  Defaults to ``"executive"``.
    include_recommendations : bool
        Whether to append a recommendations section.  Defaults to
        ``True``.

    Returns
    -------
    dict
        ``{"narrative": str, "sections": [...], "key_points": [...],
        "recommendations": [...]}``
    """
    findings: dict[str, Any] = arguments["findings"]
    detail_level: str = arguments.get("detail_level", "executive")
    include_recommendations: bool = arguments.get("include_recommendations", True)

    if detail_level not in _SECTION_BUILDERS:
        detail_level = "executive"

    key_points = _extract_key_points(findings)
    sections = _SECTION_BUILDERS[detail_level](findings, key_points)

    recommendations: list[str] = []
    if include_recommendations:
        recommendations = _build_recommendations(findings)
        sections.append({
            "heading": "Recommendations",
            "content": "\n".join(f"{i + 1}. {r}" for i, r in enumerate(recommendations)),
        })

    # Compile full narrative text
    narrative_parts: list[str] = []
    for section in sections:
        narrative_parts.append(f"## {section['heading']}\n\n{section['content']}")
    narrative = "\n\n".join(narrative_parts)

    return {
        "narrative": narrative,
        "sections": sections,
        "key_points": key_points,
        "recommendations": recommendations,
    }
