"""Eval Guards MCP Server.

Provides data integrity checking, hallucination detection, PII scanning,
statistical validation, quality scoring, and bias detection tools for the
Agent Mesh.  These guards run as part of the Guardian agent's quality
assurance pipeline before outputs are delivered.
"""

from __future__ import annotations

from src.mcp_servers.base_server import BaseMCPServer
from src.mcp_servers.eval_guards.tools.check_data_integrity import check_data_integrity
from src.mcp_servers.eval_guards.tools.detect_hallucination import detect_hallucination
from src.mcp_servers.eval_guards.tools.check_pii import check_pii
from src.mcp_servers.eval_guards.tools.validate_statistics import validate_statistics
from src.mcp_servers.eval_guards.tools.score_quality import score_quality
from src.mcp_servers.eval_guards.tools.check_bias import check_bias


class EvalGuardsServer(BaseMCPServer):
    """MCP server that exposes evaluation and guardrail tools."""

    def __init__(self) -> None:
        super().__init__(name="eval-guards-server", version="1.0.0")
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all eval-guard tools with the MCP server."""

        self.register_tool(
            name="check_data_integrity",
            description=(
                "Check data for completeness, type consistency, and "
                "freshness. Reports issues per field and an overall "
                "integrity score."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Row-oriented dataset to validate.",
                    },
                    "expected_schema": {
                        "type": "object",
                        "description": (
                            "Optional schema mapping field names to expected "
                            "types (e.g. {\"age\": \"int\", \"name\": \"str\"})."
                        ),
                        "default": None,
                    },
                },
                "required": ["data"],
            },
            handler=check_data_integrity,
        )

        self.register_tool(
            name="detect_hallucination",
            description=(
                "Verify numeric claims against source data. Extracts "
                "numbers from claim text and checks whether they appear "
                "in the provided source data."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of textual claims to verify.",
                    },
                    "source_data": {
                        "type": "object",
                        "description": "Authoritative source data to verify claims against.",
                    },
                },
                "required": ["claims", "source_data"],
            },
            handler=detect_hallucination,
        )

        self.register_tool(
            name="check_pii",
            description=(
                "Scan text for personally identifiable information using "
                "regex patterns. Detects emails, phone numbers, SSNs, "
                "credit card numbers, and common name patterns."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to scan for PII.",
                    },
                },
                "required": ["text"],
            },
            handler=check_pii,
        )

        self.register_tool(
            name="validate_statistics",
            description=(
                "Validate statistical claims (mean, sum, percentages, etc.) "
                "by recomputing them from the source data and comparing "
                "against stated values."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "object",
                        "description": (
                            "Statistical claims as a dict. Each key is a "
                            "descriptive label, each value is the claimed "
                            "numeric result."
                        ),
                    },
                    "source_data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Source data rows used to recompute statistics.",
                    },
                },
                "required": ["claims", "source_data"],
            },
            handler=validate_statistics,
        )

        self.register_tool(
            name="score_quality",
            description=(
                "Aggregate individual guard check scores into a single "
                "overall quality score with a verdict: auto_approve, "
                "flag_warnings, reprocess, or escalate."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content that was evaluated.",
                    },
                    "checks": {
                        "type": "object",
                        "description": (
                            "Results from individual guard checks. Keys are "
                            "check names, values are dicts with at least a "
                            "'score' field (float 0-1)."
                        ),
                    },
                },
                "required": ["content", "checks"],
            },
            handler=score_quality,
        )

        self.register_tool(
            name="check_bias",
            description=(
                "Check text and recommendations for one-sided language, "
                "absolute statements, and missing alternative perspectives."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to analyse for bias.",
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of recommendation strings to check.",
                        "default": None,
                    },
                },
                "required": ["text"],
            },
            handler=check_bias,
        )


if __name__ == "__main__":
    server = EvalGuardsServer()
    server.run_stdio()
