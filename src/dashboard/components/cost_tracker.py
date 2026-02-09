"""Reusable cost tracking component."""

import streamlit as st


def render_cost_summary(cost_data: dict) -> None:
    """Render cost summary metrics in a 4-column layout.

    Expected keys in cost_data:
        - total (float): Total cost in dollars.
        - budget_pct (float): Percentage of budget consumed (0-100).
        - tokens (int): Total tokens used.
        - cache_savings (float): Dollar savings from caching.
    """
    cols = st.columns(4)
    cols[0].metric("Total Cost", f"${cost_data.get('total', 0):.3f}")
    cols[1].metric("Budget Used", f"{cost_data.get('budget_pct', 0):.0f}%")
    cols[2].metric("Tokens Used", f"{cost_data.get('tokens', 0):,}")
    cols[3].metric("Cache Savings", f"${cost_data.get('cache_savings', 0):.3f}")
