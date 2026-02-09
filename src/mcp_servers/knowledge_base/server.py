"""Knowledge Base MCP Server.

Provides RAG-style retrieval, benchmark lookup, and narrative generation
tools for the Agent Mesh. In production the retrieval tool queries Qdrant;
for local development it falls back to keyword matching against an
in-memory knowledge base.
"""

from __future__ import annotations

from src.mcp_servers.base_server import BaseMCPServer
from src.mcp_servers.knowledge_base.tools.retrieve_context import retrieve_context
from src.mcp_servers.knowledge_base.tools.search_benchmarks import search_benchmarks
from src.mcp_servers.knowledge_base.tools.generate_narrative import generate_narrative


class KnowledgeBaseServer(BaseMCPServer):
    """MCP server that exposes knowledge retrieval and narrative tools."""

    def __init__(self) -> None:
        super().__init__(name="knowledge-base-server", version="1.0.0")
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all knowledge-base tools with the MCP server."""

        self.register_tool(
            name="retrieve_context",
            description=(
                "Retrieve relevant context passages for a query using "
                "keyword matching (demo) or vector search (production). "
                "Returns ranked results with relevance scores."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to retrieve context for.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                        "default": 5,
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of source names to restrict search to.",
                        "default": None,
                    },
                },
                "required": ["query"],
            },
            handler=retrieve_context,
        )

        self.register_tool(
            name="search_benchmarks",
            description=(
                "Look up industry benchmark data for a given business metric. "
                "Returns benchmark values and percentile ranges."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "description": "The business metric to look up (e.g. 'revenue_growth', 'churn_rate').",
                    },
                    "industry": {
                        "type": "string",
                        "description": "Industry vertical for the benchmark.",
                        "default": "technology",
                    },
                },
                "required": ["metric"],
            },
            handler=search_benchmarks,
        )

        self.register_tool(
            name="generate_narrative",
            description=(
                "Transform structured analytical findings into a formatted "
                "business narrative with sections, key points, and optional "
                "recommendations. This is a template-based formatter."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "object",
                        "description": "Structured analytical findings to narrate.",
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": ["executive", "detailed", "technical"],
                        "description": "Level of detail for the narrative.",
                        "default": "executive",
                    },
                    "include_recommendations": {
                        "type": "boolean",
                        "description": "Whether to include a recommendations section.",
                        "default": True,
                    },
                },
                "required": ["findings"],
            },
            handler=generate_narrative,
        )


if __name__ == "__main__":
    server = KnowledgeBaseServer()
    server.run_stdio()
