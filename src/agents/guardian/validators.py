"""Individual validation check implementations for the Guardian Agent.

Each check function takes the content to validate and the source data,
and returns a dict with ``check_name``, ``passed``, ``score``, ``details``,
and ``warnings``.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_us": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}

# ---------------------------------------------------------------------------
# Bias indicator words (simplified heuristic)
# ---------------------------------------------------------------------------

_BIAS_INDICATORS: list[str] = [
    "obviously",
    "clearly everyone knows",
    "always",
    "never",
    "all women",
    "all men",
    "those people",
    "typical of",
]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_data_integrity(content: dict[str, Any], source_data: dict[str, Any]) -> dict[str, Any]:
    """Verify that the output is structurally complete and internally consistent."""
    warnings: list[str] = []
    score = 1.0

    # Check for empty or missing critical fields
    if not content:
        return {
            "check_name": "data_integrity",
            "passed": False,
            "score": 0.0,
            "details": "Output is empty.",
            "warnings": ["Output content is completely empty."],
        }

    # Check for None values in top-level fields
    none_fields = [k for k, v in content.items() if v is None]
    if none_fields:
        penalty = min(len(none_fields) * 0.1, 0.3)
        score -= penalty
        warnings.append(f"Fields with None values: {none_fields}")

    # Check for empty lists/dicts that should contain data
    empty_fields = [
        k for k, v in content.items()
        if isinstance(v, (list, dict)) and len(v) == 0
    ]
    if empty_fields:
        penalty = min(len(empty_fields) * 0.05, 0.2)
        score -= penalty
        warnings.append(f"Empty collection fields: {empty_fields}")

    # Verify row counts match if present
    claimed_count = content.get("row_count") or content.get("cleaned_row_count")
    actual_data = content.get("data", [])
    if claimed_count is not None and isinstance(actual_data, list):
        if claimed_count != len(actual_data):
            score -= 0.2
            warnings.append(
                f"Row count mismatch: claimed {claimed_count}, actual {len(actual_data)}"
            )

    score = max(score, 0.0)
    return {
        "check_name": "data_integrity",
        "passed": score >= 0.6,
        "score": round(score, 4),
        "details": f"Checked {len(content)} top-level fields.",
        "warnings": warnings,
    }


def check_hallucination(content: dict[str, Any], source_data: dict[str, Any]) -> dict[str, Any]:
    """Check for claims in the output not grounded in source data.

    This is a heuristic check that looks for numeric claims in text
    fields and tries to verify them against source data values.
    """
    warnings: list[str] = []
    score = 1.0

    # Extract all text from the content
    text_fragments = _extract_text(content)
    all_text = " ".join(text_fragments)

    # Extract numbers mentioned in text
    mentioned_numbers = set(re.findall(r"\b\d+\.?\d*\b", all_text))

    # Extract numbers from source data
    source_numbers: set[str] = set()
    _collect_numbers(source_data, source_numbers)

    if not mentioned_numbers:
        return {
            "check_name": "hallucination_detection",
            "passed": True,
            "score": 1.0,
            "details": "No numeric claims found in text to verify.",
            "warnings": [],
        }

    # Check what fraction of mentioned numbers appear in source
    ungrounded = mentioned_numbers - source_numbers
    # Filter out very small numbers (indices, counts) that are likely generated
    significant_ungrounded = {n for n in ungrounded if float(n) > 10}

    if significant_ungrounded:
        ratio = len(significant_ungrounded) / max(len(mentioned_numbers), 1)
        score -= min(ratio * 0.5, 0.4)
        warnings.append(
            f"Potentially ungrounded numbers: {list(significant_ungrounded)[:10]}"
        )

    score = max(score, 0.0)
    return {
        "check_name": "hallucination_detection",
        "passed": score >= 0.6,
        "score": round(score, 4),
        "details": (
            f"Checked {len(mentioned_numbers)} numeric claims; "
            f"{len(significant_ungrounded)} potentially ungrounded."
        ),
        "warnings": warnings,
    }


def check_pii(content: dict[str, Any], source_data: dict[str, Any]) -> dict[str, Any]:
    """Scan output text for personally identifiable information."""
    warnings: list[str] = []
    pii_found: dict[str, list[str]] = {}

    text_fragments = _extract_text(content)
    all_text = " ".join(text_fragments)

    for pii_type, pattern in _PII_PATTERNS.items():
        matches = pattern.findall(all_text)
        if matches:
            # Deduplicate
            unique_matches = list(set(matches))
            pii_found[pii_type] = unique_matches[:5]  # Cap displayed matches
            warnings.append(
                f"PII detected ({pii_type}): {len(unique_matches)} instance(s)"
            )

    total_pii_count = sum(len(v) for v in pii_found.values())

    if total_pii_count == 0:
        score = 1.0
    elif total_pii_count <= 2:
        score = 0.5
    else:
        score = 0.2

    return {
        "check_name": "pii_scanning",
        "passed": total_pii_count == 0,
        "score": round(score, 4),
        "details": f"Scanned {len(all_text)} characters; found {total_pii_count} PII instance(s).",
        "warnings": warnings,
        "pii_found": pii_found,
    }


def check_statistical_validity(
    content: dict[str, Any],
    source_data: dict[str, Any],
) -> dict[str, Any]:
    """Verify that reported statistics are mathematically consistent."""
    warnings: list[str] = []
    checks_performed = 0
    checks_passed = 0

    # Look for statistics in the content
    stats = (
        content.get("statistics", {})
        or content.get("results", {}).get("statistics", {})
    )

    descriptive = {}
    if isinstance(stats, dict):
        descriptive = stats.get("descriptive", stats)

    for col, col_stats in descriptive.items():
        if not isinstance(col_stats, dict):
            continue
        if col_stats.get("type") != "numeric":
            continue

        mean = col_stats.get("mean")
        min_val = col_stats.get("min")
        max_val = col_stats.get("max")
        median = col_stats.get("median")
        std = col_stats.get("std")

        # Check: mean between min and max
        if mean is not None and min_val is not None and max_val is not None:
            checks_performed += 1
            if min_val <= mean <= max_val:
                checks_passed += 1
            else:
                warnings.append(
                    f"Column '{col}': mean ({mean}) outside [min ({min_val}), max ({max_val})]"
                )

        # Check: median between min and max
        if median is not None and min_val is not None and max_val is not None:
            checks_performed += 1
            if min_val <= median <= max_val:
                checks_passed += 1
            else:
                warnings.append(
                    f"Column '{col}': median ({median}) outside [min ({min_val}), max ({max_val})]"
                )

        # Check: std non-negative
        if std is not None:
            checks_performed += 1
            if std >= 0:
                checks_passed += 1
            else:
                warnings.append(f"Column '{col}': negative std ({std})")

        # Check: min <= max
        if min_val is not None and max_val is not None:
            checks_performed += 1
            if min_val <= max_val:
                checks_passed += 1
            else:
                warnings.append(f"Column '{col}': min ({min_val}) > max ({max_val})")

    if checks_performed == 0:
        return {
            "check_name": "statistical_validity",
            "passed": True,
            "score": 1.0,
            "details": "No statistics to validate.",
            "warnings": [],
        }

    score = checks_passed / checks_performed
    return {
        "check_name": "statistical_validity",
        "passed": score >= 0.8,
        "score": round(score, 4),
        "details": f"Passed {checks_passed}/{checks_performed} statistical consistency checks.",
        "warnings": warnings,
    }


def check_bias(content: dict[str, Any], source_data: dict[str, Any]) -> dict[str, Any]:
    """Check text outputs for language indicating potential bias."""
    warnings: list[str] = []

    text_fragments = _extract_text(content)
    all_text = " ".join(text_fragments).lower()

    found_indicators: list[str] = []
    for indicator in _BIAS_INDICATORS:
        if indicator.lower() in all_text:
            found_indicators.append(indicator)

    if not found_indicators:
        score = 1.0
    elif len(found_indicators) <= 1:
        score = 0.8
        warnings.append(f"Mild bias indicator detected: '{found_indicators[0]}'")
    else:
        score = max(0.4, 1.0 - len(found_indicators) * 0.15)
        warnings.append(f"Multiple bias indicators: {found_indicators}")

    return {
        "check_name": "bias_detection",
        "passed": score >= 0.7,
        "score": round(score, 4),
        "details": f"Scanned text for {len(_BIAS_INDICATORS)} bias indicators.",
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

# Check name -> (function, weight)
_ALL_CHECKS: dict[str, tuple[Any, float]] = {
    "data_integrity": (check_data_integrity, 0.25),
    "hallucination_detection": (check_hallucination, 0.25),
    "pii_scanning": (check_pii, 0.20),
    "statistical_validity": (check_statistical_validity, 0.15),
    "bias_detection": (check_bias, 0.15),
}


async def run_all_checks(
    content: dict[str, Any],
    source_data: dict[str, Any],
    checks: list[str] | None = None,
) -> dict[str, Any]:
    """Run specified validation checks (or all by default) and return aggregated result.

    Returns
    -------
    dict
        ``{"checks": [...], "overall_score": float, "passed": bool,
          "recommendations": [...]}``
    """
    selected = checks if checks else list(_ALL_CHECKS.keys())

    results: list[dict[str, Any]] = []
    weighted_sum = 0.0
    total_weight = 0.0

    for check_name in selected:
        entry = _ALL_CHECKS.get(check_name)
        if entry is None:
            results.append({
                "check_name": check_name,
                "passed": False,
                "score": 0.0,
                "details": f"Unknown check: {check_name}",
                "warnings": [],
            })
            continue

        func, weight = entry
        result = func(content, source_data)
        results.append(result)
        weighted_sum += result["score"] * weight
        total_weight += weight

    overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Gather recommendations
    recommendations: list[str] = []
    for r in results:
        if not r.get("passed", True):
            recommendations.append(
                f"Fix {r['check_name']}: {r.get('details', '')} "
                f"(score: {r.get('score', 0):.2f})"
            )
        for w in r.get("warnings", []):
            recommendations.append(f"[{r['check_name']}] {w}")

    return {
        "checks": results,
        "overall_score": round(overall_score, 4),
        "passed": overall_score >= 0.6,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Text extraction helper
# ---------------------------------------------------------------------------

def _extract_text(obj: Any, depth: int = 0) -> list[str]:
    """Recursively extract string values from a nested structure."""
    if depth > 10:
        return []
    fragments: list[str] = []
    if isinstance(obj, str):
        fragments.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            fragments.extend(_extract_text(v, depth + 1))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            fragments.extend(_extract_text(item, depth + 1))
    return fragments


def _collect_numbers(obj: Any, numbers: set[str], depth: int = 0) -> None:
    """Recursively collect numeric string representations from a structure."""
    if depth > 10:
        return
    if isinstance(obj, (int, float)):
        numbers.add(str(obj))
        # Also add common representations
        if isinstance(obj, float):
            numbers.add(f"{obj:.2f}")
            numbers.add(f"{obj:.0f}")
    elif isinstance(obj, str):
        for match in re.findall(r"\b\d+\.?\d*\b", obj):
            numbers.add(match)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, numbers, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _collect_numbers(item, numbers, depth + 1)
