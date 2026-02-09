"""Hallucination detection tool.

Performs simple claim verification by extracting numeric values from
textual claims and checking whether those values appear anywhere in the
provided source data.  This is a lightweight heuristic -- not a full
entailment model -- suitable for catching obvious fabrications.
"""

from __future__ import annotations

import re
from typing import Any


def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from a text string.

    Handles integers, decimals, percentages (stripped of ``%``), and
    values with comma separators (e.g. ``1,234.56``).
    """
    # Match patterns like 1,234.56 or 42.5% or plain 42
    raw_matches = re.findall(
        r"(?<!\w)(\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?)(?!\w)",
        text,
    )
    numbers: list[float] = []
    for raw in raw_matches:
        cleaned = raw.replace(",", "").replace("$", "").replace("%", "")
        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue
    return numbers


def _flatten_values(obj: Any) -> list[float]:
    """Recursively extract all numeric values from a nested structure."""
    values: list[float] = []
    if isinstance(obj, dict):
        for v in obj.values():
            values.extend(_flatten_values(v))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            values.extend(_flatten_values(item))
    elif isinstance(obj, (int, float)):
        values.append(float(obj))
    elif isinstance(obj, str):
        # Try to parse stringified numbers
        try:
            values.append(float(obj.replace(",", "")))
        except ValueError:
            pass
    return values


def _number_matches(claim_num: float, source_nums: set[float], tolerance: float = 0.01) -> bool:
    """Check if a claimed number approximately matches any source number.

    Uses both absolute and relative tolerance to handle rounding
    differences.
    """
    for src in source_nums:
        if src == 0 and claim_num == 0:
            return True
        if abs(claim_num - src) <= tolerance:
            return True
        # Relative tolerance for larger numbers
        if src != 0 and abs((claim_num - src) / src) <= tolerance:
            return True
    return False


async def detect_hallucination(arguments: dict) -> dict:
    """Verify numeric claims against source data.

    Parameters (via *arguments* dict)
    ----------------------------------
    claims : list[str]
        Textual claims to verify.
    source_data : dict
        Authoritative data to verify claims against.

    Returns
    -------
    dict
        ``{"verified_claims": int, "total_claims": int,
        "unverified": [...], "score": float}``
    """
    claims: list[str] = arguments["claims"]
    source_data: dict[str, Any] = arguments["source_data"]

    source_numbers = set(_flatten_values(source_data))

    verified_count = 0
    unverified: list[dict[str, Any]] = []

    for claim in claims:
        claim_numbers = _extract_numbers(claim)

        if not claim_numbers:
            # Claims without numbers are treated as unverifiable but
            # not penalised -- they cannot be checked here.
            verified_count += 1
            continue

        all_matched = True
        unmatched_nums: list[float] = []

        for num in claim_numbers:
            if not _number_matches(num, source_numbers):
                all_matched = False
                unmatched_nums.append(num)

        if all_matched:
            verified_count += 1
        else:
            unverified.append({
                "claim": claim,
                "unmatched_numbers": unmatched_nums,
                "reason": (
                    f"Number(s) {unmatched_nums} not found in source data."
                ),
            })

    total = len(claims)
    score = verified_count / total if total > 0 else 1.0

    return {
        "verified_claims": verified_count,
        "total_claims": total,
        "unverified": unverified,
        "score": round(score, 4),
    }
