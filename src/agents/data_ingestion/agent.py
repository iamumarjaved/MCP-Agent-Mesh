"""Data Ingestion Agent.

Connects to databases, files, and APIs through the Data Access MCP server
to ingest, profile, clean, and prepare data for downstream analysis.
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.data_ingestion.prompts import DATA_INGESTION_SYSTEM_PROMPT


class DataIngestionAgent(BaseAgent):
    """Specialist agent for data acquisition and preparation."""

    def __init__(self) -> None:
        super().__init__(
            agent_id="data-ingestion-v1",
            name="Data Ingestion Agent",
            description=(
                "Connects to databases, files, and APIs to ingest, "
                "clean, and prepare data for analysis"
            ),
            capabilities=[
                "sql_query",
                "file_ingestion",
                "data_cleaning",
                "data_profiling",
            ],
            mcp_server="data-access-server",
            model="gpt-4o-mini",
        )

    def get_system_prompt(self) -> str:
        return DATA_INGESTION_SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Ingest data from one or more sources and return a cleaned dataset.

        Supported task parameters:
            action          -- ``"ingest_and_clean"`` (default),
                               ``"profile_only"``, ``"query"``.
            sources         -- List of source descriptors (``{"type": "csv",
                               "path": "..."}`` or ``{"type": "sql", "query":
                               "..."}``).
            filters         -- Optional column-level filters to apply after
                               ingestion (``{"column": "region", "op": "==",
                               "value": "NA"}``).
            columns         -- Optional list of columns to select.
            clean           -- Whether to run the cleaning pipeline
                               (default ``True``).
        """
        action: str = task.get("action", "ingest_and_clean")
        sources: list[dict[str, Any]] = task.get("sources", [])
        filters: dict[str, Any] = task.get("filters", {})
        selected_columns: list[str] | None = task.get("columns")
        should_clean: bool = task.get("clean", True)

        self.logger.info(
            "data_ingestion.execute",
            action=action,
            source_count=len(sources),
        )

        # ------ Step 1: Fetch data from each source ------
        all_records: list[dict[str, Any]] = []
        all_columns: list[str] = []
        source_metadata: list[dict[str, Any]] = []

        if sources:
            for src in sources:
                fetched = await self._fetch_source(src)
                all_records.extend(fetched.get("data", []))
                all_columns = fetched.get("columns", all_columns)
                source_metadata.append({
                    "source": src,
                    "row_count": fetched.get("row_count", 0),
                    "columns": fetched.get("columns", []),
                })
        else:
            # No explicit sources -- try a default query from context
            default_result = await self.call_mcp_tool(
                "query_database",
                {"query": "SELECT * FROM orders LIMIT 1000", "database": "sqlite"},
            )
            data_payload = default_result.get("data", default_result)
            if isinstance(data_payload, dict):
                all_records = data_payload.get("data", [])
                all_columns = data_payload.get("columns", [])
            else:
                all_records = data_payload if isinstance(data_payload, list) else []

        raw_row_count = len(all_records)

        # ------ Step 2: Profile data quality ------
        profile = self._profile_data(all_records, all_columns)

        if action == "profile_only":
            return {
                "action": "profile_only",
                "raw_row_count": raw_row_count,
                "raw_column_count": len(all_columns),
                "profile": profile,
                "sources": source_metadata,
            }

        # ------ Step 3: Clean data if requested ------
        cleaned_records = all_records
        cleaning_actions: dict[str, str] = {}

        if should_clean and all_records:
            cleaned_records, cleaning_actions = self._clean_data(
                all_records, profile
            )

        # ------ Step 4: Apply column selection ------
        if selected_columns and cleaned_records:
            cleaned_records = [
                {k: v for k, v in row.items() if k in selected_columns}
                for row in cleaned_records
            ]
            all_columns = [c for c in all_columns if c in selected_columns]

        # ------ Step 5: Apply filters ------
        if filters and cleaned_records:
            cleaned_records = self._apply_filters(cleaned_records, filters)

        self.logger.info(
            "data_ingestion.complete",
            raw_rows=raw_row_count,
            cleaned_rows=len(cleaned_records),
            columns=len(all_columns),
        )

        return {
            "action": action,
            "data": cleaned_records,
            "columns": all_columns,
            "raw_row_count": raw_row_count,
            "cleaned_row_count": len(cleaned_records),
            "profile": profile,
            "cleaning_actions": cleaning_actions,
            "quality_issues": profile.get("issues", []),
            "sources": source_metadata,
        }

    # ------------------------------------------------------------------
    # Source fetching
    # ------------------------------------------------------------------

    async def _fetch_source(self, source: dict[str, Any]) -> dict[str, Any]:
        """Fetch data from a single source descriptor."""
        src_type = source.get("type", "csv")

        if src_type == "csv":
            return await self.call_mcp_tool(
                "fetch_csv",
                {
                    "source": source.get("path", ""),
                    "delimiter": source.get("delimiter", ","),
                    "encoding": source.get("encoding", "utf-8"),
                },
            )

        if src_type == "sql":
            return await self.call_mcp_tool(
                "query_database",
                {
                    "query": source.get("query", ""),
                    "database": source.get("database", "sqlite"),
                    "timeout_seconds": source.get("timeout_seconds", 30),
                    "max_rows": source.get("max_rows", 10_000),
                },
            )

        self.logger.warning("data_ingestion.unknown_source_type", src_type=src_type)
        return {"data": [], "columns": [], "row_count": 0}

    # ------------------------------------------------------------------
    # Profiling
    # ------------------------------------------------------------------

    @staticmethod
    def _profile_data(
        records: list[dict[str, Any]],
        columns: list[str],
    ) -> dict[str, Any]:
        """Generate a lightweight data-quality profile.

        Returns column-level stats and a list of detected issues.
        """
        if not records:
            return {"column_profiles": {}, "issues": [], "row_count": 0}

        # Derive columns from the first record if not provided
        if not columns:
            columns = list(records[0].keys())

        row_count = len(records)
        issues: list[str] = []
        column_profiles: dict[str, dict[str, Any]] = {}

        for col in columns:
            values = [row.get(col) for row in records]
            non_null = [v for v in values if v is not None and v != ""]
            null_count = row_count - len(non_null)
            null_pct = (null_count / row_count * 100) if row_count > 0 else 0.0

            # Determine dominant type
            type_counts: dict[str, int] = {}
            for v in non_null:
                t = type(v).__name__
                type_counts[t] = type_counts.get(t, 0) + 1

            dominant_type = max(type_counts, key=type_counts.get) if type_counts else "unknown"

            profile: dict[str, Any] = {
                "non_null_count": len(non_null),
                "null_count": null_count,
                "null_pct": round(null_pct, 2),
                "dominant_type": dominant_type,
                "unique_count": len(set(str(v) for v in non_null)),
            }

            # Numeric stats
            numeric_vals: list[float] = []
            for v in non_null:
                try:
                    numeric_vals.append(float(v))
                except (TypeError, ValueError):
                    pass

            if numeric_vals:
                sorted_nums = sorted(numeric_vals)
                profile["min"] = sorted_nums[0]
                profile["max"] = sorted_nums[-1]
                profile["mean"] = sum(numeric_vals) / len(numeric_vals)
                mid = len(sorted_nums) // 2
                profile["median"] = (
                    sorted_nums[mid]
                    if len(sorted_nums) % 2 == 1
                    else (sorted_nums[mid - 1] + sorted_nums[mid]) / 2
                )

            column_profiles[col] = profile

            # Flag issues
            if null_pct > 5.0:
                issues.append(
                    f"Column '{col}' has {null_pct:.1f}% missing values "
                    f"({null_count}/{row_count})"
                )

            if len(type_counts) > 1:
                issues.append(
                    f"Column '{col}' has mixed types: {type_counts}"
                )

        return {
            "column_profiles": column_profiles,
            "issues": issues,
            "row_count": row_count,
            "column_count": len(columns),
        }

    # ------------------------------------------------------------------
    # Cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_data(
        records: list[dict[str, Any]],
        profile: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Apply basic cleaning heuristics and return (cleaned_records, actions).

        Cleaning rules:
        - Columns with > 50 % nulls are dropped.
        - Numeric columns with <= 50 % nulls are filled with the median.
        - Categorical columns with <= 50 % nulls are filled with the mode.
        - Duplicate rows are removed.
        """
        if not records:
            return records, {}

        col_profiles: dict[str, dict[str, Any]] = profile.get("column_profiles", {})
        actions: dict[str, str] = {}

        # Identify columns to drop
        drop_cols: set[str] = set()
        fill_rules: dict[str, Any] = {}

        for col, cp in col_profiles.items():
            null_pct = cp.get("null_pct", 0.0)
            if null_pct > 50.0:
                drop_cols.add(col)
                actions[col] = "drop"
            elif null_pct > 0.0:
                if "median" in cp:
                    fill_rules[col] = cp["median"]
                    actions[col] = "fill_median"
                else:
                    # Categorical: fill with the most common value
                    non_null = [
                        row.get(col) for row in records
                        if row.get(col) is not None and row.get(col) != ""
                    ]
                    if non_null:
                        from collections import Counter
                        mode = Counter(non_null).most_common(1)[0][0]
                        fill_rules[col] = mode
                        actions[col] = "fill_mode"

        # Apply cleaning
        cleaned: list[dict[str, Any]] = []
        seen: set[str] = set()

        for row in records:
            # Drop columns
            new_row = {k: v for k, v in row.items() if k not in drop_cols}

            # Fill missing values
            for col, fill_val in fill_rules.items():
                if col in new_row and (new_row[col] is None or new_row[col] == ""):
                    new_row[col] = fill_val

            # Deduplicate
            row_key = str(sorted(new_row.items()))
            if row_key not in seen:
                seen.add(row_key)
                cleaned.append(new_row)

        return cleaned, actions

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_filters(
        records: list[dict[str, Any]],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Apply column-level filters to a list of records.

        ``filters`` may be a single filter dict or a list of filter dicts.
        Each filter dict must have ``column``, ``op``, and ``value``.

        Supported operators: ``==``, ``!=``, ``>``, ``<``, ``>=``, ``<=``,
        ``in``, ``not_in``, ``contains``.
        """
        if isinstance(filters, dict) and "column" in filters:
            filter_list: list[dict[str, Any]] = [filters]
        elif isinstance(filters, list):
            filter_list = filters
        else:
            return records

        for f in filter_list:
            col = f.get("column", "")
            op = f.get("op", "==")
            val = f.get("value")

            def _match(row: dict[str, Any]) -> bool:
                rv = row.get(col)
                if rv is None:
                    return False
                if op == "==":
                    return rv == val
                if op == "!=":
                    return rv != val
                if op == ">":
                    return rv > val
                if op == "<":
                    return rv < val
                if op == ">=":
                    return rv >= val
                if op == "<=":
                    return rv <= val
                if op == "in":
                    return rv in (val if isinstance(val, (list, set)) else [val])
                if op == "not_in":
                    return rv not in (val if isinstance(val, (list, set)) else [val])
                if op == "contains":
                    return str(val) in str(rv)
                return True

            records = [row for row in records if _match(row)]

        return records
