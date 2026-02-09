"""PII detection tool.

Uses regex patterns to detect common categories of personally
identifiable information in free text: email addresses, phone numbers,
Social Security Numbers, credit card numbers, and name-like patterns.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# PII regex patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[dict[str, Any]] = [
    {
        "type": "email",
        "pattern": re.compile(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        ),
    },
    {
        "type": "phone_number",
        "pattern": re.compile(
            r"(?<!\d)"
            r"(?:\+?1[\s\-.]?)?"
            r"(?:\(?\d{3}\)?[\s\-.]?)"
            r"\d{3}[\s\-.]?"
            r"\d{4}"
            r"(?!\d)"
        ),
    },
    {
        "type": "ssn",
        "pattern": re.compile(
            r"(?<!\d)\d{3}[\s\-]\d{2}[\s\-]\d{4}(?!\d)"
        ),
    },
    {
        "type": "credit_card",
        "pattern": re.compile(
            r"(?<!\d)"
            r"(?:\d{4}[\s\-]?){3}\d{4}"
            r"(?!\d)"
        ),
    },
    {
        "type": "ip_address",
        "pattern": re.compile(
            r"(?<!\d)"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\."
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\."
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\."
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
            r"(?!\d)"
        ),
    },
]

# Common first name prefixes for simple name detection (limited set)
_NAME_PREFIXES = re.compile(
    r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?",
)


def _assess_risk_level(detections: list[dict[str, Any]]) -> str:
    """Determine risk level based on PII types found."""
    if not detections:
        return "none"

    types_found = {d["type"] for d in detections}

    high_risk_types = {"ssn", "credit_card"}
    medium_risk_types = {"email", "phone_number"}

    if types_found & high_risk_types:
        return "high"
    if types_found & medium_risk_types:
        return "medium"
    return "low"


async def check_pii(arguments: dict) -> dict:
    """Scan text for personally identifiable information.

    Parameters (via *arguments* dict)
    ----------------------------------
    text : str
        The text to scan.

    Returns
    -------
    dict
        ``{"pii_found": bool, "detections": [...],
        "risk_level": str}``
        Each detection contains ``type``, ``value``, and ``position``.
    """
    text: str = arguments["text"]
    detections: list[dict[str, Any]] = []

    for spec in _PII_PATTERNS:
        for match in spec["pattern"].finditer(text):
            detections.append({
                "type": spec["type"],
                "value": match.group(),
                "position": match.start(),
            })

    # Name pattern detection
    for match in _NAME_PREFIXES.finditer(text):
        detections.append({
            "type": "name",
            "value": match.group(),
            "position": match.start(),
        })

    # Sort by position for deterministic output
    detections.sort(key=lambda d: d["position"])

    risk_level = _assess_risk_level(detections)

    return {
        "pii_found": len(detections) > 0,
        "detections": detections,
        "risk_level": risk_level,
    }
