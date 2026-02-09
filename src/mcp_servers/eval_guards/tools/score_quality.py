"""Quality scoring tool.

Aggregates individual guard-check results into a single overall quality
score and determines a verdict based on configurable thresholds.

Weights
-------
- data_integrity : 0.25
- hallucination  : 0.25
- statistics     : 0.20
- pii            : 0.15
- bias           : 0.15

Verdicts
--------
- ``auto_approve``  : overall score >= 0.85
- ``flag_warnings`` : 0.60 <= score < 0.85
- ``reprocess``     : 0.40 <= score < 0.60
- ``escalate``      : score < 0.40
"""

from __future__ import annotations

from typing import Any

# Check name -> weight
_DEFAULT_WEIGHTS: dict[str, float] = {
    "data_integrity": 0.25,
    "hallucination": 0.25,
    "statistics": 0.20,
    "pii": 0.15,
    "bias": 0.15,
}

# Verdict thresholds (descending)
_THRESHOLDS: list[tuple[float, str]] = [
    (0.85, "auto_approve"),
    (0.60, "flag_warnings"),
    (0.40, "reprocess"),
]
_DEFAULT_VERDICT = "escalate"


def _determine_verdict(score: float) -> str:
    """Map an overall score to a verdict string."""
    for threshold, verdict in _THRESHOLDS:
        if score >= threshold:
            return verdict
    return _DEFAULT_VERDICT


def _build_recommendations(
    breakdown: dict[str, dict[str, Any]],
    overall_score: float,
) -> list[str]:
    """Generate actionable recommendations based on check scores."""
    recommendations: list[str] = []

    for check_name, info in breakdown.items():
        score = info.get("score", 1.0)
        if score < 0.60:
            label = check_name.replace("_", " ").title()
            recommendations.append(
                f"{label} score is critically low ({score:.2f}). "
                f"Review and re-run this check before publishing."
            )
        elif score < 0.85:
            label = check_name.replace("_", " ").title()
            recommendations.append(
                f"{label} score ({score:.2f}) is below the auto-approve "
                f"threshold. Consider manual review."
            )

    if overall_score < 0.40:
        recommendations.append(
            "Overall quality is below acceptable levels. Escalate to a "
            "human reviewer before proceeding."
        )
    elif overall_score < 0.60:
        recommendations.append(
            "Content should be reprocessed by the generating agent with "
            "feedback on flagged issues."
        )

    if not recommendations:
        recommendations.append("All checks passed. Content is ready for delivery.")

    return recommendations


async def score_quality(arguments: dict) -> dict:
    """Aggregate guard-check scores into an overall quality verdict.

    Parameters (via *arguments* dict)
    ----------------------------------
    content : str
        The content that was evaluated (kept for audit context).
    checks : dict
        Mapping of check names to result dicts.  Each result must
        contain at least a ``score`` key (float 0-1).  Recognised
        check names are ``data_integrity``, ``hallucination``,
        ``statistics``, ``pii``, and ``bias``.

    Returns
    -------
    dict
        ``{"overall_score": float, "verdict": str,
        "breakdown": {...}, "recommendations": [...]}``
    """
    content: str = arguments["content"]
    checks: dict[str, dict[str, Any]] = arguments["checks"]

    breakdown: dict[str, dict[str, Any]] = {}
    weighted_sum = 0.0
    total_weight = 0.0

    for check_name, weight in _DEFAULT_WEIGHTS.items():
        check_result = checks.get(check_name)
        if check_result is not None:
            score = float(check_result.get("score", 0.0))
            score = max(0.0, min(1.0, score))  # clamp to [0, 1]
            breakdown[check_name] = {
                "score": round(score, 4),
                "weight": weight,
                "weighted_contribution": round(score * weight, 4),
                "passed": check_result.get("passed", score >= 0.85),
            }
            weighted_sum += score * weight
            total_weight += weight
        else:
            # Check not provided -- note it but do not penalise
            breakdown[check_name] = {
                "score": None,
                "weight": weight,
                "weighted_contribution": 0.0,
                "passed": None,
                "note": "Check result not provided.",
            }

    # Handle any extra checks not in the default set
    for check_name, check_result in checks.items():
        if check_name not in _DEFAULT_WEIGHTS:
            score = float(check_result.get("score", 0.0))
            score = max(0.0, min(1.0, score))
            extra_weight = 0.10  # minor weight for unrecognised checks
            breakdown[check_name] = {
                "score": round(score, 4),
                "weight": extra_weight,
                "weighted_contribution": round(score * extra_weight, 4),
                "passed": check_result.get("passed", score >= 0.85),
            }
            weighted_sum += score * extra_weight
            total_weight += extra_weight

    overall_score = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0
    verdict = _determine_verdict(overall_score)
    recommendations = _build_recommendations(breakdown, overall_score)

    return {
        "overall_score": overall_score,
        "verdict": verdict,
        "breakdown": breakdown,
        "recommendations": recommendations,
    }
