"""Data Access MCP Server.

Exposes five tools for retrieving, profiling, cleaning, and transforming
tabular data:

* **query_database** -- Execute SQL against a demo SQLite database.
* **fetch_csv** -- Load a CSV file from a local path.
* **profile_data** -- Generate a data-quality report.
* **clean_data** -- Apply a cleaning pipeline (dedup, impute, normalize).
* **transform_data** -- Filter, aggregate, sort, or select columns.
"""

from __future__ import annotations

import structlog

from src.core.config import settings
from src.mcp_servers.base_server import BaseMCPServer
from src.mcp_servers.data_access.tools.clean_data import (
    clean_data as _clean_data,
)
from src.mcp_servers.data_access.tools.fetch_csv import (
    fetch_csv as _fetch_csv,
)
from src.mcp_servers.data_access.tools.profile_data import (
    profile_data as _profile_data,
)
from src.mcp_servers.data_access.tools.query_database import (
    query_database as _query_database,
)
from src.mcp_servers.data_access.tools.transform_data import (
    transform_data as _transform_data,
)

logger = structlog.get_logger(__name__)


class DataAccessServer(BaseMCPServer):
    """MCP server that provides data-access tools.

    Registers all five data tools during ``__init__``.  The server can
    then be started with :meth:`run_stdio` or :meth:`run_sse`.
    """

    def __init__(self) -> None:
        super().__init__(name="data-access-server", version=settings.app_version)
        self._register_tools()

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        """Register all data-access tools with their JSON schemas."""

        # ---- query_database ----
        self.register_tool(
            name="query_database",
            description=(
                "Execute a SQL query against a database and return the "
                "result set. The demo environment uses an in-memory SQLite "
                "database seeded with sample customer/order data."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL SELECT statement to execute.",
                    },
                    "database": {
                        "type": "string",
                        "description": "Target database identifier.",
                        "enum": ["sqlite"],
                        "default": "sqlite",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Maximum seconds before the query is aborted.",
                        "default": 30,
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "Maximum number of rows to return.",
                        "default": 10000,
                    },
                },
                "required": ["query"],
            },
            handler=self._handle_query_database,
        )

        # ---- fetch_csv ----
        self.register_tool(
            name="fetch_csv",
            description=(
                "Load a CSV file from a local path and return its "
                "contents as structured records with column metadata."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Absolute or relative path to a CSV file.",
                    },
                    "delimiter": {
                        "type": "string",
                        "description": "Column delimiter character.",
                        "default": ",",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding.",
                        "default": "utf-8",
                    },
                },
                "required": ["source"],
            },
            handler=self._handle_fetch_csv,
        )

        # ---- profile_data ----
        self.register_tool(
            name="profile_data",
            description=(
                "Generate a data-quality profile for a dataset. Reports "
                "null counts, data types, distributions for numeric "
                "columns, unique counts, and an overall quality score."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data_ref": {
                        "type": "string",
                        "description": (
                            "Reference key for the dataset in the context "
                            "store. Alternatively, inline data can be passed "
                            "via the 'data' field."
                        ),
                    },
                    "data": {
                        "type": "array",
                        "description": "Inline list of row dicts to profile.",
                        "items": {"type": "object"},
                    },
                },
            },
            handler=self._handle_profile_data,
        )

        # ---- clean_data ----
        self.register_tool(
            name="clean_data",
            description=(
                "Apply a sequence of cleaning operations to a dataset. "
                "Supported operations: 'dedup' (drop duplicate rows), "
                "'impute' (fill nulls with median/mode), "
                "'normalize' (min-max scale numeric columns)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data_ref": {
                        "type": "string",
                        "description": (
                            "Reference key for the dataset in the context "
                            "store. Alternatively, pass inline data via "
                            "the 'data' field."
                        ),
                    },
                    "data": {
                        "type": "array",
                        "description": "Inline list of row dicts to clean.",
                        "items": {"type": "object"},
                    },
                    "operations": {
                        "type": "array",
                        "description": (
                            "Ordered list of operations to apply. "
                            "Supported: 'dedup', 'impute', 'normalize'."
                        ),
                        "items": {
                            "type": "string",
                            "enum": ["dedup", "impute", "normalize"],
                        },
                    },
                },
                "required": ["operations"],
            },
            handler=self._handle_clean_data,
        )

        # ---- transform_data ----
        self.register_tool(
            name="transform_data",
            description=(
                "Apply a structural transformation to a dataset. "
                "Supported operations: 'filter', 'aggregate', 'sort', "
                "'select'."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data_ref": {
                        "type": "string",
                        "description": (
                            "Reference key for the dataset in the context "
                            "store. Alternatively, pass inline data via "
                            "the 'data' field."
                        ),
                    },
                    "data": {
                        "type": "array",
                        "description": "Inline list of row dicts.",
                        "items": {"type": "object"},
                    },
                    "operation": {
                        "type": "string",
                        "description": "Transformation to apply.",
                        "enum": ["filter", "aggregate", "sort", "select"],
                    },
                    "params": {
                        "type": "object",
                        "description": (
                            "Operation-specific parameters. See tool docs."
                        ),
                    },
                },
                "required": ["operation", "params"],
            },
            handler=self._handle_transform_data,
        )

    # ------------------------------------------------------------------
    # Handler wrappers (unpack arguments -> call tool function)
    # ------------------------------------------------------------------

    async def _handle_query_database(self, arguments: dict) -> dict:
        return await _query_database(
            query=arguments["query"],
            database=arguments.get("database", "sqlite"),
            timeout_seconds=arguments.get("timeout_seconds", 30),
            max_rows=arguments.get("max_rows", 10_000),
        )

    async def _handle_fetch_csv(self, arguments: dict) -> dict:
        return await _fetch_csv(
            source=arguments["source"],
            delimiter=arguments.get("delimiter", ","),
            encoding=arguments.get("encoding", "utf-8"),
        )

    async def _handle_profile_data(self, arguments: dict) -> dict:
        data = self._resolve_data(arguments)
        return await _profile_data(data=data)

    async def _handle_clean_data(self, arguments: dict) -> dict:
        data = self._resolve_data(arguments)
        return await _clean_data(
            data=data,
            operations=arguments["operations"],
        )

    async def _handle_transform_data(self, arguments: dict) -> dict:
        data = self._resolve_data(arguments)
        return await _transform_data(
            data=data,
            operation=arguments["operation"],
            params=arguments.get("params", {}),
        )

    # ------------------------------------------------------------------
    # Data resolution helper
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_data(arguments: dict) -> list[dict]:
        """Resolve inline ``data`` or ``data_ref`` from arguments.

        In a full production system ``data_ref`` would look up a dataset
        from a shared context store (e.g. Redis).  For now, inline ``data``
        is the primary path; ``data_ref`` raises a clear error directing
        callers to pass inline data instead.
        """
        if "data" in arguments and arguments["data"]:
            return arguments["data"]

        if "data_ref" in arguments and arguments["data_ref"]:
            # Placeholder: in production, resolve from context store
            raise NotImplementedError(
                f"Context-store lookup for data_ref='{arguments['data_ref']}' "
                "is not yet implemented. Pass inline 'data' instead."
            )

        raise ValueError(
            "Either 'data' (inline records) or 'data_ref' (context store key) "
            "must be provided."
        )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    """CLI entry point -- runs the server over stdio."""
    server = DataAccessServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
