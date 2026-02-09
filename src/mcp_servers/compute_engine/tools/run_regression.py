"""Regression analysis tool for the Compute Engine MCP server.

Supports linear and logistic regression using scikit-learn, returning
coefficients, R-squared (or accuracy), and feature importance.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_VALID_MODEL_TYPES = {"linear", "logistic"}


async def run_regression(
    data: list[dict],
    target: str,
    features: list[str],
    model_type: str = "linear",
) -> dict[str, Any]:
    """Fit a regression model and return diagnostics.

    Parameters
    ----------
    data:
        List of row-dicts.
    target:
        Name of the target (dependent) column.
    features:
        List of feature (independent) column names.
    model_type:
        ``"linear"`` for :class:`~sklearn.linear_model.LinearRegression` or
        ``"logistic"`` for :class:`~sklearn.linear_model.LogisticRegression`.

    Returns
    -------
    dict
        ``{"model_type": str, "coefficients": {...}, "r_squared": float,
        "feature_importance": [...], "summary": str}``
    """
    if not data:
        return _empty_result(model_type, "No data provided.")

    if model_type not in _VALID_MODEL_TYPES:
        return _empty_result(
            model_type,
            f"Unknown model_type '{model_type}'. Supported: {sorted(_VALID_MODEL_TYPES)}.",
        )

    if not features:
        return _empty_result(model_type, "No features specified.")

    try:
        df = pd.DataFrame(data)
    except Exception as exc:
        return _empty_result(model_type, f"Failed to create DataFrame: {exc}")

    # Validate columns exist
    required_cols = [target] + list(features)
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return _empty_result(
            model_type,
            f"Columns not found in data: {missing}. Available: {df.columns.tolist()}.",
        )

    # Coerce to numeric and drop rows with NaNs in relevant columns
    for col in required_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[required_cols].dropna()

    if df.empty:
        return _empty_result(
            model_type,
            "No valid rows remain after dropping NaN values.",
        )

    if len(df) < len(features) + 1:
        return _empty_result(
            model_type,
            f"Insufficient data: {len(df)} rows for {len(features)} features (need at least {len(features) + 1}).",
        )

    X = df[features].values  # noqa: N806
    y = df[target].values

    try:
        if model_type == "linear":
            result = _fit_linear(X, y, features, target)
        else:
            result = _fit_logistic(X, y, features, target)
    except Exception as exc:
        logger.exception("Regression fitting failed (model_type=%s)", model_type)
        return _empty_result(model_type, f"Model fitting failed: {exc}")

    return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _empty_result(model_type: str, error: str) -> dict[str, Any]:
    return {
        "model_type": model_type,
        "coefficients": {},
        "intercept": None,
        "r_squared": None,
        "feature_importance": [],
        "predictions_sample": [],
        "summary": "",
        "error": error,
    }


def _fit_linear(
    X: np.ndarray,  # noqa: N803
    y: np.ndarray,
    features: list[str],
    target: str,
) -> dict[str, Any]:
    """Fit an OLS linear regression and return diagnostics."""
    from sklearn.linear_model import LinearRegression

    model = LinearRegression()
    model.fit(X, y)

    r_squared = float(model.score(X, y))
    coefficients = {feat: round(float(c), 6) for feat, c in zip(features, model.coef_)}
    intercept = round(float(model.intercept_), 6)

    # Feature importance based on absolute standardised coefficients
    std_x = np.std(X, axis=0)
    std_y = np.std(y) if np.std(y) != 0 else 1.0
    standardised = np.abs(model.coef_ * std_x / std_y)
    total = standardised.sum()
    importance = (
        standardised / total if total > 0 else np.zeros_like(standardised)
    )

    feature_importance = sorted(
        [
            {"feature": feat, "importance": round(float(imp), 4)}
            for feat, imp in zip(features, importance)
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )

    # Small sample of predictions for quick inspection
    predictions = model.predict(X)
    sample_size = min(10, len(predictions))
    predictions_sample = [
        {"actual": round(float(y[i]), 4), "predicted": round(float(predictions[i]), 4)}
        for i in range(sample_size)
    ]

    summary = (
        f"Linear regression on '{target}' using {len(features)} feature(s). "
        f"R-squared: {r_squared:.4f}. "
        f"Top feature: {feature_importance[0]['feature']} "
        f"(importance {feature_importance[0]['importance']:.4f})."
    )

    return {
        "model_type": "linear",
        "coefficients": coefficients,
        "intercept": intercept,
        "r_squared": round(r_squared, 4),
        "feature_importance": feature_importance,
        "predictions_sample": predictions_sample,
        "summary": summary,
        "error": None,
    }


def _fit_logistic(
    X: np.ndarray,  # noqa: N803
    y: np.ndarray,
    features: list[str],
    target: str,
) -> dict[str, Any]:
    """Fit a logistic regression and return diagnostics."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)  # noqa: N806

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_scaled, y)

    accuracy = float(model.score(X_scaled, y))

    # For binary logistic regression coef_ is shape (1, n_features)
    coef = model.coef_[0] if model.coef_.ndim > 1 else model.coef_
    coefficients = {feat: round(float(c), 6) for feat, c in zip(features, coef)}
    intercept = round(float(model.intercept_[0] if np.ndim(model.intercept_) > 0 else model.intercept_), 6)

    abs_coef = np.abs(coef)
    total = abs_coef.sum()
    importance = abs_coef / total if total > 0 else np.zeros_like(abs_coef)

    feature_importance = sorted(
        [
            {"feature": feat, "importance": round(float(imp), 4)}
            for feat, imp in zip(features, importance)
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )

    predictions = model.predict(X_scaled)
    sample_size = min(10, len(predictions))
    predictions_sample = [
        {"actual": float(y[i]), "predicted": float(predictions[i])}
        for i in range(sample_size)
    ]

    summary = (
        f"Logistic regression on '{target}' using {len(features)} feature(s). "
        f"Training accuracy: {accuracy:.4f}. "
        f"Top feature: {feature_importance[0]['feature']} "
        f"(importance {feature_importance[0]['importance']:.4f})."
    )

    return {
        "model_type": "logistic",
        "coefficients": coefficients,
        "intercept": intercept,
        "r_squared": round(accuracy, 4),  # accuracy in place of R^2 for logistic
        "feature_importance": feature_importance,
        "predictions_sample": predictions_sample,
        "summary": summary,
        "error": None,
    }
