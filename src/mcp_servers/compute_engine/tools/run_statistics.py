"""Descriptive statistics tool for the Compute Engine MCP server.

Computes comprehensive summary statistics for numeric and categorical
columns, including correlation matrices and distribution measures.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


async def run_statistics(
    data: list[dict],
    columns: list[str] | None = None,
) -> dict[str, Any]:
    """Compute descriptive statistics for the supplied tabular data.

    Parameters
    ----------
    data:
        List of row-dicts (e.g. ``[{"a": 1, "b": "x"}, ...]``).
    columns:
        Optional subset of columns to analyse.  When ``None`` all columns
        are included.

    Returns
    -------
    dict
        ``{"descriptive": {...}, "correlations": {...}, "summary": str}``
    """
    if not data:
        return {
            "descriptive": {},
            "correlations": {},
            "summary": "No data provided.",
            "error": None,
        }

    try:
        df = pd.DataFrame(data)
    except Exception as exc:
        return {
            "descriptive": {},
            "correlations": {},
            "summary": "",
            "error": f"Failed to create DataFrame: {exc}",
        }

    # Restrict to requested columns if supplied
    if columns is not None:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            return {
                "descriptive": {},
                "correlations": {},
                "summary": "",
                "error": f"Columns not found in data: {missing}",
            }
        df = df[columns]

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

    descriptive: dict[str, Any] = {}

    # --- Numeric columns ---
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            descriptive[col] = {
                "type": "numeric",
                "count": 0,
                "mean": None,
                "median": None,
                "std": None,
                "min": None,
                "max": None,
                "q25": None,
                "q50": None,
                "q75": None,
                "skewness": None,
                "kurtosis": None,
                "missing": int(df[col].isna().sum()),
            }
            continue

        descriptive[col] = {
            "type": "numeric",
            "count": int(series.count()),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "std": float(series.std()) if len(series) > 1 else 0.0,
            "min": float(series.min()),
            "max": float(series.max()),
            "q25": float(series.quantile(0.25)),
            "q50": float(series.quantile(0.50)),
            "q75": float(series.quantile(0.75)),
            "skewness": float(series.skew()) if len(series) > 2 else None,
            "kurtosis": float(series.kurtosis()) if len(series) > 3 else None,
            "missing": int(df[col].isna().sum()),
        }

    # --- Categorical columns ---
    for col in categorical_cols:
        series = df[col].dropna()
        value_counts = series.value_counts()
        mode_values = series.mode().tolist()

        descriptive[col] = {
            "type": "categorical",
            "count": int(series.count()),
            "unique": int(series.nunique()),
            "mode": mode_values[0] if mode_values else None,
            "value_counts": {str(k): int(v) for k, v in value_counts.head(20).items()},
            "missing": int(df[col].isna().sum()),
        }

    # --- Correlation matrix (numeric only) ---
    correlations: dict[str, Any] = {}
    if len(numeric_cols) >= 2:
        corr_df = df[numeric_cols].corr()
        correlations = {
            col: {
                other_col: round(float(corr_df.loc[col, other_col]), 4)
                for other_col in numeric_cols
            }
            for col in numeric_cols
        }

    # --- Summary text ---
    summary_parts: list[str] = [
        f"Dataset: {len(df)} rows, {len(df.columns)} columns "
        f"({len(numeric_cols)} numeric, {len(categorical_cols)} categorical).",
    ]
    if numeric_cols:
        high_corr_pairs: list[str] = []
        for i, c1 in enumerate(numeric_cols):
            for c2 in numeric_cols[i + 1 :]:
                val = correlations.get(c1, {}).get(c2)
                if val is not None and abs(val) >= 0.7:
                    high_corr_pairs.append(f"{c1}/{c2} ({val})")
        if high_corr_pairs:
            summary_parts.append(
                f"Highly correlated pairs (|r| >= 0.7): {', '.join(high_corr_pairs)}."
            )

    return {
        "descriptive": descriptive,
        "correlations": correlations,
        "summary": " ".join(summary_parts),
        "error": None,
    }
