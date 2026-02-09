"""Tool: fetch_csv -- Load a CSV file from a local path and return its contents."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# Maximum file size we are willing to load (100 MB).
_MAX_FILE_SIZE_BYTES: int = 100 * 1024 * 1024


async def fetch_csv(
    source: str,
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Load a CSV file and return its contents as a list of records.

    Parameters
    ----------
    source:
        Absolute or relative path to a CSV file on disk.
    delimiter:
        Column delimiter (default ``","``).
    encoding:
        File encoding (default ``"utf-8"``).

    Returns
    -------
    dict
        ``data`` (list of row dicts), ``columns``, ``row_count``,
        ``dtypes`` (column name -> dtype string).
    """
    log = logger.bind(tool="fetch_csv", source=source)
    log.info("fetch_csv.start")

    # --- validate path ---
    resolved = os.path.abspath(source)
    if not os.path.isfile(resolved):
        raise FileNotFoundError(f"CSV file not found: {resolved}")

    file_size = os.path.getsize(resolved)
    if file_size > _MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds "
            f"limit of {_MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB"
        )

    # --- load in executor to avoid blocking the event loop ---
    def _load() -> pd.DataFrame:
        return pd.read_csv(resolved, delimiter=delimiter, encoding=encoding)

    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(None, _load)

    records = df.to_dict(orient="records")
    columns = list(df.columns)
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

    log.info("fetch_csv.done", row_count=len(records), columns=len(columns))

    return {
        "data": records,
        "columns": columns,
        "row_count": len(records),
        "dtypes": dtypes,
    }
