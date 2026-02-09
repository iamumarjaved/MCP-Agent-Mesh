"""Bias detection tool.

Checks text and recommendations for:
- One-sided / loaded language
- Absolute statements without supporting evidence
- Missing alternative perspectives

Uses keyword and pattern matching heuristics rather than ML models.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Words / phrases that signal one-sided or loaded language
_LOADED_LANGUAGE: list[str] = [
    "obviously",
    "clearly",
    "undeniably",
    "without question",
    "indisputably",
    "unquestionably",
    "beyond doubt",
    "superior",
    "inferior",
    "the best",
    "the worst",
    "no alternative",
    "the only option",
    "the only way",
    "everyone knows",
    "everybody agrees",
    "it is well known",
    "it goes without saying",
    "needless to say",
]

# Patterns for absolute statements (overly certain without evidence)
_ABSOLUTE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\balways\b", re.IGNORECASE),
    re.compile(r"\bnever\b", re.IGNORECASE),
    re.compile(r"\bimpossible\b", re.IGNORECASE),
    re.compile(r"\bguaranteed?\b", re.IGNORECASE),
    re.compile(r"\bperfect(?:ly)?\b", re.IGNORECASE),
    re.compile(r"\bno chance\b", re.IGNORECASE),
    re.compile(r"\b100\s*%\s*(?:certain|sure|guaranteed)\b", re.IGNORECASE),
    re.compile(r"\bwithout exception\b", re.IGNORECASE),
    re.compile(r"\bin every case\b", re.IGNORECASE),
    re.compile(r"\buniversally\b", re.IGNORECASE),
    re.compile(r"\bwill definitely\b", re.IGNORECASE),
    re.compile(r"\bmust always\b", re.IGNORECASE),
    re.compile(r"\bcannot fail\b", re.IGNORECASE),
]

# Balanced language indicators (presence reduces bias score)
_BALANCE_INDICATORS: list[str] = [
    "however",
    "on the other hand",
    "alternatively",
    "conversely",
    "in contrast",
    "some argue",
    "critics note",
    "potential risks",
    "potential drawbacks",
    "limitations include",
    "trade-off",
    "tradeoff",
    "trade off",
    "it is worth noting",
    "consideration",
    "caveat",
    "might",
    "could",
    "may",
    "potentially",
    "it depends",
]


def _check_loaded_language(text: str) -> list[dict[str, Any]]:
    """Find instances of loaded or one-sided language."""
    issues: list[dict[str, Any]] = []
    text_lower = text.lower()
    for phrase in _LOADED_LANGUAGE:
        idx = text_lower.find(phrase)
        if idx != -1:
            # Find surrounding context (up to 80 chars)
            start = max(0, idx - 30)
            end = min(len(text), idx + len(phrase) + 30)
            context = text[start:end].strip()
            issues.append({
                "type": "loaded_language",
                "phrase": phrase,
                "context": f"...{context}...",
                "position": idx,
            })
    return issues


def _check_absolute_statements(text: str) -> list[dict[str, Any]]:
    """Find absolute statements that lack evidence qualifiers."""
    issues: list[dict[str, Any]] = []
    for pattern in _ABSOLUTE_PATTERNS:
        for match in pattern.finditer(text):
            # Check if the surrounding sentence has a qualifier
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            surrounding = text[start:end].lower()

            # If the surrounding context has qualifiers, skip it
            has_qualifier = any(
                q in surrounding
                for q in ["data shows", "according to", "based on", "evidence", "study", "research"]
            )
            if not has_qualifier:
                context_start = max(0, match.start() - 30)
                context_end = min(len(text), match.end() + 30)
                context = text[context_start:context_end].strip()
                issues.append({
                    "type": "absolute_statement",
                    "phrase": match.group(),
                    "context": f"...{context}...",
                    "position": match.start(),
                })
    return issues


def _check_missing_perspectives(text: str) -> list[dict[str, Any]]:
    """Check whether the text lacks alternative viewpoints."""
    issues: list[dict[str, Any]] = []
    text_lower = text.lower()

    balance_count = sum(
        1 for indicator in _BALANCE_INDICATORS if indicator in text_lower
    )

    # Heuristic: longer texts should have more balance indicators
    word_count = len(text.split())
    expected_indicators = max(1, word_count // 200)  # at least 1 per 200 words

    if word_count > 100 and balance_count < expected_indicators:
        issues.append({
            "type": "missing_perspective",
            "phrase": None,
            "context": (
                f"Text has {word_count} words but only {balance_count} "
                f"balance indicator(s) (expected at least {expected_indicators})."
            ),
            "position": 0,
        })

    return issues


def _check_recommendations_bias(recommendations: list[str]) -> list[dict[str, Any]]:
    """Check recommendation strings for one-sided framing."""
    issues: list[dict[str, Any]] = []
    for idx, rec in enumerate(recommendations):
        rec_lower = rec.lower()

        # Check for loaded language in recommendations
        for phrase in _LOADED_LANGUAGE:
            if phrase in rec_lower:
                issues.append({
                    "type": "biased_recommendation",
                    "phrase": phrase,
                    "context": rec,
                    "position": idx,
                })

        # Check for absolute language
        for pattern in _ABSOLUTE_PATTERNS:
            if pattern.search(rec):
                issues.append({
                    "type": "absolute_recommendation",
                    "phrase": pattern.pattern.replace(r"\b", ""),
                    "context": rec,
                    "position": idx,
                })

    return issues


# ---------------------------------------------------------------------------
# Public tool handler
# ---------------------------------------------------------------------------

async def check_bias(arguments: dict) -> dict:
    """Check text and recommendations for bias indicators.

    Parameters (via *arguments* dict)
    ----------------------------------
    text : str
        The text to analyse.
    recommendations : list[str] | None
        Optional recommendation strings to check separately.

    Returns
    -------
    dict
        ``{"bias_detected": bool, "score": float, "issues": [...],
        "suggestions": [...]}``
    """
    text: str = arguments["text"]
    recommendations: list[str] | None = arguments.get("recommendations")

    all_issues: list[dict[str, Any]] = []

    all_issues.extend(_check_loaded_language(text))
    all_issues.extend(_check_absolute_statements(text))
    all_issues.extend(_check_missing_perspectives(text))

    if recommendations:
        all_issues.extend(_check_recommendations_bias(recommendations))

    # Compute bias score (1.0 = no bias, 0.0 = heavily biased)
    # Each issue reduces the score; diminishing returns after many issues
    issue_count = len(all_issues)
    if issue_count == 0:
        score = 1.0
    else:
        # Logistic-style decay: score = 1 / (1 + k * issues)
        score = 1.0 / (1.0 + 0.15 * issue_count)
        score = round(max(0.0, score), 4)

    # Build suggestions
    suggestions: list[str] = []
    issue_types = {issue["type"] for issue in all_issues}

    if "loaded_language" in issue_types:
        suggestions.append(
            "Replace loaded or emotionally charged language with neutral, "
            "evidence-based phrasing."
        )
    if "absolute_statement" in issue_types:
        suggestions.append(
            "Qualify absolute statements (always, never, guaranteed) with "
            "supporting evidence or soften to probabilistic language."
        )
    if "missing_perspective" in issue_types:
        suggestions.append(
            "Include alternative viewpoints, potential risks, or "
            "counterarguments to provide a balanced analysis."
        )
    if "biased_recommendation" in issue_types or "absolute_recommendation" in issue_types:
        suggestions.append(
            "Review recommendations for one-sided framing. Present "
            "trade-offs and alternative approaches."
        )
    if not suggestions:
        suggestions.append("No bias issues detected. Text appears balanced.")

    return {
        "bias_detected": issue_count > 0,
        "score": score,
        "issues": all_issues,
        "suggestions": suggestions,
    }
