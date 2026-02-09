"""Seed the Qdrant knowledge base with sample document embeddings.

Creates a collection in Qdrant and indexes placeholder vectors that
represent business-domain documents (industry reports, best practices,
glossary entries).  In production these would be real embeddings from
an Azure OpenAI embedding model.

Usage:
    python scripts/seed_knowledge_base.py
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass

random.seed(42)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "knowledge_base"
EMBEDDING_DIM = 1536  # text-embedding-3-small dimension

# ---------------------------------------------------------------------------
# Sample documents
# ---------------------------------------------------------------------------

@dataclass
class Document:
    title: str
    content: str
    category: str
    source: str


SAMPLE_DOCUMENTS: list[Document] = [
    Document(
        title="SaaS Revenue Recognition Best Practices",
        content=(
            "Revenue from SaaS subscriptions should be recognized ratably "
            "over the subscription period. Multi-year contracts require "
            "careful allocation between performance obligations."
        ),
        category="accounting",
        source="internal_policy",
    ),
    Document(
        title="Customer Churn Analysis Framework",
        content=(
            "Effective churn analysis combines cohort analysis, survival "
            "curves, and predictive modeling. Key leading indicators include "
            "declining login frequency, reduced feature usage, and support "
            "ticket escalations."
        ),
        category="analytics",
        source="best_practices",
    ),
    Document(
        title="Q4 2025 Technology Sector Outlook",
        content=(
            "The technology sector is expected to see continued growth in "
            "AI infrastructure spending. Enterprise software companies "
            "with AI-native products are commanding premium multiples. "
            "Key risks include regulatory uncertainty and talent competition."
        ),
        category="market_research",
        source="industry_report",
    ),
    Document(
        title="Sales Pipeline Velocity Metrics",
        content=(
            "Pipeline velocity measures the speed at which deals move "
            "through the sales funnel. Formula: (Number of Opportunities * "
            "Win Rate * Average Deal Size) / Sales Cycle Length. "
            "Top quartile companies achieve velocity above $150K/month."
        ),
        category="sales",
        source="internal_benchmark",
    ),
    Document(
        title="Data Quality Scorecard Methodology",
        content=(
            "Data quality is assessed across six dimensions: completeness, "
            "accuracy, consistency, timeliness, validity, and uniqueness. "
            "Each dimension is scored 0-100 and weighted based on business "
            "criticality to produce an overall DQ score."
        ),
        category="data_governance",
        source="methodology",
    ),
    Document(
        title="Financial Ratio Analysis Guide",
        content=(
            "Key financial ratios for SaaS companies: LTV:CAC ratio "
            "(target > 3:1), Rule of 40 (growth rate + profit margin > 40%), "
            "Magic Number (net new ARR / sales & marketing spend > 0.75), "
            "and Net Revenue Retention (target > 110%)."
        ),
        category="finance",
        source="best_practices",
    ),
    Document(
        title="Anomaly Detection in Business Metrics",
        content=(
            "Statistical process control (SPC) charts, Z-score analysis, "
            "and Isolation Forest algorithms are effective for detecting "
            "anomalies in business KPIs. Combine automated detection with "
            "human review to reduce false positive rates."
        ),
        category="analytics",
        source="methodology",
    ),
    Document(
        title="Competitive Intelligence Framework",
        content=(
            "Systematic competitive analysis should cover: product features, "
            "pricing strategy, market positioning, customer reviews, "
            "financial performance, and technology stack. Update quarterly "
            "and distribute to product, sales, and strategy teams."
        ),
        category="strategy",
        source="internal_policy",
    ),
    Document(
        title="Regional Sales Performance Benchmarks",
        content=(
            "North America typically represents 55-65% of global SaaS "
            "revenue. Europe accounts for 20-25%, with DACH region "
            "outperforming. APAC is the fastest growing at 30%+ YoY, "
            "led by Japan and Australia."
        ),
        category="sales",
        source="industry_report",
    ),
    Document(
        title="Cost Optimization Strategies for Cloud Infrastructure",
        content=(
            "Key strategies: right-sizing instances, reserved capacity "
            "commitments, spot/preemptible instances for batch workloads, "
            "auto-scaling policies, and storage tiering. Target 20-30% "
            "cost reduction from baseline."
        ),
        category="operations",
        source="best_practices",
    ),
]


def _random_embedding(dim: int) -> list[float]:
    """Generate a random unit vector as a placeholder embedding."""
    vec = [random.gauss(0, 1) for _ in range(dim)]
    magnitude = sum(x**2 for x in vec) ** 0.5
    return [x / magnitude for x in vec]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams
    except ImportError:
        print("qdrant-client is not installed. Run: pip install qdrant-client")
        sys.exit(1)

    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")

    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=10)
    except Exception as exc:
        print(f"Failed to connect to Qdrant: {exc}")
        print("Make sure Qdrant is running: docker compose up -d qdrant")
        sys.exit(1)

    # Recreate collection (idempotent seeding)
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in collections:
        client.delete_collection(COLLECTION_NAME)
        print(f"  Deleted existing collection '{COLLECTION_NAME}'")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=EMBEDDING_DIM,
            distance=Distance.COSINE,
        ),
    )
    print(f"  Created collection '{COLLECTION_NAME}' (dim={EMBEDDING_DIM}, cosine)")

    # Index documents
    points = []
    for idx, doc in enumerate(SAMPLE_DOCUMENTS):
        embedding = _random_embedding(EMBEDDING_DIM)
        points.append(
            PointStruct(
                id=idx + 1,
                vector=embedding,
                payload={
                    "title": doc.title,
                    "content": doc.content,
                    "category": doc.category,
                    "source": doc.source,
                },
            )
        )

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"  Indexed {len(points)} documents into '{COLLECTION_NAME}'")

    # Verify
    info = client.get_collection(COLLECTION_NAME)
    print(f"  Collection points count: {info.points_count}")
    print()
    print("Knowledge base seeding complete.")


if __name__ == "__main__":
    main()
