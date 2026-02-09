"""Tool: transform_data -- Apply structural transformations to a dataset."""

from __future__ import annotations

import asyncio
import operator
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

_SUPPORTED_OPERATIONS = {"filter", "aggregate", "sort", "select"}

# Comparison operators for the "filter" operation.
_FILTER_OPS: dict[str, Any] = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "contains": None,  # handled separately for string matching
}


def _transform_filter(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Filter rows by column value."""
    column = params.get("column")
    op_name = params.get("operator", "eq")
    value = params.get("value")

    if column is None or column not in df.columns:
        raise ValueError(
            f"Filter column '{column}' not found. Available: {list(df.columns)}"
        )
    if op_name not in _FILTER_OPS:
        raise ValueError(
            f"Unsupported filter operator '{op_name}'. "
            f"Supported: {sorted(_FILTER_OPS)}"
        )

    if op_name == "contains":
        mask = df[column].astype(str).str.contains(str(value), na=False)
    else:
        cmp_fn = _FILTER_OPS[op_name]
        mask = cmp_fn(df[column], value)

    return df.loc[mask].reset_index(drop=True)


def _transform_aggregate(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Group-by aggregation."""
    group_by = params.get("group_by")
    agg_func = params.get("agg_func", "sum")

    if group_by is None:
        raise ValueError("'group_by' is required for aggregation")

    # Normalise to list
    if isinstance(group_by, str):
        group_by = [group_by]

    missing = [c for c in group_by if c not in df.columns]
    if missing:
        raise ValueError(
            f"Group-by columns not found: {missing}. Available: {list(df.columns)}"
        )

    allowed_funcs = {"sum", "mean", "min", "max", "count", "median", "std"}
    if agg_func not in allowed_funcs:
        raise ValueError(
            f"Unsupported agg_func '{agg_func}'. Supported: {sorted(allowed_funcs)}"
        )

    # Select numeric columns for aggregation (besides the group keys)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    agg_cols = [c for c in numeric_cols if c not in group_by]

    if not agg_cols:
        # Fallback: count only
        result = df.groupby(group_by, as_index=False).size()
        result = result.rename(columns={"size": "count"})
    else:
        result = df.groupby(group_by, as_index=False)[agg_cols].agg(agg_func)

    return result


def _transform_sort(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Sort rows by one or more columns."""
    column = params.get("column")
    ascending = params.get("ascending", True)

    if column is None:
        raise ValueError("'column' is required for sort")

    # Normalise to list
    if isinstance(column, str):
        column = [column]

    missing = [c for c in column if c not in df.columns]
    if missing:
        raise ValueError(
            f"Sort columns not found: {missing}. Available: {list(df.columns)}"
        )

    return df.sort_values(by=column, ascending=ascending).reset_index(drop=True)


def _transform_select(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Select a subset of columns."""
    columns = params.get("columns")
    if columns is None or not isinstance(columns, list):
        raise ValueError("'columns' (list of str) is required for select")

    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"Select columns not found: {missing}. Available: {list(df.columns)}"
        )

    return df[columns].copy()


_TRANSFORM_MAP = {
    "filter": _transform_filter,
    "aggregate": _transform_aggregate,
    "sort": _transform_sort,
    "select": _transform_select,
}


async def transform_data(
    data: list[dict],
    operation: str,
    params: dict,
) -> dict[str, Any]:
    """Apply a structural transformation to the provided data.

    Parameters
    ----------
    data:
        A list of row dicts.
    operation:
        One of ``"filter"``, ``"aggregate"``, ``"sort"``, ``"select"``.
    params:
        Operation-specific parameters:

        * **filter**: ``column``, ``operator`` (eq/ne/gt/ge/lt/le/contains),
          ``value``
        * **aggregate**: ``group_by`` (str or list), ``agg_func``
          (sum/mean/min/max/count/median/std)
        * **sort**: ``column`` (str or list), ``ascending`` (bool)
        * **select**: ``columns`` (list of str)

    Returns
    -------
    dict
        ``data`` (transformed records), ``row_count``, ``operation``.
    """
    log = logger.bind(tool="transform_data", operation=operation)
    log.info("transform_data.start", row_count=len(data))

    if operation not in _SUPPORTED_OPERATIONS:
        raise ValueError(
            f"Unsupported transform operation '{operation}'. "
            f"Supported: {sorted(_SUPPORTED_OPERATIONS)}"
        )

    if not data:
        return {
            "data": [],
            "row_count": 0,
            "operation": operation,
        }

    def _run() -> list[dict]:
        df = pd.DataFrame(data)
        fn = _TRANSFORM_MAP[operation]
        result_df = fn(df, params)
        return result_df.to_dict(orient="records")

    loop = asyncio.get_running_loop()
    records = await loop.run_in_executor(None, _run)

    log.info("transform_data.done", row_count=len(records))

    return {
        "data": records,
        "row_count": len(records),
        "operation": operation,
    }
