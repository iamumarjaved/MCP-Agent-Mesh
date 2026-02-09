"""Agent registry and health routes.

Exposes endpoints for listing registered agents, inspecting individual
agent details, querying health metrics, and discovering agents by
capability.  All data is served from the ``AgentRegistry`` stored in
``request.app.state.agent_registry``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.routes.auth import verify_token
from src.core.exceptions import AgentRegistrationError
from src.core.models import AgentCard, AgentHealthResponse

router = APIRouter(prefix="/agents", tags=["Agents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_registry(request: Request):
    """Retrieve the AgentRegistry from application state."""
    registry = request.app.state.agent_registry
    if registry is None:
        raise HTTPException(
            status_code=503,
            detail="Agent registry is not initialised.",
        )
    return registry


def _card_to_dict(card: AgentCard) -> dict[str, Any]:
    """Serialise an ``AgentCard`` to a JSON-friendly dict."""
    return card.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def list_agents(
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """List all registered agents with their health status.

    Returns basic metadata for every agent currently in the registry.
    Agents whose TTL has expired in Redis are automatically excluded.
    """
    registry = _get_registry(request)

    try:
        cards: list[AgentCard] = await registry.list_all()
    except AgentRegistrationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {
        "count": len(cards),
        "agents": [_card_to_dict(c) for c in cards],
    }


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """Get full details and capabilities for a specific agent.

    Returns the complete ``AgentCard`` including input/output schemas,
    cost estimates, average latency, and registration timestamp.
    """
    registry = _get_registry(request)

    try:
        card: AgentCard | None = await registry.get_agent(agent_id)
    except AgentRegistrationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if card is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found or has expired.",
        )

    return _card_to_dict(card)


@router.get("/{agent_id}/health")
async def agent_health(
    agent_id: str,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> AgentHealthResponse:
    """Get detailed health metrics for an agent.

    Computes uptime from the registration timestamp and returns health
    status, average latency, error rate, and last heartbeat time.
    """
    registry = _get_registry(request)

    try:
        card: AgentCard | None = await registry.get_agent(agent_id)
    except AgentRegistrationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if card is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found or has expired.",
        )

    now = datetime.now(timezone.utc)
    uptime_seconds = (now - card.registered_at).total_seconds()

    # Error rate is not tracked in the card itself; derive a placeholder
    # from the health field.  A production implementation would query
    # actual error counters from a metrics store.
    error_rate = 0.0 if card.health == "healthy" else 1.0

    return AgentHealthResponse(
        agent_id=card.agent_id,
        name=card.name,
        health=card.health,
        uptime_seconds=uptime_seconds,
        avg_latency_ms=float(card.avg_latency_ms),
        error_rate=error_rate,
        last_heartbeat=card.last_heartbeat,
    )


@router.get("/capabilities/{capability}")
async def find_agents_by_capability(
    capability: str,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """Discover agents that declare a specific capability.

    Uses the Redis-backed capability index to find agents that can
    fulfil the requested capability (e.g. ``"data_retrieval"``,
    ``"statistical_analysis"``).
    """
    registry = _get_registry(request)

    try:
        cards: list[AgentCard] = await registry.discover(capability)
    except AgentRegistrationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {
        "capability": capability,
        "count": len(cards),
        "agents": [_card_to_dict(c) for c in cards],
    }
