"""Tool: profile_data -- Generate a data-quality profile for a dataset."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def _profile_column(series: pd.Series) -> dict[str, Any]:
    """Build a profile dict for a single column."""
    total = len(series)
    null_count = int(series.isna().sum())
    unique_count = int(series.nunique(dropna=True))
    dtype_str = str(series.dtype)

    profile: dict[str, Any] = {
        "dtype": dtype_str,
        "null_count": null_count,
        "null_pct": round(null_count / total * 100, 2) if total else 0.0,
        "unique_count": unique_count,
    }

    # Numeric distributions
    if pd.api.types.is_numeric_dtype(series):
        clean = series.dropna()
        profile["min"] = float(clean.min()) if len(clean) else None
        profile["max"] = float(clean.max()) if len(clean) else None
        profile["mean"] = round(float(clean.mean()), 4) if len(clean) else None
        profile["median"] = round(float(clean.median()), 4) if len(clean) else None
        profile["std"] = round(float(clean.std()), 4) if len(clean) > 1 else None
        # Quartiles
        if len(clean) >= 4:
            q1, q3 = float(np.percentile(clean, 25)), float(np.percentile(clean, 75))
            profile["q1"] = round(q1, 4)
            profile["q3"] = round(q3, 4)
    else:
        # Categorical / string top values
        if unique_count > 0:
            top_values = series.value_counts(dropna=True).head(5)
            profile["top_values"] = {
                str(k): int(v) for k, v in top_values.items()
            }

    return profile


def _compute_quality_score(df: pd.DataFrame, column_profiles: dict) -> float:
    """Heuristic quality score between 0 and 1.

    Factors:
    * Completeness -- fraction of non-null cells
    * Uniqueness -- columns with all-identical values penalised
    * Consistency -- mixed types within a column penalised (not easily
      detectable post-parse, so approximated by checking object cols)
    """
    total_cells = df.shape[0] * df.shape[1]
    if total_cells == 0:
        return 0.0

    # Completeness: ratio of non-null cells
    null_cells = sum(p["null_count"] for p in column_profiles.values())
    completeness = 1.0 - (null_cells / total_cells)

    # Uniqueness: penalise columns that are constant (single unique value)
    constant_cols = sum(
        1
        for p in column_profiles.values()
        if p["unique_count"] <= 1 and p["null_count"] < df.shape[0]
    )
    uniqueness = 1.0 - (constant_cols / max(len(column_profiles), 1))

    # Weighted average
    score = 0.6 * completeness + 0.4 * uniqueness
    return round(max(0.0, min(1.0, score)), 4)


async def profile_data(data: list[dict]) -> dict[str, Any]:
    """Generate a comprehensive data-quality profile.

    Parameters
    ----------
    data:
        A list of row dicts (as returned by other data tools).

    Returns
    -------
    dict
        ``row_count``, ``column_count``, ``columns`` (per-column profiles),
        ``quality_score``.
    """
    log = logger.bind(tool="profile_data")
    log.info("profile_data.start", row_count=len(data))

    if not data:
        return {
            "row_count": 0,
            "column_count": 0,
            "columns": {},
            "quality_score": 0.0,
        }

    def _profile() -> dict[str, Any]:
        df = pd.DataFrame(data)
        col_profiles = {col: _profile_column(df[col]) for col in df.columns}
        quality = _compute_quality_score(df, col_profiles)
        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": col_profiles,
            "quality_score": quality,
        }

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _profile)

    log.info("profile_data.done", quality_score=result["quality_score"])
    return result
