"""Seed sample data for the MCP Agent Mesh development environment.

Creates:
- SQLite database with sample sales data
- CSV files in data/sample/
- JSON benchmark data
"""

from __future__ import annotations

import csv
import json
import os
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "sample"
DB_PATH = PROJECT_ROOT / "data" / "sample_sales.db"

PRODUCTS = [
    "Widget Pro", "Widget Lite", "Gadget X", "Gadget Y",
    "Module Alpha", "Module Beta", "Sensor V1", "Sensor V2",
    "Platform Base", "Platform Premium",
]

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East"]

CUSTOMER_SEGMENTS = ["Enterprise", "SMB", "Startup", "Government", "Education"]

random.seed(42)


# ---------------------------------------------------------------------------
# Generate sales CSV
# ---------------------------------------------------------------------------

def generate_sales_csv(path: Path, num_rows: int = 100) -> None:
    """Generate a CSV file with synthetic Q4 2025 sales data."""
    start_date = date(2025, 10, 1)
    end_date = date(2025, 12, 31)
    date_range = (end_date - start_date).days

    rows: list[dict] = []
    for _ in range(num_rows):
        sale_date = start_date + timedelta(days=random.randint(0, date_range))
        product = random.choice(PRODUCTS)
        region = random.choice(REGIONS)
        units = random.randint(1, 500)
        base_price = random.uniform(50.0, 2000.0)
        discount = round(random.choice([0.0, 0.05, 0.10, 0.15, 0.20]), 2)
        revenue = round(units * base_price * (1 - discount), 2)
        segment = random.choice(CUSTOMER_SEGMENTS)

        rows.append({
            "date": sale_date.isoformat(),
            "product": product,
            "region": region,
            "revenue": revenue,
            "units_sold": units,
            "discount": discount,
            "customer_segment": segment,
        })

    # Sort by date for realism
    rows.sort(key=lambda r: r["date"])

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Created {path} ({num_rows} rows)")


# ---------------------------------------------------------------------------
# Generate company targets CSV
# ---------------------------------------------------------------------------

