"""Trend analysis tool for the Compute Engine MCP server.

Performs time-series decomposition including moving averages,
period-over-period changes, trend direction, and basic seasonality
detection from tabular date/value data.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_VALID_PERIODS = {"daily", "weekly", "monthly", "quarterly", "yearly"}


async def analyze_trends(
    data: list[dict],
    date_column: str,
    value_column: str,
    period: str = "monthly",
) -> dict[str, Any]:
    """Analyse trends in a time-series defined by a date and value column.

    Parameters
    ----------
    data:
        List of row-dicts containing at least *date_column* and
        *value_column*.
    date_column:
        Name of the column holding date/datetime strings.
    value_column:
        Name of the numeric value column.
    period:
        Aggregation period -- ``"daily"``, ``"weekly"``, ``"monthly"``,
        ``"quarterly"``, or ``"yearly"``.

    Returns
    -------
    dict
        ``{"trend_direction": str, "moving_averages": {...},
        "period_changes": [...], "seasonality": {...}, "summary": str}``
    """
    if not data:
        return _empty_result("No data provided.")

    if period not in _VALID_PERIODS:
        return _empty_result(
            f"Unknown period '{period}'. Supported: {sorted(_VALID_PERIODS)}."
        )

    try:
        df = pd.DataFrame(data)
    except Exception as exc:
        return _empty_result(f"Failed to create DataFrame: {exc}")

    for col, label in [(date_column, "date_column"), (value_column, "value_column")]:
        if col not in df.columns:
            return _empty_result(
                f"{label} '{col}' not found. Available: {df.columns.tolist()}."
            )

    # Parse dates and coerce values
    try:
        df[date_column] = pd.to_datetime(df[date_column], utc=True)
    except Exception:
        try:
            df[date_column] = pd.to_datetime(df[date_column])
        except Exception as exc:
            return _empty_result(f"Cannot parse dates in '{date_column}': {exc}")

    df[value_column] = pd.to_numeric(df[value_column], errors="coerce")
    df = df.dropna(subset=[date_column, value_column]).sort_values(date_column)

    if df.empty:
        return _empty_result(
            "No valid rows remain after dropping NaN dates/values."
        )

    # Set date as index for resampling
    ts = df.set_index(date_column)[value_column]

    # --- Moving averages (computed on the raw daily-level or original data) ---
    ma_7 = ts.rolling(window=7, min_periods=1).mean()
    ma_30 = ts.rolling(window=30, min_periods=1).mean()

    moving_averages: dict[str, Any] = {
        "ma_7": [
            {"date": str(d.date()) if hasattr(d, "date") else str(d), "value": round(float(v), 4)}
            for d, v in ma_7.tail(30).items()
        ],
        "ma_30": [
            {"date": str(d.date()) if hasattr(d, "date") else str(d), "value": round(float(v), 4)}
            for d, v in ma_30.tail(30).items()
        ],
    }

    # --- Period aggregation ---
    freq_map = {
        "daily": "D",
        "weekly": "W",
        "monthly": "MS",
        "quarterly": "QS",
        "yearly": "YS",
    }
    resampled = ts.resample(freq_map[period]).mean().dropna()

    # --- Period-over-period changes ---
    period_changes: list[dict[str, Any]] = []
    if len(resampled) >= 2:
        pct_change = resampled.pct_change().dropna()
        for dt, change in pct_change.items():
            period_changes.append({
                "date": str(dt.date()) if hasattr(dt, "date") else str(dt),
                "change_pct": round(float(change) * 100, 2),
            })

    # --- Trend direction ---
    trend_direction = _compute_trend_direction(resampled)

    # --- Seasonality detection (month-based grouping) ---
    seasonality = _compute_seasonality(df, date_column, value_column)

    # --- Summary ---
    summary_parts: list[str] = [
        f"Analysed {len(ts)} data points over {period} periods.",
        f"Trend direction: {trend_direction}.",
    ]
    if period_changes:
        avg_change = np.mean([pc["change_pct"] for pc in period_changes])
        summary_parts.append(
            f"Average period-over-period change: {avg_change:+.2f}%."
        )
    if seasonality.get("peak_month"):
        summary_parts.append(
            f"Seasonal peak: month {seasonality['peak_month']}; "
            f"trough: month {seasonality.get('trough_month', 'N/A')}."
        )

    return {
        "trend_direction": trend_direction,
        "moving_averages": moving_averages,
        "period_changes": period_changes,
        "seasonality": seasonality,
        "summary": " ".join(summary_parts),
        "error": None,
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _empty_result(error: str) -> dict[str, Any]:
    """Return a standardised empty result with an error message."""
    return {
        "trend_direction": "unknown",
        "moving_averages": {},
        "period_changes": [],
        "seasonality": {},
        "summary": "",
        "error": error,
    }


def _compute_trend_direction(resampled: pd.Series) -> str:
    """Determine overall trend by fitting a linear slope to the resampled data."""
    if len(resampled) < 2:
        return "insufficient_data"

    y = resampled.values.astype(float)
    x = np.arange(len(y), dtype=float)

    try:
        slope, _ = np.polyfit(x, y, deg=1)
    except Exception:
        return "unknown"

    # Normalise slope by the mean of y to make the threshold scale-independent
    mean_y = np.mean(np.abs(y))
    if mean_y == 0:
        return "flat"

    relative_slope = slope / mean_y

    if relative_slope > 0.01:
        return "up"
    elif relative_slope < -0.01:
        return "down"
    return "flat"


def _compute_seasonality(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
) -> dict[str, Any]:
    """Detect basic seasonality via month-based grouping."""
    try:
        months = df[date_column].dt.month
        monthly_avg = df.groupby(months)[value_column].mean()

        if monthly_avg.empty:
            return {}

        peak_month = int(monthly_avg.idxmax())
        trough_month = int(monthly_avg.idxmin())

        # Seasonality strength: coefficient of variation across monthly means
        cv = float(monthly_avg.std() / monthly_avg.mean()) if monthly_avg.mean() != 0 else 0.0

        return {
            "monthly_averages": {int(m): round(float(v), 4) for m, v in monthly_avg.items()},
            "peak_month": peak_month,
            "trough_month": trough_month,
            "seasonality_strength": round(cv, 4),
        }
    except Exception as exc:
        logger.warning("Seasonality computation failed: %s", exc)
        return {}
