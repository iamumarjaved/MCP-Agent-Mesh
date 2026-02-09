"""RAG-style context retrieval tool.

For demonstration purposes this module uses simple keyword matching against
an in-memory knowledge base.  In production the implementation would be
swapped for a Qdrant vector-search call using pre-computed embeddings.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# In-memory knowledge base (demo data)
# ---------------------------------------------------------------------------

_KNOWLEDGE_BASE: list[dict[str, Any]] = [
    {
        "content": (
            "Q3 revenue grew 12% year-over-year to $4.2B, driven primarily by "
            "cloud services which expanded 28% to represent 45% of total revenue."
        ),
        "source": "quarterly_earnings",
        "tags": ["revenue", "growth", "cloud", "q3", "earnings"],
    },
    {
        "content": (
            "Customer acquisition cost (CAC) decreased 8% to $245 per customer "
            "while lifetime value (LTV) increased 15% to $3,200, improving the "
            "LTV/CAC ratio to 13.1x."
        ),
        "source": "unit_economics",
        "tags": ["cac", "ltv", "acquisition", "customer", "economics"],
    },
    {
        "content": (
            "Employee satisfaction scores averaged 4.2/5.0 across all departments. "
            "Engineering reported the highest at 4.5 while customer support was "
            "lowest at 3.8, indicating potential burnout risks."
        ),
        "source": "hr_analytics",
        "tags": ["employee", "satisfaction", "engineering", "support", "hr"],
    },
    {
        "content": (
            "Monthly active users reached 15.2M, up 22% quarter-over-quarter. "
            "DAU/MAU ratio held steady at 0.42, suggesting healthy engagement. "
            "Average session duration increased 3 minutes to 18 minutes."
        ),
        "source": "product_analytics",
        "tags": ["users", "mau", "dau", "engagement", "session", "product"],
    },
    {
        "content": (
            "Churn rate declined from 5.2% to 4.1% following the launch of the "
            "loyalty program. Net revenue retention improved to 112%, with "
            "expansion revenue offsetting losses from downgrades."
        ),
        "source": "retention_report",
        "tags": ["churn", "retention", "loyalty", "revenue", "nrr"],
    },
    {
        "content": (
            "Infrastructure costs rose 18% to $32M due to GPU capacity expansion. "
            "Cost per transaction fell 12% to $0.003 as throughput scaled. "
            "Gross margin on cloud services held at 68%."
        ),
        "source": "infrastructure_report",
        "tags": ["infrastructure", "cost", "gpu", "margin", "cloud", "transaction"],
    },
    {
        "content": (
            "The enterprise sales pipeline grew 35% to $890M. Average deal size "
            "increased to $125K from $98K. Win rate improved to 32% from 27% "
            "in the prior quarter."
        ),
        "source": "sales_report",
        "tags": ["sales", "pipeline", "enterprise", "deal", "win"],
    },
    {
        "content": (
            "Marketing spend efficiency improved with a blended ROAS of 4.8x. "
            "Paid channels contributed 38% of new signups while organic grew to "
            "represent 45% of acquisition, up from 39%."
        ),
        "source": "marketing_report",
        "tags": ["marketing", "roas", "organic", "paid", "acquisition", "signups"],
    },
    {
        "content": (
            "Technical debt index decreased from 8.2 to 6.5 after a focused "
            "sprint. Deployment frequency increased to 12x per week. Mean time "
            "to recovery (MTTR) improved to 14 minutes from 28 minutes."
        ),
        "source": "engineering_metrics",
        "tags": ["engineering", "debt", "deployment", "mttr", "devops"],
    },
    {
        "content": (
            "Compliance audit passed with zero critical findings. Data processing "
            "agreements cover 98% of vendor relationships. GDPR subject access "
            "requests are fulfilled in an average of 2.3 days."
        ),
        "source": "compliance_report",
        "tags": ["compliance", "audit", "gdpr", "vendor", "data"],
    },
]


def _compute_relevance(query: str, entry: dict[str, Any]) -> float:
    """Compute a simple keyword-overlap relevance score in [0, 1]."""
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not query_tokens:
        return 0.0

    content_tokens = set(re.findall(r"[a-z0-9]+", entry["content"].lower()))
    tag_tokens = {t.lower() for t in entry.get("tags", [])}

    # Tag matches are weighted more heavily than content token matches
    tag_hits = len(query_tokens & tag_tokens)
    content_hits = len(query_tokens & content_tokens)

    score = (tag_hits * 2.0 + content_hits) / (len(query_tokens) * 3.0)
    return min(score, 1.0)


async def retrieve_context(arguments: dict) -> dict:
    """Retrieve context passages relevant to *query*.

    Parameters (via *arguments* dict)
    ----------------------------------
    query : str
        Free-text search query.
    top_k : int, default 5
        Maximum number of results to return.
    sources : list[str] | None
        Optional allowlist of source names to restrict the search.

    Returns
    -------
    dict
        ``{"results": [...], "query": str, "total_results": int}``
        Each result contains ``content``, ``source``, and
        ``relevance_score``.
    """
    query: str = arguments["query"]
    top_k: int = arguments.get("top_k", 5)
    sources: list[str] | None = arguments.get("sources")

    candidates = _KNOWLEDGE_BASE
    if sources:
        source_set = {s.lower() for s in sources}
        candidates = [e for e in candidates if e["source"].lower() in source_set]

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in candidates:
        relevance = _compute_relevance(query, entry)
        if relevance > 0.0:
            scored.append((relevance, entry))

    # Sort descending by relevance, then take top_k
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_results = scored[:top_k]

    results = [
        {
            "content": entry["content"],
            "source": entry["source"],
            "relevance_score": round(relevance, 4),
        }
        for relevance, entry in top_results
    ]

    return {
        "results": results,
        "query": query,
        "total_results": len(results),
    }
