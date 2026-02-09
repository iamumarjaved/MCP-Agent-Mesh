"""Cluster analysis tool for the Compute Engine MCP server.

Supports KMeans and DBSCAN clustering with silhouette scoring and
centroid reporting.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_VALID_METHODS = {"kmeans", "dbscan"}


async def cluster_analysis(
    data: list[dict],
    features: list[str],
    n_clusters: int = 3,
    method: str = "kmeans",
) -> dict[str, Any]:
    """Perform cluster analysis on the supplied data.

    Parameters
    ----------
    data:
        List of row-dicts.
    features:
        Column names to use as clustering features.
    n_clusters:
        Desired number of clusters (used by KMeans; ignored for DBSCAN).
    method:
        ``"kmeans"`` or ``"dbscan"``.

    Returns
    -------
    dict
        ``{"clusters": [...], "n_clusters": int, "silhouette_score": float,
        "cluster_sizes": {...}, "centroids": [...]}``
    """
    if not data:
        return _empty_result(method, "No data provided.")

    if method not in _VALID_METHODS:
        return _empty_result(
            method,
            f"Unknown method '{method}'. Supported: {sorted(_VALID_METHODS)}.",
        )

    if not features:
        return _empty_result(method, "No features specified.")

    try:
        df = pd.DataFrame(data)
    except Exception as exc:
        return _empty_result(method, f"Failed to create DataFrame: {exc}")

    missing = [c for c in features if c not in df.columns]
    if missing:
        return _empty_result(
            method,
            f"Columns not found in data: {missing}. Available: {df.columns.tolist()}.",
        )

    # Coerce features to numeric and drop incomplete rows
    for col in features:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    subset = df[features].dropna()
    if subset.empty:
        return _empty_result(
            method,
            "No valid rows remain after dropping NaN values in feature columns.",
        )

    if len(subset) < 2:
        return _empty_result(
            method,
            "Need at least 2 valid data points for clustering.",
        )

    X = subset.values  # noqa: N806

    try:
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)  # noqa: N806

        if method == "kmeans":
            labels, centroids_scaled = _fit_kmeans(X_scaled, n_clusters)
            # Inverse-transform centroids back to original scale
            centroids = scaler.inverse_transform(centroids_scaled)
        else:
            labels, centroids = _fit_dbscan(X_scaled, scaler)
    except Exception as exc:
        logger.exception("Clustering failed (method=%s)", method)
        return _empty_result(method, f"Clustering failed: {exc}")

    # Silhouette score (only meaningful with >= 2 clusters and < n_samples clusters)
    unique_labels = set(labels)
    unique_labels.discard(-1)  # DBSCAN noise label

    sil_score: float | None = None
    if 2 <= len(unique_labels) < len(X_scaled):
        try:
            from sklearn.metrics import silhouette_score

            sil_score = round(float(silhouette_score(X_scaled, labels)), 4)
        except Exception as exc:
            logger.warning("Silhouette score computation failed: %s", exc)

    # Build per-row cluster assignments
    cluster_assignments: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        cluster_assignments.append({
            "index": int(subset.index[i]),
            "cluster": int(label),
        })

    # Cluster sizes
    cluster_sizes: dict[str, int] = {}
    for label in labels:
        key = str(int(label))
        cluster_sizes[key] = cluster_sizes.get(key, 0) + 1

    # Format centroids
    centroid_list: list[dict[str, float]] = []
    if centroids is not None:
        for centroid in centroids:
            centroid_list.append(
                {feat: round(float(v), 4) for feat, v in zip(features, centroid)}
            )

    actual_n_clusters = len(unique_labels)

    return {
        "clusters": cluster_assignments,
        "n_clusters": actual_n_clusters,
        "silhouette_score": sil_score,
        "cluster_sizes": cluster_sizes,
        "centroids": centroid_list,
        "method": method,
        "error": None,
    }


# ------------------------------------------------------------------
# Private fitting functions
# ------------------------------------------------------------------


def _empty_result(method: str, error: str) -> dict[str, Any]:
    return {
        "clusters": [],
        "n_clusters": 0,
        "silhouette_score": None,
        "cluster_sizes": {},
        "centroids": [],
        "method": method,
        "error": error,
    }


def _fit_kmeans(
    X: np.ndarray,  # noqa: N803
    n_clusters: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit KMeans and return (labels, centroids)."""
    from sklearn.cluster import KMeans

    # Clamp n_clusters to be at most the number of samples
    k = min(n_clusters, len(X))
    model = KMeans(n_clusters=k, n_init="auto", random_state=42)
    labels = model.fit_predict(X)
    return labels, model.cluster_centers_


def _fit_dbscan(
    X: np.ndarray,  # noqa: N803
    scaler: Any,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Fit DBSCAN and return (labels, centroids_or_None).

    Centroids are computed as the per-cluster mean of the original
    (unscaled) data.
    """
    from sklearn.cluster import DBSCAN

    model = DBSCAN(eps=0.5, min_samples=5)
    labels = model.fit_predict(X)

    # Compute centroids by averaging scaled points in each cluster,
    # then inverse-transforming.
    unique_labels = set(labels)
    unique_labels.discard(-1)

    if not unique_labels:
        return labels, None

    centroids_scaled = []
    for label in sorted(unique_labels):
        mask = labels == label
        centroids_scaled.append(X[mask].mean(axis=0))

    centroids = scaler.inverse_transform(np.array(centroids_scaled))
    return labels, centroids
