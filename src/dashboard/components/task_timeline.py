"""Reusable task timeline (Gantt) component."""

import plotly.graph_objects as go

STATUS_COLORS = {
    "completed": "#2ecc71",
    "in_progress": "#3498db",
    "failed": "#e74c3c",
    "pending": "#95a5a6",
    "reprocessing": "#f39c12",
}


def render_gantt(steps: list[dict]) -> go.Figure:
    """Render a horizontal bar chart representing task step timeline.

    Each step dict should contain:
        - agent (str): Name of the agent handling the step.
        - duration (float): Duration in seconds.
        - cost (float): Cost in dollars.
        - status (str): One of completed, in_progress, failed, pending, reprocessing.
    """
    fig = go.Figure()

    for step in steps:
        duration = step.get("duration", 0)
        cost = step.get("cost", 0)
        status = step.get("status", "pending")
        agent = step.get("agent", "Unknown")

        fig.add_trace(
            go.Bar(
                x=[duration],
                y=[agent],
                orientation="h",
                marker_color=STATUS_COLORS.get(status, "#95a5a6"),
                text=f"{duration}s | ${cost:.3f}",
                textposition="inside",
                name=agent,
                showlegend=False,
            )
        )

    fig.update_layout(
        barmode="stack",
        height=max(200, len(steps) * 50),
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis_title="Duration (seconds)",
    )
    return fig
