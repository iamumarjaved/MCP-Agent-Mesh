"""Tool: clean_data -- Apply a pipeline of cleaning operations to a dataset."""

from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

_SUPPORTED_OPERATIONS = {"dedup", "impute", "normalize"}


def _dedup(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate rows."""
    return df.drop_duplicates().reset_index(drop=True)


def _impute(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing values: median for numeric columns, mode for others."""
    for col in df.columns:
        if df[col].isna().sum() == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
        else:
            mode = df[col].mode()
            if not mode.empty:
                df[col] = df[col].fillna(mode.iloc[0])
    return df


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Min-max scale all numeric columns to [0, 1]."""
    numeric_cols = df.select_dtypes(include="number").columns
    for col in numeric_cols:
        col_min = df[col].min()
        col_max = df[col].max()
        if col_max - col_min != 0:
            df[col] = (df[col] - col_min) / (col_max - col_min)
        else:
            # Constant column -- set to 0.0 to avoid division by zero
            df[col] = 0.0
    return df


_OPERATION_MAP = {
    "dedup": _dedup,
    "impute": _impute,
    "normalize": _normalize,
}


async def clean_data(
    data: list[dict],
    operations: list[str],
) -> dict[str, Any]:
    """Apply a sequence of cleaning operations to the provided data.

    Parameters
    ----------
    data:
        A list of row dicts.
    operations:
        Ordered list of operation names to apply.  Supported values:
        ``"dedup"``, ``"impute"``, ``"normalize"``.

    Returns
    -------
    dict
        ``data`` (cleaned records), ``operations_applied``,
        ``rows_before``, ``rows_after``.
    """
    log = logger.bind(tool="clean_data", operations=operations)
    log.info("clean_data.start", row_count=len(data))

    # Validate operations
    unknown = set(operations) - _SUPPORTED_OPERATIONS
    if unknown:
        raise ValueError(
            f"Unsupported cleaning operations: {sorted(unknown)}. "
            f"Supported: {sorted(_SUPPORTED_OPERATIONS)}"
        )

    if not data:
        return {
            "data": [],
            "operations_applied": list(operations),
            "rows_before": 0,
            "rows_after": 0,
        }

    def _run_pipeline() -> tuple[list[dict], int, int]:
        df = pd.DataFrame(data)
        rows_before = len(df)
        applied: list[str] = []
        for op_name in operations:
            fn = _OPERATION_MAP[op_name]
            df = fn(df)
            applied.append(op_name)
        return df.to_dict(orient="records"), rows_before, len(df)

    loop = asyncio.get_running_loop()
    records, rows_before, rows_after = await loop.run_in_executor(None, _run_pipeline)

    log.info(
        "clean_data.done",
        rows_before=rows_before,
        rows_after=rows_after,
    )

    return {
        "data": records,
        "operations_applied": list(operations),
        "rows_before": rows_before,
        "rows_after": rows_after,
    }
