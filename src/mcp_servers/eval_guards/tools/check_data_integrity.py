"""Data integrity check tool.

Validates a tabular dataset for completeness (no unexpected nulls),
consistency (values match expected types), and freshness (date fields
are not stale).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Maximum age (in days) before a date field is flagged as stale
_FRESHNESS_THRESHOLD_DAYS = 365

# Python type name -> checker functions
_TYPE_CHECKERS: dict[str, type | tuple[type, ...]] = {
    "str": (str,),
    "string": (str,),
    "int": (int,),
    "integer": (int,),
    "float": (int, float),
    "number": (int, float),
    "bool": (bool,),
    "boolean": (bool,),
}

_DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"),  # ISO 8601
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),                # YYYY-MM-DD
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),                # MM/DD/YYYY
]


def _looks_like_date(value: Any) -> bool:
    """Heuristic: does the value look like a date string?"""
    if not isinstance(value, str):
        return False
    return any(pat.match(value) for pat in _DATE_PATTERNS)


def _try_parse_date(value: str) -> datetime | None:
    """Attempt to parse a date string into a datetime."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


async def check_data_integrity(arguments: dict) -> dict:
    """Check dataset for completeness, consistency, and freshness.

    Parameters (via *arguments* dict)
    ----------------------------------
    data : list[dict]
        Row-oriented dataset.
    expected_schema : dict | None
        Optional mapping of field names to expected type strings
        (e.g. ``{"age": "int", "name": "str"}``).

    Returns
    -------
    dict
        ``{"passed": bool, "score": float, "checks": [...],
        "warnings": [...]}``
    """
    data: list[dict[str, Any]] = arguments["data"]
    expected_schema: dict[str, str] | None = arguments.get("expected_schema")

    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not data:
        return {
            "passed": False,
            "score": 0.0,
            "checks": [{"name": "non_empty", "passed": False, "details": "Dataset is empty."}],
            "warnings": ["Dataset contains no rows."],
        }

    total_rows = len(data)

    # ----- Completeness: detect null / missing values per field -----
    all_fields: set[str] = set()
    for row in data:
        all_fields.update(row.keys())

    null_counts: dict[str, int] = {f: 0 for f in all_fields}
    for row in data:
        for field in all_fields:
            value = row.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                null_counts[field] += 1

    completeness_issues: list[str] = []
    for field, count in null_counts.items():
        if count > 0:
            pct = count / total_rows * 100
            completeness_issues.append(f"{field}: {count}/{total_rows} null ({pct:.1f}%)")

    completeness_ratio = 1.0 - (sum(null_counts.values()) / (total_rows * len(all_fields))) if all_fields else 1.0
    completeness_passed = completeness_ratio >= 0.95

    checks.append({
        "name": "completeness",
        "passed": completeness_passed,
        "details": (
            "All fields are complete."
            if completeness_passed
            else f"Null values detected: {'; '.join(completeness_issues)}"
        ),
    })
    if not completeness_passed:
        warnings.append(f"Dataset has {len(completeness_issues)} field(s) with missing values.")

    # ----- Consistency: type checking against expected schema -----
    if expected_schema:
        type_issues: list[str] = []
        type_checked = 0
        type_passed_count = 0

        for field, expected_type in expected_schema.items():
            allowed_types = _TYPE_CHECKERS.get(expected_type.lower())
            if allowed_types is None:
                warnings.append(f"Unknown type '{expected_type}' for field '{field}'; skipping type check.")
                continue

            for row in data:
                value = row.get(field)
                if value is None:
                    continue  # already counted under completeness
                type_checked += 1
                if isinstance(value, allowed_types):
                    type_passed_count += 1
                else:
                    type_issues.append(
                        f"{field}: expected {expected_type}, got {type(value).__name__}"
                    )

        consistency_score = type_passed_count / type_checked if type_checked else 1.0
        consistency_passed = consistency_score >= 0.95

        # Deduplicate issues for readability
        unique_issues = sorted(set(type_issues))
        checks.append({
            "name": "consistency",
            "passed": consistency_passed,
            "details": (
                "All values match expected types."
                if consistency_passed
                else f"Type mismatches: {'; '.join(unique_issues[:10])}"
            ),
        })
        if not consistency_passed:
            warnings.append(f"{len(type_issues)} type-mismatch occurrence(s) detected.")
    else:
        # Without a schema, infer consistency by checking each column has uniform types
        type_issue_fields: list[str] = []
        for field in all_fields:
            observed: set[str] = set()
            for row in data:
                val = row.get(field)
                if val is not None:
                    observed.add(type(val).__name__)
            if len(observed) > 1:
                type_issue_fields.append(f"{field} ({', '.join(sorted(observed))})")

        inferred_passed = len(type_issue_fields) == 0
        checks.append({
            "name": "consistency",
            "passed": inferred_passed,
            "details": (
                "All columns have uniform types."
                if inferred_passed
                else f"Mixed types in: {'; '.join(type_issue_fields[:10])}"
            ),
        })
        if not inferred_passed:
            warnings.append(f"{len(type_issue_fields)} field(s) have mixed types.")

    # ----- Freshness: check date fields are not stale -----
    date_fields: list[str] = []
    for field in all_fields:
        # Sample first non-null value
        for row in data:
            val = row.get(field)
            if val is not None:
                if _looks_like_date(val):
                    date_fields.append(field)
                break

    stale_fields: list[str] = []
    now = datetime.now(timezone.utc)

    for field in date_fields:
        most_recent: datetime | None = None
        for row in data:
            val = row.get(field)
            if isinstance(val, str):
                parsed = _try_parse_date(val)
                if parsed is not None:
                    if most_recent is None or parsed > most_recent:
                        most_recent = parsed
        if most_recent is not None:
            age_days = (now - most_recent).days
            if age_days > _FRESHNESS_THRESHOLD_DAYS:
                stale_fields.append(f"{field} (most recent: {most_recent.date()}, {age_days}d ago)")

    freshness_passed = len(stale_fields) == 0
    checks.append({
        "name": "freshness",
        "passed": freshness_passed,
        "details": (
            "All date fields are within the freshness threshold."
            if freshness_passed
            else f"Stale date fields: {'; '.join(stale_fields)}"
        ),
    })
    if not freshness_passed:
        warnings.append(f"{len(stale_fields)} date field(s) contain stale data.")

    # ----- Aggregate score -----
    check_scores = [1.0 if c["passed"] else 0.0 for c in checks]
    # Weight completeness slightly higher
    weights = {"completeness": 0.4, "consistency": 0.35, "freshness": 0.25}
    weighted_sum = sum(
        check_scores[i] * weights.get(checks[i]["name"], 1.0 / len(checks))
        for i in range(len(checks))
    )
    overall_score = round(weighted_sum, 4)
    overall_passed = all(c["passed"] for c in checks)

    return {
        "passed": overall_passed,
        "score": overall_score,
        "checks": checks,
        "warnings": warnings,
    }
