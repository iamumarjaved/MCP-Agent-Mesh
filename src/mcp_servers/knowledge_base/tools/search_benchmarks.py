"""Industry benchmark lookup tool.

Contains a built-in dataset of common business metrics across industry
verticals.  Returns benchmark values and percentile ranges for a
requested metric/industry combination.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Built-in benchmark dataset
# ---------------------------------------------------------------------------

_BENCHMARKS: dict[str, dict[str, dict[str, Any]]] = {
    "technology": {
        "revenue_growth": {
            "benchmark_value": 15.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 8.0,
                "p50": 15.0,
                "p75": 25.0,
                "p90": 40.0,
            },
            "source": "Industry Benchmark Report 2024 - Technology Sector",
        },
        "gross_margin": {
            "benchmark_value": 65.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 50.0,
                "p50": 65.0,
                "p75": 75.0,
                "p90": 82.0,
            },
            "source": "SaaS Metrics Benchmark Study 2024",
        },
        "churn_rate": {
            "benchmark_value": 5.0,
            "unit": "percent_monthly",
            "percentile_ranges": {
                "p25": 8.0,
                "p50": 5.0,
                "p75": 3.0,
                "p90": 1.5,
            },
            "source": "SaaS Retention Benchmarks 2024",
        },
        "net_revenue_retention": {
            "benchmark_value": 110.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 95.0,
                "p50": 110.0,
                "p75": 125.0,
                "p90": 140.0,
            },
            "source": "SaaS Metrics Benchmark Study 2024",
        },
        "cac_payback_months": {
            "benchmark_value": 18.0,
            "unit": "months",
            "percentile_ranges": {
                "p25": 24.0,
                "p50": 18.0,
                "p75": 12.0,
                "p90": 6.0,
            },
            "source": "Unit Economics Benchmark Report 2024",
        },
        "ltv_cac_ratio": {
            "benchmark_value": 3.0,
            "unit": "ratio",
            "percentile_ranges": {
                "p25": 1.5,
                "p50": 3.0,
                "p75": 5.0,
                "p90": 8.0,
            },
            "source": "Unit Economics Benchmark Report 2024",
        },
        "employee_satisfaction": {
            "benchmark_value": 4.0,
            "unit": "score_out_of_5",
            "percentile_ranges": {
                "p25": 3.5,
                "p50": 4.0,
                "p75": 4.3,
                "p90": 4.6,
            },
            "source": "Tech Industry HR Benchmarks 2024",
        },
        "deployment_frequency": {
            "benchmark_value": 10.0,
            "unit": "per_week",
            "percentile_ranges": {
                "p25": 2.0,
                "p50": 10.0,
                "p75": 30.0,
                "p90": 100.0,
            },
            "source": "DORA Metrics Benchmark 2024",
        },
    },
    "healthcare": {
        "revenue_growth": {
            "benchmark_value": 8.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 3.0,
                "p50": 8.0,
                "p75": 14.0,
                "p90": 22.0,
            },
            "source": "Healthcare Industry Financial Benchmarks 2024",
        },
        "gross_margin": {
            "benchmark_value": 45.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 30.0,
                "p50": 45.0,
                "p75": 55.0,
                "p90": 65.0,
            },
            "source": "Healthcare Industry Financial Benchmarks 2024",
        },
        "churn_rate": {
            "benchmark_value": 3.0,
            "unit": "percent_monthly",
            "percentile_ranges": {
                "p25": 6.0,
                "p50": 3.0,
                "p75": 1.5,
                "p90": 0.8,
            },
            "source": "Healthcare SaaS Retention Report 2024",
        },
        "employee_satisfaction": {
            "benchmark_value": 3.8,
            "unit": "score_out_of_5",
            "percentile_ranges": {
                "p25": 3.2,
                "p50": 3.8,
                "p75": 4.2,
                "p90": 4.5,
            },
            "source": "Healthcare HR Analytics Report 2024",
        },
    },
    "financial_services": {
        "revenue_growth": {
            "benchmark_value": 10.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 4.0,
                "p50": 10.0,
                "p75": 18.0,
                "p90": 28.0,
            },
            "source": "Financial Services Industry Benchmarks 2024",
        },
        "gross_margin": {
            "benchmark_value": 55.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 40.0,
                "p50": 55.0,
                "p75": 65.0,
                "p90": 72.0,
            },
            "source": "Financial Services Industry Benchmarks 2024",
        },
        "churn_rate": {
            "benchmark_value": 4.0,
            "unit": "percent_monthly",
            "percentile_ranges": {
                "p25": 7.0,
                "p50": 4.0,
                "p75": 2.5,
                "p90": 1.2,
            },
            "source": "FinTech Retention Benchmarks 2024",
        },
        "net_revenue_retention": {
            "benchmark_value": 105.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 92.0,
                "p50": 105.0,
                "p75": 115.0,
                "p90": 130.0,
            },
            "source": "Financial Services SaaS Metrics 2024",
        },
    },
    "retail": {
        "revenue_growth": {
            "benchmark_value": 6.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 2.0,
                "p50": 6.0,
                "p75": 12.0,
                "p90": 20.0,
            },
            "source": "Retail Industry Performance Report 2024",
        },
        "gross_margin": {
            "benchmark_value": 35.0,
            "unit": "percent",
            "percentile_ranges": {
                "p25": 22.0,
                "p50": 35.0,
                "p75": 48.0,
                "p90": 58.0,
            },
            "source": "Retail Industry Performance Report 2024",
        },
        "churn_rate": {
            "benchmark_value": 6.0,
            "unit": "percent_monthly",
            "percentile_ranges": {
                "p25": 10.0,
                "p50": 6.0,
                "p75": 3.5,
                "p90": 2.0,
            },
            "source": "E-Commerce Retention Benchmarks 2024",
        },
    },
}


async def search_benchmarks(arguments: dict) -> dict:
    """Look up industry benchmarks for a given metric.

    Parameters (via *arguments* dict)
    ----------------------------------
    metric : str
        Business metric identifier (e.g. ``"revenue_growth"``).
    industry : str, default ``"technology"``
        Industry vertical to look up.

    Returns
    -------
    dict
        Contains ``metric``, ``industry``, ``benchmark_value``,
        ``percentile_ranges``, and ``source``.  If the metric or industry
        is not found, ``benchmark_value`` is ``None`` and a descriptive
        ``message`` is included.
    """
    metric: str = arguments["metric"]
    industry: str = arguments.get("industry", "technology").lower()

    industry_data = _BENCHMARKS.get(industry)
    if industry_data is None:
        return {
            "metric": metric,
            "industry": industry,
            "benchmark_value": None,
            "percentile_ranges": {},
            "source": None,
            "available_industries": sorted(_BENCHMARKS.keys()),
            "message": f"Industry '{industry}' not found in benchmark dataset.",
        }

    metric_data = industry_data.get(metric.lower())
    if metric_data is None:
        return {
            "metric": metric,
            "industry": industry,
            "benchmark_value": None,
            "percentile_ranges": {},
            "source": None,
            "available_metrics": sorted(industry_data.keys()),
            "message": f"Metric '{metric}' not found for industry '{industry}'.",
        }

    return {
        "metric": metric,
        "industry": industry,
        "benchmark_value": metric_data["benchmark_value"],
        "unit": metric_data.get("unit", ""),
        "percentile_ranges": metric_data["percentile_ranges"],
        "source": metric_data["source"],
    }
