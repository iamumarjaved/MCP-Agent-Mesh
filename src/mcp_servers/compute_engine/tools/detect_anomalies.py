"""Anomaly detection tool for the Compute Engine MCP server.

Supports Z-score, IQR, and Isolation Forest methods for identifying
outliers in a numeric column.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_VALID_METHODS = {"zscore", "iqr", "isolation_forest"}


async def detect_anomalies(
    data: list[dict],
    column: str,
    method: str = "zscore",
    threshold: float = 3.0,
) -> dict[str, Any]:
    """Detect anomalies in a single numeric column.

    Parameters
    ----------
    data:
        List of row-dicts.
    column:
        Name of the numeric column to analyse.
    method:
        Detection algorithm -- ``"zscore"``, ``"iqr"``, or
        ``"isolation_forest"``.
    threshold:
        Sensitivity parameter.  For *zscore* this is the number of
        standard deviations; for *iqr* it is the IQR multiplier
        (commonly 1.5).  Ignored for *isolation_forest*.

    Returns
    -------
    dict
        ``{"anomalies": [...], "anomaly_count": int, "total_count": int,
        "anomaly_rate": float, "method": str}``
    """
    if not data:
        return {
            "anomalies": [],
            "anomaly_count": 0,
            "total_count": 0,
            "anomaly_rate": 0.0,
            "method": method,
            "error": "No data provided.",
        }

    if method not in _VALID_METHODS:
        return {
            "anomalies": [],
            "anomaly_count": 0,
            "total_count": 0,
            "anomaly_rate": 0.0,
            "method": method,
            "error": f"Unknown method '{method}'. Supported: {sorted(_VALID_METHODS)}.",
        }

    try:
        df = pd.DataFrame(data)
    except Exception as exc:
        return {
            "anomalies": [],
            "anomaly_count": 0,
            "total_count": 0,
            "anomaly_rate": 0.0,
            "method": method,
            "error": f"Failed to create DataFrame: {exc}",
        }

    if column not in df.columns:
        return {
            "anomalies": [],
            "anomaly_count": 0,
            "total_count": len(df),
            "anomaly_rate": 0.0,
            "method": method,
            "error": f"Column '{column}' not found. Available: {df.columns.tolist()}.",
        }

    series = pd.to_numeric(df[column], errors="coerce")
    valid_mask = series.notna()
    valid_series = series[valid_mask]

    if valid_series.empty:
        return {
            "anomalies": [],
            "anomaly_count": 0,
            "total_count": len(df),
            "anomaly_rate": 0.0,
            "method": method,
            "error": f"Column '{column}' has no valid numeric values.",
        }

    try:
        if method == "zscore":
            anomaly_flags, scores = _detect_zscore(valid_series, threshold)
        elif method == "iqr":
            anomaly_flags, scores = _detect_iqr(valid_series, threshold)
        else:
            anomaly_flags, scores = _detect_isolation_forest(valid_series)
    except Exception as exc:
        logger.exception("Anomaly detection failed (method=%s)", method)
        return {
            "anomalies": [],
            "anomaly_count": 0,
            "total_count": len(df),
            "anomaly_rate": 0.0,
            "method": method,
            "error": f"Detection failed: {exc}",
        }

    anomalies: list[dict[str, Any]] = []
    for idx, is_anomaly in anomaly_flags.items():
        if is_anomaly:
            anomalies.append({
                "index": int(idx),
                "value": float(valid_series.loc[idx]),
                "score": round(float(scores.loc[idx]), 4),
            })

    total_count = len(df)
    anomaly_count = len(anomalies)

    return {
        "anomalies": anomalies,
        "anomaly_count": anomaly_count,
        "total_count": total_count,
        "anomaly_rate": round(anomaly_count / total_count, 4) if total_count > 0 else 0.0,
        "method": method,
        "error": None,
    }


# ------------------------------------------------------------------
# Private detection implementations
# ------------------------------------------------------------------


def _detect_zscore(
    series: pd.Series,
    threshold: float,
) -> tuple[pd.Series, pd.Series]:
    """Flag values whose absolute Z-score exceeds *threshold*."""
    mean = series.mean()
    std = series.std()
    if std == 0 or np.isnan(std):
        scores = pd.Series(0.0, index=series.index)
        flags = pd.Series(False, index=series.index)
        return flags, scores

    scores = ((series - mean) / std).abs()
    flags = scores > threshold
    return flags, scores


def _detect_iqr(
    series: pd.Series,
    multiplier: float,
) -> tuple[pd.Series, pd.Series]:
    """Flag values outside ``[Q1 - k*IQR, Q3 + k*IQR]``."""
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        # All values in the interquartile range are the same; fall back
        # to a simple deviation from median.
        scores = (series - series.median()).abs()
        flags = pd.Series(False, index=series.index)
        return flags, scores

    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    flags = (series < lower) | (series > upper)
    # Score: how many IQRs the value is from the nearest fence
    scores = pd.Series(0.0, index=series.index)
    below = series < lower
    above = series > upper
    scores[below] = ((lower - series[below]) / iqr).abs()
    scores[above] = ((series[above] - upper) / iqr).abs()

    return flags, scores


def _detect_isolation_forest(
    series: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Use ``sklearn.ensemble.IsolationForest`` to flag anomalies."""
    from sklearn.ensemble import IsolationForest

    values = series.values.reshape(-1, 1)
    model = IsolationForest(contamination="auto", random_state=42)
    predictions = model.fit_predict(values)
    raw_scores = model.decision_function(values)

    # IsolationForest: -1 = anomaly, 1 = normal
    flags = pd.Series(predictions == -1, index=series.index)
    # Invert the decision function so higher = more anomalous
    scores = pd.Series(-raw_scores, index=series.index)

    return flags, scores
