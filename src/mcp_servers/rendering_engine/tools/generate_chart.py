"""Chart generation tool using Plotly.

Accepts tabular data (list of row dicts) and produces a serialised
Plotly figure as a JSON string.  Supports bar, line, scatter, heatmap,
pie, and histogram chart types.
"""

from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Chart builder dispatch
# ---------------------------------------------------------------------------

_VALID_CHART_TYPES = {"bar", "line", "scatter", "heatmap", "pie", "histogram"}


def _extract_columns(
    data: list[dict[str, Any]],
    x_col: str,
    y_col: str,
    color_col: str | None = None,
) -> tuple[list[Any], list[Any], list[Any] | None]:
    """Pull column vectors out of row-oriented data."""
    x_vals = [row.get(x_col) for row in data]
    y_vals = [row.get(y_col) for row in data]
    color_vals = [row.get(color_col) for row in data] if color_col else None
    return x_vals, y_vals, color_vals


def _build_bar(
    x: list[Any],
    y: list[Any],
    color: list[Any] | None,
    title: str,
) -> go.Figure:
    fig = go.Figure()
    if color is not None:
        groups: dict[str, tuple[list[Any], list[Any]]] = {}
        for xi, yi, ci in zip(x, y, color):
            groups.setdefault(str(ci), ([], []))
            groups[str(ci)][0].append(xi)
            groups[str(ci)][1].append(yi)
        for group_name, (gx, gy) in groups.items():
            fig.add_trace(go.Bar(x=gx, y=gy, name=group_name))
    else:
        fig.add_trace(go.Bar(x=x, y=y))
    fig.update_layout(title=title, barmode="group")
    return fig


def _build_line(
    x: list[Any],
    y: list[Any],
    color: list[Any] | None,
    title: str,
) -> go.Figure:
    fig = go.Figure()
    if color is not None:
        groups: dict[str, tuple[list[Any], list[Any]]] = {}
        for xi, yi, ci in zip(x, y, color):
            groups.setdefault(str(ci), ([], []))
            groups[str(ci)][0].append(xi)
            groups[str(ci)][1].append(yi)
        for group_name, (gx, gy) in groups.items():
            fig.add_trace(go.Scatter(x=gx, y=gy, mode="lines+markers", name=group_name))
    else:
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers"))
    fig.update_layout(title=title)
    return fig


def _build_scatter(
    x: list[Any],
    y: list[Any],
    color: list[Any] | None,
    title: str,
) -> go.Figure:
    fig = go.Figure()
    if color is not None:
        groups: dict[str, tuple[list[Any], list[Any]]] = {}
        for xi, yi, ci in zip(x, y, color):
            groups.setdefault(str(ci), ([], []))
            groups[str(ci)][0].append(xi)
            groups[str(ci)][1].append(yi)
        for group_name, (gx, gy) in groups.items():
            fig.add_trace(go.Scatter(x=gx, y=gy, mode="markers", name=group_name))
    else:
        fig.add_trace(go.Scatter(x=x, y=y, mode="markers"))
    fig.update_layout(title=title)
    return fig


def _build_heatmap(
    x: list[Any],
    y: list[Any],
    _color: list[Any] | None,
    title: str,
) -> go.Figure:
    """Build a heatmap.  Expects y-values to be numeric intensities."""
    # Construct a simple matrix: unique x as columns, rows inferred from order
    unique_x = sorted(set(x), key=lambda v: str(v))
    x_index = {v: i for i, v in enumerate(unique_x)}

    # Group y values by x position
    z_map: dict[int, list[float]] = {}
    row_idx = 0
    prev_xi: int | None = None
    for xi_val, yi_val in zip(x, y):
        col = x_index[xi_val]
        if prev_xi is not None and col <= prev_xi:
            row_idx += 1
        prev_xi = col
        z_map.setdefault(row_idx, [0.0] * len(unique_x))
        try:
            z_map[row_idx][col] = float(yi_val)
        except (TypeError, ValueError):
            z_map[row_idx][col] = 0.0

    z = [z_map[r] for r in sorted(z_map.keys())]
    fig = go.Figure(data=go.Heatmap(z=z, x=[str(v) for v in unique_x], colorscale="Viridis"))
    fig.update_layout(title=title)
    return fig


def _build_pie(
    x: list[Any],
    y: list[Any],
    _color: list[Any] | None,
    title: str,
) -> go.Figure:
    """Build a pie chart with x as labels and y as values."""
    fig = go.Figure(data=go.Pie(labels=[str(v) for v in x], values=y))
    fig.update_layout(title=title)
    return fig


def _build_histogram(
    _x: list[Any],
    y: list[Any],
    _color: list[Any] | None,
    title: str,
) -> go.Figure:
    """Build a histogram from the y-column values."""
    fig = go.Figure(data=go.Histogram(x=y))
    fig.update_layout(title=title, xaxis_title="Value", yaxis_title="Count")
    return fig


_BUILDERS = {
    "bar": _build_bar,
    "line": _build_line,
    "scatter": _build_scatter,
    "heatmap": _build_heatmap,
    "pie": _build_pie,
    "histogram": _build_histogram,
}

# ---------------------------------------------------------------------------
# Public tool handler
# ---------------------------------------------------------------------------


async def generate_chart(arguments: dict) -> dict:
    """Generate a Plotly chart from tabular data.

    Parameters (via *arguments* dict)
    ----------------------------------
    data : list[dict]
        Row-oriented tabular data.
    chart_type : str
        One of ``"bar"``, ``"line"``, ``"scatter"``, ``"heatmap"``,
        ``"pie"``, ``"histogram"``.
    x_column : str
        Column name for the x-axis (or labels for pie).
    y_column : str
        Column name for the y-axis (or values for pie).
    title : str
        Chart title (default ``""``).
    color_column : str | None
        Optional grouping column for colour-coding traces.

    Returns
    -------
    dict
        ``{"chart_json": str, "chart_type": str, "title": str}``
    """
    data: list[dict[str, Any]] = arguments["data"]
    chart_type: str = arguments["chart_type"]
    x_column: str = arguments["x_column"]
    y_column: str = arguments["y_column"]
    title: str = arguments.get("title", "")
    color_column: str | None = arguments.get("color_column")

    if chart_type not in _VALID_CHART_TYPES:
        raise ValueError(
            f"Unsupported chart_type '{chart_type}'. "
            f"Must be one of {sorted(_VALID_CHART_TYPES)}."
        )

    if not data:
        raise ValueError("Data must contain at least one row.")

    x_vals, y_vals, color_vals = _extract_columns(data, x_column, y_column, color_column)

    builder = _BUILDERS[chart_type]
    fig = builder(x_vals, y_vals, color_vals, title)

    # Apply consistent styling
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=60, r=30, t=60, b=60),
        font=dict(family="Inter, Arial, sans-serif", size=12),
    )

    chart_json = json.loads(fig.to_json())

    return {
        "chart_json": json.dumps(chart_json),
        "chart_type": chart_type,
        "title": title,
    }
