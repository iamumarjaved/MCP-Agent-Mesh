"""Abstract base class for all agents in the MCP Agent Mesh.

Every specialist agent inherits from :class:`BaseAgent`, which provides
common infrastructure: structured logging, token tracking, MCP tool
invocation, and agent-card generation.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import structlog

from src.core.config import settings
from src.core.exceptions import MCPToolError
from src.core.models import AgentCard, CostRecord, TokenUsage


class BaseAgent(ABC):
    """Abstract foundation for every agent in the mesh.

    Parameters
    ----------
    agent_id:
        Unique, human-readable identifier (e.g. ``"analytics-v1"``).
    name:
        Display name shown in the dashboard and registry.
    description:
        One-sentence description of the agent's purpose.
    capabilities:
        List of capability tags used for registry discovery.
    mcp_server:
        Name of the MCP server this agent calls (e.g. ``"compute-engine-server"``).
    model:
        Default LLM model identifier for this agent.
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        capabilities: list[str],
        mcp_server: str,
        model: str = "gpt-4o",
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.mcp_server = mcp_server
        self.model = model
        self.logger = structlog.get_logger(agent=agent_id)
        self._total_tokens = TokenUsage()
        self._started_at: float = time.monotonic()

    # ------------------------------------------------------------------
    # Agent card
    # ------------------------------------------------------------------

    def get_agent_card(self) -> AgentCard:
        """Build and return an :class:`AgentCard` from current attributes."""
        return AgentCard(
            agent_id=self.agent_id,
            name=self.name,
            description=self.description,
            capabilities=self.capabilities,
            mcp_server=self.mcp_server,
            version="1.0.0",
            health="healthy",
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's primary task.

        Parameters
        ----------
        task:
            Task-specific parameters (action, sources, analyses, etc.).
        context:
            Shared context from upstream agents (data, intermediate
            results, task metadata).

        Returns
        -------
        dict
            Agent-specific result payload.
        """
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt that configures this agent's LLM persona."""
        ...

    # ------------------------------------------------------------------
    # MCP tool invocation
    # ------------------------------------------------------------------

    async def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool exposed by this agent's MCP server.

        In production this method connects to the MCP server over stdio or
        SSE and invokes the tool.  The current implementation logs the call,
        records placeholder token usage, and returns the arguments as a
        passthrough so that integration tests can verify wiring without a
        live server.

        Parameters
        ----------
        tool_name:
            Name of the tool to invoke (e.g. ``"query_database"``).
        arguments:
            JSON-serialisable argument dict forwarded to the tool handler.

        Returns
        -------
        dict
            The tool result payload.

        Raises
        ------
        MCPToolError
            If the tool call fails for any reason.
        """
        self.logger.info(
            "mcp_tool.call",
            server=self.mcp_server,
            tool=tool_name,
            args_keys=list(arguments.keys()),
        )

        t0 = time.perf_counter()

        try:
            # ----- Placeholder: in production this dispatches via the MCP client -----
            # from mcp import ClientSession
            # async with ClientSession(transport) as session:
            #     result = await session.call_tool(tool_name, arguments)
            result: dict[str, Any] = {
                "status": "success",
                "tool": tool_name,
                "server": self.mcp_server,
                "data": arguments,
            }
            # -------------------------------------------------------------------------

            elapsed_ms = (time.perf_counter() - t0) * 1000

            # Record modest placeholder token usage for cost tracking
            self._track_tokens(input_tokens=50, output_tokens=30)

            self.logger.info(
                "mcp_tool.success",
                server=self.mcp_server,
                tool=tool_name,
                elapsed_ms=round(elapsed_ms, 2),
            )
            return result

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.logger.error(
                "mcp_tool.error",
                server=self.mcp_server,
                tool=tool_name,
                error=str(exc),
                elapsed_ms=round(elapsed_ms, 2),
            )
            raise MCPToolError(
                server=self.mcp_server,
                tool=tool_name,
                reason=str(exc),
            ) from exc

    # ------------------------------------------------------------------
    # Token tracking
    # ------------------------------------------------------------------

    def _track_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate token usage for this agent's lifetime metrics."""
        self._total_tokens.input_tokens += input_tokens
        self._total_tokens.output_tokens += output_tokens
        self.logger.debug(
            "tokens.tracked",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total=self._total_tokens.total,
        )

    @property
    def total_tokens(self) -> TokenUsage:
        """Return the cumulative token usage since agent creation."""
        return self._total_tokens

    @property
    def uptime_seconds(self) -> float:
        """Seconds since the agent was instantiated."""
        return time.monotonic() - self._started_at