def generate_targets_csv(path: Path) -> None:
    """Generate quarterly company targets."""
    rows = [
        {"quarter": "Q1 2025", "revenue_target": 5_000_000, "units_target": 12_000, "margin_target": 0.35},
        {"quarter": "Q2 2025", "revenue_target": 5_500_000, "units_target": 13_500, "margin_target": 0.36},
        {"quarter": "Q3 2025", "revenue_target": 6_000_000, "units_target": 14_000, "margin_target": 0.37},
        {"quarter": "Q4 2025", "revenue_target": 7_000_000, "units_target": 16_000, "margin_target": 0.38},
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Created {path} ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Generate industry benchmarks JSON
# ---------------------------------------------------------------------------

def generate_benchmarks_json(path: Path) -> None:
    """Generate industry benchmark reference data."""
    benchmarks = {
        "industry": "Technology / SaaS",
        "period": "2025",
        "source": "Synthetic benchmark data for development",
        "metrics": {
            "revenue_growth_yoy": {
                "p25": 0.08,
                "p50": 0.15,
                "p75": 0.25,
                "top_quartile": 0.30,
                "unit": "percentage",
            },
            "gross_margin": {
                "p25": 0.55,
                "p50": 0.65,
                "p75": 0.75,
                "top_quartile": 0.80,
                "unit": "percentage",
            },
            "net_margin": {
                "p25": 0.05,
                "p50": 0.12,
                "p75": 0.20,
                "top_quartile": 0.25,
                "unit": "percentage",
            },
            "customer_retention": {
                "p25": 0.80,
                "p50": 0.88,
                "p75": 0.93,
                "top_quartile": 0.96,
                "unit": "percentage",
            },
            "customer_acquisition_cost": {
                "p25": 800,
                "p50": 500,
                "p75": 300,
                "top_quartile": 200,
                "unit": "usd",
            },
            "revenue_per_employee": {
                "p25": 150_000,
                "p50": 250_000,
                "p75": 400_000,
                "top_quartile": 500_000,
                "unit": "usd",
            },
            "nps_score": {
                "p25": 20,
                "p50": 40,
                "p75": 60,
                "top_quartile": 75,
                "unit": "score",
            },
        },
        "regional_multipliers": {
            "North America": 1.0,
            "Europe": 0.9,
            "Asia Pacific": 1.1,
            "Latin America": 0.75,
            "Middle East": 0.85,
        },
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(benchmarks, f, indent=2)

    print(f"  Created {path}")


# ---------------------------------------------------------------------------
# Seed SQLite database
# ---------------------------------------------------------------------------

def seed_sqlite(db_path: Path) -> None:
    """Create a SQLite database and populate with sales data."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DB for a clean seed
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date TEXT NOT NULL,
            product TEXT NOT NULL,
            region TEXT NOT NULL,
            revenue REAL NOT NULL,
            units_sold INTEGER NOT NULL,
            discount REAL DEFAULT 0.0,
            customer_segment TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            base_price REAL NOT NULL,
            cost REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            segment TEXT NOT NULL,
            region TEXT NOT NULL,
            lifetime_value REAL DEFAULT 0.0
        )
    """)

    # Populate products
    product_data = [
        ("Widget Pro", "Widgets", 499.99, 150.00),
        ("Widget Lite", "Widgets", 199.99, 60.00),
        ("Gadget X", "Gadgets", 1299.99, 450.00),
        ("Gadget Y", "Gadgets", 899.99, 300.00),
        ("Module Alpha", "Modules", 349.99, 100.00),
        ("Module Beta", "Modules", 249.99, 80.00),
        ("Sensor V1", "Sensors", 79.99, 25.00),
        ("Sensor V2", "Sensors", 129.99, 40.00),
        ("Platform Base", "Platforms", 1999.99, 600.00),
        ("Platform Premium", "Platforms", 2999.99, 900.00),
    ]
    cursor.executemany(
        "INSERT INTO products (name, category, base_price, cost) VALUES (?, ?, ?, ?)",
        product_data,
    )

    # Populate sales (same data as CSV for consistency)
    start_date = date(2025, 10, 1)
    end_date = date(2025, 12, 31)
    date_range = (end_date - start_date).days
    random.seed(42)  # Reset seed for reproducibility

    for _ in range(100):
        sale_date = start_date + timedelta(days=random.randint(0, date_range))
        product = random.choice(PRODUCTS)
        region = random.choice(REGIONS)
        units = random.randint(1, 500)
        base_price = random.uniform(50.0, 2000.0)
        discount = round(random.choice([0.0, 0.05, 0.10, 0.15, 0.20]), 2)
        revenue = round(units * base_price * (1 - discount), 2)
        segment = random.choice(CUSTOMER_SEGMENTS)

        cursor.execute(
            "INSERT INTO sales (sale_date, product, region, revenue, units_sold, discount, customer_segment) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sale_date.isoformat(), product, region, revenue, units, discount, segment),
        )

    # Populate sample customers
    first_names = ["Acme", "TechCorp", "GlobalInc", "DataSystems", "CloudFirst",
                   "NextGen", "SmartSol", "InnoTech", "PrimeSoft", "CoreLogic"]
    for i, name in enumerate(first_names):
        cursor.execute(
            "INSERT INTO customers (name, segment, region, lifetime_value) VALUES (?, ?, ?, ?)",
            (name, CUSTOMER_SEGMENTS[i % len(CUSTOMER_SEGMENTS)],
             REGIONS[i % len(REGIONS)], round(random.uniform(10_000, 500_000), 2)),
        )

    # Create useful indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_region ON sales(region)")

    conn.commit()
    conn.close()

    print(f"  Created SQLite database at {db_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Seeding MCP Agent Mesh sample data...")
    print()

    generate_sales_csv(DATA_DIR / "sales_q4_2025.csv", num_rows=100)
    generate_targets_csv(DATA_DIR / "company_targets.csv")
    generate_benchmarks_json(DATA_DIR / "industry_benchmarks.json")
    seed_sqlite(DB_PATH)

    print()
    print("Done. Sample data is ready in data/sample/")


if __name__ == "__main__":
    main()
