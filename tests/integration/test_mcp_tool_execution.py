"""Integration tests for end-to-end MCP tool execution.

Tests the full tool dispatch pipeline: registration -> invocation ->
caching -> metrics, using the base server infrastructure.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.core.exceptions import MCPToolError
from src.mcp_servers.base_server import BaseMCPServer


# ---------------------------------------------------------------------------
# Concrete test server
# ---------------------------------------------------------------------------

class TestMCPServer(BaseMCPServer):
    """Minimal MCP server for integration testing."""

    def __init__(self) -> None:
        super().__init__(name="test-server", version="1.0.0")

        self.register_tool(
            name="echo",
            description="Echo back the input arguments",
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            handler=self._handle_echo,
        )

        self.register_tool(
            name="add",
            description="Add two numbers",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
            handler=self._handle_add,
        )

        self.register_tool(
            name="fail",
            description="Always raises an error",
            input_schema={"type": "object", "properties": {}},
            handler=self._handle_fail,
        )

    async def _handle_echo(self, arguments: dict) -> dict:
        return {"echoed": arguments.get("message", "")}

    async def _handle_add(self, arguments: dict) -> dict:
        return {"result": arguments["a"] + arguments["b"]}

    async def _handle_fail(self, arguments: dict) -> dict:
        raise RuntimeError("Intentional failure for testing")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def test_server() -> TestMCPServer:
    return TestMCPServer()


@pytest.mark.asyncio
class TestMCPToolExecution:

    async def test_echo_tool(self, test_server: TestMCPServer) -> None:
        result = await test_server.handle_tool_call("echo", {"message": "hello"})
        assert result == {"echoed": "hello"}

    async def test_add_tool(self, test_server: TestMCPServer) -> None:
        result = await test_server.handle_tool_call("add", {"a": 10, "b": 20})
        assert result == {"result": 30}

    async def test_unknown_tool_raises(self, test_server: TestMCPServer) -> None:
        with pytest.raises(MCPToolError, match="Unknown tool"):
            await test_server.handle_tool_call("nonexistent", {})

    async def test_tool_error_propagation(self, test_server: TestMCPServer) -> None:
        with pytest.raises(MCPToolError, match="Intentional failure"):
            await test_server.handle_tool_call("fail", {})

    async def test_metrics_tracking(self, test_server: TestMCPServer) -> None:
        await test_server.handle_tool_call("echo", {"message": "a"})
        await test_server.handle_tool_call("echo", {"message": "b"})

        metrics = test_server._metrics["echo"]
        assert metrics.call_count == 2
        assert metrics.error_count == 0
        assert metrics.avg_latency_ms > 0

    async def test_error_metrics(self, test_server: TestMCPServer) -> None:
        with pytest.raises(MCPToolError):
            await test_server.handle_tool_call("fail", {})

        metrics = test_server._metrics["fail"]
        assert metrics.call_count == 1
        assert metrics.error_count == 1
        assert metrics.error_rate == 1.0

    async def test_cache_hit(self, test_server: TestMCPServer) -> None:
        """Same arguments should return cached result."""
        result1 = await test_server.handle_tool_call("add", {"a": 5, "b": 3})
        result2 = await test_server.handle_tool_call("add", {"a": 5, "b": 3})

        assert result1 == result2
        # Second call should be a cache hit (call_count is still 2 because
        # cache hits are counted)
        metrics = test_server._metrics["add"]
        assert metrics.call_count == 2

    async def test_cache_miss_different_args(self, test_server: TestMCPServer) -> None:
        result1 = await test_server.handle_tool_call("add", {"a": 1, "b": 2})
        result2 = await test_server.handle_tool_call("add", {"a": 3, "b": 4})

        assert result1 != result2

    async def test_health_check(self, test_server: TestMCPServer) -> None:
        health = await test_server.health_check()
        assert health["status"] == "healthy"
        assert health["server"] == "test-server"
        assert health["version"] == "1.0.0"
        assert health["tool_count"] == 3

    async def test_health_check_after_calls(self, test_server: TestMCPServer) -> None:
        await test_server.handle_tool_call("echo", {"message": "x"})

        health = await test_server.health_check()
        assert "echo" in health["tools"]
        assert health["tools"]["echo"]["call_count"] == 1

    async def test_duplicate_tool_registration_raises(self) -> None:
        server = TestMCPServer()
        with pytest.raises(ValueError, match="already registered"):
            server.register_tool(
                name="echo",
                description="duplicate",
                input_schema={},
                handler=server._handle_echo,
            )
