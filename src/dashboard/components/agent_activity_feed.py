"""Reusable agent activity feed component."""

import streamlit as st


def render_activity_feed(activities: list[dict], max_items: int = 20) -> None:
    """Render a scrollable activity feed.

    Each activity dict should contain:
        - time (str): Timestamp or time string.
        - agent (str): Name of the agent.
        - action (str): Description of the action.
        - icon (str, optional): Emoji icon (defaults to a blue circle).
    """
    if not activities:
        st.caption("No activity yet.")
        return

    for activity in activities[:max_items]:
        time_str = activity.get("time", "")
        agent = activity.get("agent", "Unknown")
        action = activity.get("action", "")
        icon = activity.get("icon", "\U0001f535")
        st.markdown(f"`{time_str}` {icon} **{agent}** -- {action}")
