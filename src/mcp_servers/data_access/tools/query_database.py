"""Tool: query_database -- Execute SQL queries against a database.

For demonstration purposes this uses an in-memory SQLite database seeded
with sample data.  In production the ``database`` parameter would route to
a connection pool backed by Postgres, Snowflake, etc.
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
import time
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL injection guard (basic heuristic -- not a substitute for parameterised
# queries, but useful as a first line of defence in a demo tool).
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r";\s*(DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b", re.IGNORECASE),
    re.compile(r"--\s*$", re.MULTILINE),
    re.compile(r"/\*.*\*/", re.DOTALL),
    re.compile(r"\bUNION\s+ALL\s+SELECT\b", re.IGNORECASE),
    re.compile(r"\bINTO\s+OUTFILE\b", re.IGNORECASE),
    re.compile(r"\bLOAD_FILE\b", re.IGNORECASE),
]


def _validate_query(query: str) -> None:
    """Raise ``ValueError`` if the query matches known injection patterns."""
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(query):
            raise ValueError(
                f"Query rejected: matches dangerous pattern '{pattern.pattern}'"
            )


# ---------------------------------------------------------------------------
# Demo database seed
# ---------------------------------------------------------------------------

def _seed_demo_db(conn: sqlite3.Connection) -> None:
    """Create a small set of sample tables for demo queries."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            region TEXT,
            signup_date TEXT
        );
        INSERT OR IGNORE INTO customers VALUES
            (1, 'Alice',   'alice@example.com',   'NA',   '2024-01-15'),
            (2, 'Bob',     'bob@example.com',     'EU',   '2024-02-20'),
            (3, 'Charlie', 'charlie@example.com', 'APAC', '2024-03-10'),
            (4, 'Diana',   'diana@example.com',   'NA',   '2024-04-05'),
            (5, 'Eve',     'eve@example.com',     'EU',   '2024-05-22');

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount REAL,
            status TEXT,
            created_at TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
        INSERT OR IGNORE INTO orders VALUES
            (1, 1, 120.50, 'completed', '2024-06-01'),
            (2, 2,  75.00, 'completed', '2024-06-02'),
            (3, 1, 200.00, 'pending',   '2024-06-03'),
            (4, 3,  50.00, 'completed', '2024-06-04'),
            (5, 4, 310.25, 'cancelled', '2024-06-05'),
            (6, 5,  99.99, 'completed', '2024-06-06'),
            (7, 2, 149.99, 'pending',   '2024-06-07');
        """
    )


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------

async def query_database(
    query: str,
    database: str = "sqlite",
    timeout_seconds: int = 30,
    max_rows: int = 10_000,
) -> dict[str, Any]:
    """Execute a SQL query and return the results.

    Parameters
    ----------
    query:
        SQL SELECT statement to execute.
    database:
        Target database identifier. Currently only ``"sqlite"`` (in-memory
        demo) is supported.
    timeout_seconds:
        Maximum wall-clock seconds before the query is aborted.
    max_rows:
        Hard cap on the number of rows returned.

    Returns
    -------
    dict
        ``data`` (list of row dicts), ``row_count``, ``columns``,
        ``execution_time_ms``.
    """
    log = logger.bind(tool="query_database", database=database)
    log.info("query_database.start", query_preview=query[:120])

    # --- validation ---
    _validate_query(query)

    if database != "sqlite":
        raise ValueError(f"Unsupported database: {database!r}. Use 'sqlite' for demo.")

    # --- execute with timeout ---
    t0 = time.perf_counter()

    def _run_query() -> pd.DataFrame:
        conn = sqlite3.connect(":memory:")
        try:
            _seed_demo_db(conn)
            df = pd.read_sql_query(query, conn)
            return df.head(max_rows)
        finally:
            conn.close()

    loop = asyncio.get_running_loop()
    try:
        df = await asyncio.wait_for(
            loop.run_in_executor(None, _run_query),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        log.warning("query_database.timeout", timeout_seconds=timeout_seconds)
        raise TimeoutError(
            f"Query exceeded timeout of {timeout_seconds}s"
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    records = df.to_dict(orient="records")
    columns = list(df.columns)

    log.info(
        "query_database.done",
        row_count=len(records),
        elapsed_ms=round(elapsed_ms, 2),
    )

    return {
        "data": records,
        "row_count": len(records),
        "columns": columns,
        "execution_time_ms": round(elapsed_ms, 2),
    }
