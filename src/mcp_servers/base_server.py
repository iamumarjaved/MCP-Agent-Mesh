"""Base MCP server with health checks, authentication, and logging.

Provides the abstract foundation for all MCP servers in the Agent Mesh.
Each concrete server inherits from BaseMCPServer and registers its tools
during initialization.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.core.config import settings
from src.core.exceptions import MCPToolError

logger = structlog.get_logger(__name__)


@dataclass
class _CacheEntry:
    """Single entry in the tool result cache."""

    value: dict
    expires_at: float


@dataclass
class ToolRegistration:
    """Metadata and handler for a registered MCP tool."""

    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Coroutine[Any, Any, dict]]


@dataclass
class ToolMetrics:
    """Runtime metrics tracked per tool."""

    call_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_latency_ms / self.call_count

    @property
    def error_rate(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.error_count / self.call_count


class BaseMCPServer(ABC):
    """Abstract base class for all MCP servers in the Agent Mesh.

    Subclasses must call ``super().__init__(name, version)`` and then
    register their tools via :meth:`register_tool`.

    Features
    --------
    * Structured logging via *structlog*
    * Per-tool call counts, error counts, and latency tracking
    * LRU-ish result cache with configurable TTL
    * ``health_check`` endpoint reporting uptime, tool count, and metrics
    * Stdio and SSE transport runners
    """

    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version

        # Core MCP server from the official SDK
        self.mcp_server = Server(name)

        # Tool registry: tool_name -> ToolRegistration
        self._tools: dict[str, ToolRegistration] = {}

        # Per-tool metrics
        self._metrics: dict[str, ToolMetrics] = defaultdict(ToolMetrics)

        # Result cache: cache_key -> _CacheEntry
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_ttl_seconds: int = settings.mcp_cache_ttl_seconds

        # Uptime tracking
        self._started_at: float = time.monotonic()

        self._log = logger.bind(server=name, version=version)
        self._log.info("mcp_server.init")

        # Wire the MCP SDK list_tools / call_tool handlers
        self._register_sdk_handlers()

    # ------------------------------------------------------------------
    # SDK handler wiring
    # ------------------------------------------------------------------

    def _register_sdk_handlers(self) -> None:
        """Attach ``list_tools`` and ``call_tool`` handlers to the SDK server."""

        @self.mcp_server.list_tools()
        async def _list_tools() -> list[Tool]:
            return [
                Tool(
                    name=reg.name,
                    description=reg.description,
                    inputSchema=reg.input_schema,
                )
                for reg in self._tools.values()
            ]

        @self.mcp_server.call_tool()
        async def _call_tool(name: str, arguments: dict | None = None) -> list[TextContent]:
            result = await self.handle_tool_call(name, arguments or {})
            return [TextContent(type="text", text=json.dumps(result, default=str))]

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: Callable[..., Coroutine[Any, Any, dict]],
    ) -> None:
        """Register a tool that this server exposes.

        Parameters
        ----------
        name:
            Unique tool name (e.g. ``query_database``).
        description:
            Human-readable description shown in tool listings.
        input_schema:
            JSON Schema dict describing the tool's input parameters.
        handler:
            Async callable ``(arguments: dict) -> dict`` that implements
            the tool logic.
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered on server '{self.name}'")
        self._tools[name] = ToolRegistration(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )
        self._log.info("tool.registered", tool=name)

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def handle_tool_call(self, name: str, arguments: dict) -> dict:
        """Dispatch a tool call to its registered handler.

        Applies caching, metrics collection, and error handling.

        Returns
        -------
        dict
            The result dict produced by the tool handler.

        Raises
        ------
        MCPToolError
            If the tool is unknown or the handler raises an exception.
        """
        if name not in self._tools:
            raise MCPToolError(
                server=self.name,
                tool=name,
                reason=f"Unknown tool '{name}'",
            )

        metrics = self._metrics[name]
        log = self._log.bind(tool=name)

        # --- cache lookup ---
        cache_key = self._make_cache_key(name, arguments)
        cached = self._cache_get(cache_key)
        if cached is not None:
            log.debug("tool.cache_hit")
            metrics.call_count += 1
            return cached

        # --- execute ---
        t0 = time.perf_counter()
        try:
            result = await self._tools[name].handler(arguments)
        except Exception as exc:
            metrics.call_count += 1
            metrics.error_count += 1
            elapsed_ms = (time.perf_counter() - t0) * 1000
            metrics.total_latency_ms += elapsed_ms
            log.error("tool.error", error=str(exc), elapsed_ms=round(elapsed_ms, 2))
            raise MCPToolError(server=self.name, tool=name, reason=str(exc)) from exc

        elapsed_ms = (time.perf_counter() - t0) * 1000
        metrics.call_count += 1
        metrics.total_latency_ms += elapsed_ms
        log.info("tool.success", elapsed_ms=round(elapsed_ms, 2))

        # --- cache store ---
        self._cache_put(cache_key, result)

        return result

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> dict:
        """Return a health-check payload for monitoring.

        Returns
        -------
        dict
            Contains *status*, *uptime_seconds*, *tool_count*, and
            per-tool metrics.
        """
        uptime = time.monotonic() - self._started_at
        tool_stats = {
            name: {
                "call_count": m.call_count,
                "error_count": m.error_count,
                "avg_latency_ms": round(m.avg_latency_ms, 2),
                "error_rate": round(m.error_rate, 4),
            }
            for name, m in self._metrics.items()
        }
        return {
            "status": "healthy",
            "server": self.name,
            "version": self.version,
            "uptime_seconds": round(uptime, 2),
            "tool_count": len(self._tools),
            "tools": tool_stats,
        }

    # ------------------------------------------------------------------
    # Transport runners
    # ------------------------------------------------------------------

    def run_stdio(self) -> None:
        """Run this MCP server over **stdio** transport (blocking)."""
        self._log.info("transport.stdio.starting")

        async def _run() -> None:
            async with stdio_server() as (read_stream, write_stream):
                await self.mcp_server.run(
                    read_stream,
                    write_stream,
                    self.mcp_server.create_initialization_options(),
                )

        asyncio.run(_run())

    def run_sse(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Run this MCP server over **SSE** transport using Starlette/uvicorn.

        Parameters
        ----------
        host:
            Bind address (default ``0.0.0.0``).
        port:
            Listen port (default ``8000``).
        """
        # Deferred import so SSE dependencies are optional
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route
        import uvicorn

        self._log.info("transport.sse.starting", host=host, port=port)

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self.mcp_server.run(
                    streams[0],
                    streams[1],
                    self.mcp_server.create_initialization_options(),
                )

        async def handle_health(request):
            from starlette.responses import JSONResponse
            return JSONResponse(await self.health_check())

        app = Starlette(
            debug=settings.debug,
            routes=[
                Route("/health", handle_health),
                Mount("/sse", app=sse.get_sse_app()),
                Route("/messages/", handle_sse, methods=["POST"]),
            ],
        )

        uvicorn.run(app, host=host, port=port)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_cache_key(tool_name: str, arguments: dict) -> str:
        raw = json.dumps({"tool": tool_name, "args": arguments}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_get(self, key: str) -> dict | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            return None
        return entry.value

    def _cache_put(self, key: str, value: dict) -> None:
        self._cache[key] = _CacheEntry(
            value=value,
            expires_at=time.monotonic() + self._cache_ttl_seconds,
        )
        # Lazy eviction: prune expired entries when cache grows large
        if len(self._cache) > 1000:
            self._evict_expired()

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._cache.items() if now > v.expires_at]
        for k in expired:
            del self._cache[k]
