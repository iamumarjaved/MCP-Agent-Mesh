"""Custom exception hierarchy for MCP Agent Mesh."""


class AgentMeshError(Exception):
    """Base exception for all Agent Mesh errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class AgentTimeoutError(AgentMeshError):
    """Raised when an agent exceeds its configured timeout."""

    def __init__(self, agent_id: str, timeout_seconds: float):
        super().__init__(
            f"Agent '{agent_id}' timed out after {timeout_seconds}s",
            details={"agent_id": agent_id, "timeout_seconds": timeout_seconds},
        )


class MCPToolError(AgentMeshError):
    """Raised when an MCP tool call fails."""

    def __init__(self, server: str, tool: str, reason: str):
        super().__init__(
            f"MCP tool '{server}.{tool}' failed: {reason}",
            details={"server": server, "tool": tool, "reason": reason},
        )


class BudgetExceededError(AgentMeshError):
    """Raised when a task exceeds its cost budget."""

    def __init__(self, task_id: str, spent: float, budget: float):
        super().__init__(
            f"Task '{task_id}' exceeded budget: ${spent:.4f} / ${budget:.4f}",
            details={"task_id": task_id, "spent": spent, "budget": budget},
        )


class GuardianRejectionError(AgentMeshError):
    """Raised when the Guardian agent rejects an output."""

    def __init__(self, step_id: str, score: float, reasons: list[str]):
        super().__init__(
            f"Guardian rejected step '{step_id}' with score {score:.2f}",
            details={"step_id": step_id, "score": score, "reasons": reasons},
        )


class WorkflowError(AgentMeshError):
    """Raised when a workflow definition is invalid or execution fails."""


class AgentRegistrationError(AgentMeshError):
    """Raised when agent registration or discovery fails."""


class ContextStoreError(AgentMeshError):
    """Raised when shared context read/write fails."""


class HITLTimeoutError(AgentMeshError):
    """Raised when a human-in-the-loop approval times out."""

    def __init__(self, task_id: str, step_id: str, timeout_minutes: int = 30):
        super().__init__(
            f"HITL approval timed out for task '{task_id}' step '{step_id}' "
            f"after {timeout_minutes} minutes",
            details={
                "task_id": task_id,
                "step_id": step_id,
                "timeout_minutes": timeout_minutes,
            },
        )
