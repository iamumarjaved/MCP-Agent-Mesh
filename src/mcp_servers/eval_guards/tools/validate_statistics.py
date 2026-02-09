"""Statistical validation tool.

Validates statistical claims (mean, sum, count, min, max, percentages)
by recomputing them from source data and comparing against stated values.
Claim labels are parsed heuristically to determine the operation and
target column.
"""

from __future__ import annotations

import re
from typing import Any


def _extract_column_values(
    source_data: list[dict[str, Any]],
    column: str,
) -> list[float]:
    """Extract numeric values for *column* from source rows."""
    values: list[float] = []
    for row in source_data:
        val = row.get(column)
        if val is not None:
            try:
                values.append(float(val))
            except (TypeError, ValueError):
                continue
    return values


def _compute_stat(operation: str, values: list[float]) -> float | None:
    """Compute a statistical operation on a list of floats."""
    if not values:
        return None

    if operation == "mean":
        return sum(values) / len(values)
    if operation == "sum":
        return sum(values)
    if operation == "count":
        return float(len(values))
    if operation == "min":
        return min(values)
    if operation == "max":
        return max(values)
    if operation == "median":
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        return sorted_vals[mid]
    return None


def _parse_claim_label(label: str) -> tuple[str, str]:
    """Heuristically parse a claim label into (operation, column).

    Supports patterns like:
    - ``"mean_revenue"`` -> ``("mean", "revenue")``
    - ``"sum of sales"`` -> ``("sum", "sales")``
    - ``"total_cost"``   -> ``("sum", "cost")``
    - ``"average price"`` -> ``("mean", "price")``
    - ``"revenue_count"`` -> ``("count", "revenue")``
    """
    normalized = label.lower().strip()

    # Map common synonyms to canonical operation names
    synonym_map = {
        "average": "mean",
        "avg": "mean",
        "total": "sum",
        "minimum": "min",
        "maximum": "max",
        "med": "median",
    }

    # Try "operation_column" or "operation of column"
    for sep in ("_", " of ", " "):
        parts = normalized.split(sep, maxsplit=1)
        if len(parts) == 2:
            op_candidate = parts[0].strip()
            col_candidate = parts[1].strip().replace(" ", "_")
            op_canonical = synonym_map.get(op_candidate, op_candidate)
            if op_canonical in ("mean", "sum", "count", "min", "max", "median"):
                return op_canonical, col_candidate

    # Try "column_operation" (e.g. "revenue_mean")
    for sep in ("_", " "):
        parts = normalized.rsplit(sep, maxsplit=1)
        if len(parts) == 2:
            col_candidate = parts[0].strip().replace(" ", "_")
            op_candidate = parts[1].strip()
            op_canonical = synonym_map.get(op_candidate, op_candidate)
            if op_canonical in ("mean", "sum", "count", "min", "max", "median"):
                return op_canonical, col_candidate

    # Default: try treating entire label as column, assume "mean"
    return "mean", normalized.replace(" ", "_")


def _values_match(claimed: float, actual: float, tolerance: float = 0.01) -> bool:
    """Check whether two values match within tolerance."""
    if actual == 0:
        return abs(claimed) <= tolerance
    return abs((claimed - actual) / actual) <= tolerance


async def validate_statistics(arguments: dict) -> dict:
    """Validate statistical claims against recomputed values.

    Parameters (via *arguments* dict)
    ----------------------------------
    claims : dict
        Keys are descriptive labels (e.g. ``"mean_revenue"``), values
        are the claimed numeric results.
    source_data : list[dict]
        Row-oriented source data to recompute statistics from.

    Returns
    -------
    dict
        ``{"valid": bool, "score": float, "validations": [...]}``
    """
    claims: dict[str, Any] = arguments["claims"]
    source_data: list[dict[str, Any]] = arguments["source_data"]

    validations: list[dict[str, Any]] = []
    match_count = 0
    total = 0

    # Collect all available columns for fuzzy matching
    available_columns: set[str] = set()
    for row in source_data:
        available_columns.update(row.keys())

    for label, claimed_value in claims.items():
        try:
            claimed_float = float(claimed_value)
        except (TypeError, ValueError):
            validations.append({
                "claim": label,
                "expected": claimed_value,
                "actual": None,
                "match": False,
                "reason": f"Claimed value '{claimed_value}' is not numeric.",
            })
            total += 1
            continue

        operation, column = _parse_claim_label(label)

        # Try exact match on column name first, then fuzzy
        target_column: str | None = None
        if column in available_columns:
            target_column = column
        else:
            # Try case-insensitive or partial match
            for ac in available_columns:
                if ac.lower() == column.lower():
                    target_column = ac
                    break
                if column.lower() in ac.lower() or ac.lower() in column.lower():
                    target_column = ac
                    break

        if target_column is None:
            validations.append({
                "claim": label,
                "expected": claimed_float,
                "actual": None,
                "match": False,
                "reason": (
                    f"Column '{column}' (from label '{label}') not found in source data. "
                    f"Available: {sorted(available_columns)}"
                ),
            })
            total += 1
            continue

        values = _extract_column_values(source_data, target_column)
        if not values:
            validations.append({
                "claim": label,
                "expected": claimed_float,
                "actual": None,
                "match": False,
                "reason": f"No numeric values found in column '{target_column}'.",
            })
            total += 1
            continue

        actual = _compute_stat(operation, values)
        if actual is None:
            validations.append({
                "claim": label,
                "expected": claimed_float,
                "actual": None,
                "match": False,
                "reason": f"Unsupported operation '{operation}'.",
            })
            total += 1
            continue

        matched = _values_match(claimed_float, actual)
        if matched:
            match_count += 1

        validations.append({
            "claim": label,
            "expected": round(claimed_float, 4),
            "actual": round(actual, 4),
            "match": matched,
        })
        total += 1

    score = match_count / total if total > 0 else 1.0

    return {
        "valid": score >= 0.95,
        "score": round(score, 4),
        "validations": validations,
    }
