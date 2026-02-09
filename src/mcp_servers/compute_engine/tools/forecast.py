"""Forecasting tool for the Compute Engine MCP server.

Implements a simple trend + seasonal decomposition forecast using
numpy polyfit for the linear trend and monthly seasonal averages.
No external forecasting libraries (e.g. Prophet) are required.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


async def forecast(
    data: list[dict],
    date_column: str,
    value_column: str,
    periods: int = 12,
) -> dict[str, Any]:
    """Produce a simple forecast combining a linear trend with seasonal factors.

    Parameters
    ----------
    data:
        List of row-dicts containing at least *date_column* and
        *value_column*.
    date_column:
        Name of the column holding date/datetime strings.
    value_column:
        Name of the numeric value column.
    periods:
        Number of future periods (months) to forecast.

    Returns
    -------
    dict
        ``{"forecast": [{"date": str, "value": float, "lower": float,
        "upper": float}], "trend": str, "confidence": float}``
    """
    if not data:
        return _empty_result("No data provided.")

    if periods <= 0:
        return _empty_result("periods must be a positive integer.")

    try:
        df = pd.DataFrame(data)
    except Exception as exc:
        return _empty_result(f"Failed to create DataFrame: {exc}")

    for col, label in [(date_column, "date_column"), (value_column, "value_column")]:
        if col not in df.columns:
            return _empty_result(
                f"{label} '{col}' not found. Available: {df.columns.tolist()}."
            )

    # Parse dates
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
        return _empty_result("No valid rows remain after dropping NaN dates/values.")

    if len(df) < 3:
        return _empty_result(
            "Need at least 3 data points to produce a meaningful forecast."
        )

    try:
        result = _build_forecast(df, date_column, value_column, periods)
    except Exception as exc:
        logger.exception("Forecast computation failed")
        return _empty_result(f"Forecast computation failed: {exc}")

    return result


# ------------------------------------------------------------------
# Core forecast implementation
# ------------------------------------------------------------------


def _build_forecast(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
    periods: int,
) -> dict[str, Any]:
    """Build a linear-trend + seasonal-average forecast."""
    # Aggregate to monthly means for decomposition
    ts = df.set_index(date_column)[value_column]
    monthly = ts.resample("MS").mean().dropna()

    if monthly.empty:
        return _empty_result("Could not resample data to monthly frequency.")

    y = monthly.values.astype(float)
    n = len(y)
    x = np.arange(n, dtype=float)

    # --- Fit linear trend ---
    coeffs = np.polyfit(x, y, deg=1)
    slope, intercept = float(coeffs[0]), float(coeffs[1])
    trend_line = np.polyval(coeffs, x)

    # Residuals after removing trend
    residuals = y - trend_line

    # --- Seasonal component (monthly averages of residuals) ---
    months = monthly.index.month
    seasonal_avg: dict[int, float] = {}
    for m in range(1, 13):
        mask = months == m
        vals = residuals[mask]
        seasonal_avg[m] = float(vals.mean()) if len(vals) > 0 else 0.0

    # --- Confidence estimation ---
    # Use the residuals' standard deviation (after removing trend + season)
    deseasonalised_residuals = np.array([
        residuals[i] - seasonal_avg.get(int(months[i]), 0.0)
        for i in range(n)
    ])
    residual_std = float(np.std(deseasonalised_residuals)) if n > 1 else 0.0

    # R-squared of the trend model
    ss_res = np.sum(deseasonalised_residuals ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))

    # --- Generate future dates ---
    last_date = monthly.index[-1]
    future_dates = pd.date_range(
        start=last_date + pd.DateOffset(months=1),
        periods=periods,
        freq="MS",
    )

    # --- Produce forecast values ---
    forecast_points: list[dict[str, Any]] = []
    for i, fdate in enumerate(future_dates):
        future_x = n + i
        trend_value = slope * future_x + intercept
        seasonal_value = seasonal_avg.get(fdate.month, 0.0)
        predicted = trend_value + seasonal_value

        # Widen confidence interval as we project further into the future
        spread = residual_std * 1.96 * np.sqrt(1 + (i + 1) / n)

        forecast_points.append({
            "date": str(fdate.date()),
            "value": round(predicted, 4),
            "lower": round(predicted - spread, 4),
            "upper": round(predicted + spread, 4),
        })

    # Trend direction
    if slope > 0 and abs(slope / (np.mean(np.abs(y)) or 1.0)) > 0.001:
        trend = "up"
    elif slope < 0 and abs(slope / (np.mean(np.abs(y)) or 1.0)) > 0.001:
        trend = "down"
    else:
        trend = "flat"

    return {
        "forecast": forecast_points,
        "trend": trend,
        "confidence": round(r_squared, 4),
        "model_details": {
            "slope": round(slope, 6),
            "intercept": round(intercept, 4),
            "residual_std": round(residual_std, 4),
            "historical_months": n,
        },
        "error": None,
    }


def _empty_result(error: str) -> dict[str, Any]:
    return {
        "forecast": [],
        "trend": "unknown",
        "confidence": 0.0,
        "model_details": {},
        "error": error,
    }
