"""Reusable quality scoreboard component."""

import streamlit as st


def render_quality_score(score: float, checks: list[dict] | None = None) -> None:
    """Render quality score with optional breakdown.

    Args:
        score: Overall quality score between 0.0 and 1.0.
        checks: Optional list of check dicts, each containing:
            - name (str): Check name.
            - passed (bool): Whether the check passed.
            - score (float): Individual check score.
            - details (str): Human-readable details.
    """
    if score >= 0.85:
        color = "green"
    elif score >= 0.60:
        color = "orange"
    else:
        color = "red"

    st.markdown(f"### Quality Score: :{color}[{score:.2f}]")

    if checks:
        for check in checks:
            icon = "\u2705" if check.get("passed") else "\u274c"
            name = check.get("name", "Unknown")
            check_score = check.get("score", 0)
            details = check.get("details", "")
            st.markdown(f"{icon} **{name}**: {check_score:.2f} -- {details}")
