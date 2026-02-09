"""Agent discovery and registration backed by Redis.

Stores AgentCard data in Redis with configurable TTLs, enabling agents
to register, send heartbeats, and be discovered by capability.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis

from src.core.config import settings
from src.core.exceptions import AgentRegistrationError
from src.core.models import AgentCard

logger = logging.getLogger(__name__)

_KEY_PREFIX = "agents"


def _agent_key(agent_id: str) -> str:
    """Build a namespaced Redis key for an agent."""
    return f"{_KEY_PREFIX}:{agent_id}"


def _capability_index_key(capability: str) -> str:
    """Build a namespaced Redis key for a capability index set."""
    return f"{_KEY_PREFIX}:cap:{capability}"


class AgentRegistry:
    """Async agent registry backed by Redis.

    Each registered agent is stored as a JSON-serialised ``AgentCard`` under
    the key ``agents:{agent_id}`` with a configurable TTL.  Capability-based
    discovery is supported via per-capability Redis sets that hold agent IDs.
    """

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client
        self._ttl: int = settings.redis.registry_ttl_seconds

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    async def _get_redis(self) -> aioredis.Redis:
        """Lazily initialise and return the Redis client."""
        if self._redis is None:
            self._redis = aioredis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                password=settings.redis.password or None,
                db=settings.redis.db,
                ssl=settings.redis.ssl,
                decode_responses=True,
            )
        return self._redis

    async def close(self) -> None:
        """Gracefully close the underlying Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def register(self, agent_card: AgentCard) -> None:
        """Register an agent by storing its card in Redis with a TTL.

        The agent's capabilities are also indexed so that
        :meth:`discover` can look them up efficiently.

        Raises:
            AgentRegistrationError: If the Redis write fails.
        """
        r = await self._get_redis()
        key = _agent_key(agent_card.agent_id)
        payload = agent_card.model_dump_json()

        try:
            pipe = r.pipeline(transaction=True)
            pipe.set(key, payload, ex=self._ttl)

            # Maintain per-capability index sets.
            for cap in agent_card.capabilities:
                idx_key = _capability_index_key(cap)
                pipe.sadd(idx_key, agent_card.agent_id)
                # Keep the index alive as long as agents with the capability exist.
                pipe.expire(idx_key, self._ttl * 2)

            await pipe.execute()
            logger.info(
                "Registered agent %s (%s) with TTL %ds",
                agent_card.agent_id,
                agent_card.name,
                self._ttl,
            )
        except aioredis.RedisError as exc:
            raise AgentRegistrationError(
                f"Failed to register agent '{agent_card.agent_id}': {exc}",
                details={"agent_id": agent_card.agent_id},
            ) from exc

    async def deregister(self, agent_id: str) -> None:
        """Remove an agent from the registry and all capability indices."""
        r = await self._get_redis()
        key = _agent_key(agent_id)

        try:
            # Retrieve current card to clean up capability indices.
            raw = await r.get(key)
            if raw is not None:
                card = AgentCard.model_validate_json(raw)
                pipe = r.pipeline(transaction=True)
                pipe.delete(key)
                for cap in card.capabilities:
                    pipe.srem(_capability_index_key(cap), agent_id)
                await pipe.execute()
                logger.info("Deregistered agent %s", agent_id)
            else:
                logger.warning("Attempted to deregister unknown agent %s", agent_id)
        except aioredis.RedisError as exc:
            raise AgentRegistrationError(
                f"Failed to deregister agent '{agent_id}': {exc}",
                details={"agent_id": agent_id},
            ) from exc

    async def discover(self, capability: str) -> list[AgentCard]:
        """Return all agents that declare the given *capability*."""
        r = await self._get_redis()

        try:
            idx_key = _capability_index_key(capability)
            agent_ids: set[str] = await r.smembers(idx_key)

            cards: list[AgentCard] = []
            for aid in agent_ids:
                card = await self.get_agent(aid)
                if card is not None:
                    cards.append(card)
                else:
                    # Stale reference -- clean up the index.
                    await r.srem(idx_key, aid)

            return cards
        except aioredis.RedisError as exc:
            raise AgentRegistrationError(
                f"Discovery failed for capability '{capability}': {exc}",
                details={"capability": capability},
            ) from exc

    async def get_agent(self, agent_id: str) -> AgentCard | None:
        """Retrieve a single agent card, or ``None`` if not found / expired."""
        r = await self._get_redis()

        try:
            raw = await r.get(_agent_key(agent_id))
            if raw is None:
                return None
            return AgentCard.model_validate_json(raw)
        except aioredis.RedisError as exc:
            raise AgentRegistrationError(
                f"Failed to get agent '{agent_id}': {exc}",
                details={"agent_id": agent_id},
            ) from exc

    async def heartbeat(self, agent_id: str) -> None:
        """Refresh the TTL for an agent and update its ``last_heartbeat``.

        If the agent is not currently registered this is a no-op.
        """
        r = await self._get_redis()
        key = _agent_key(agent_id)

        try:
            raw = await r.get(key)
            if raw is None:
                logger.warning("Heartbeat for unknown/expired agent %s", agent_id)
                return

            card = AgentCard.model_validate_json(raw)
            card.last_heartbeat = datetime.now(timezone.utc)
            await r.set(key, card.model_dump_json(), ex=self._ttl)

            logger.debug("Heartbeat refreshed for agent %s", agent_id)
        except aioredis.RedisError as exc:
            raise AgentRegistrationError(
                f"Heartbeat failed for agent '{agent_id}': {exc}",
                details={"agent_id": agent_id},
            ) from exc

    async def list_all(self) -> list[AgentCard]:
        """Return every currently-registered agent card."""
        r = await self._get_redis()

        try:
            keys: list[str] = []
            async for key in r.scan_iter(match=f"{_KEY_PREFIX}:*"):
                # Skip capability index keys.
                if ":cap:" not in key:
                    keys.append(key)

            if not keys:
                return []

            raw_values = await r.mget(keys)
            cards: list[AgentCard] = []
            for raw in raw_values:
                if raw is not None:
                    cards.append(AgentCard.model_validate_json(raw))
            return cards
        except aioredis.RedisError as exc:
            raise AgentRegistrationError(
                f"Failed to list agents: {exc}",
            ) from exc

    async def health_check(self, agent_id: str) -> bool:
        """Return ``True`` if the agent exists and its ``health`` is *healthy*."""
        card = await self.get_agent(agent_id)
        if card is None:
            return False
        return card.health == "healthy"
