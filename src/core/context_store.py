"""Redis-backed shared context store for inter-agent communication.

Keys are namespaced as ``context:{task_id}:{key}`` so every task has
its own isolated keyspace that can be cleaned up atomically.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

from src.core.config import settings
from src.core.exceptions import ContextStoreError

logger = logging.getLogger(__name__)

_KEY_PREFIX = "context"


def _context_key(task_id: str, key: str) -> str:
    """Build a namespaced Redis key for a context entry."""
    return f"{_KEY_PREFIX}:{task_id}:{key}"


def _context_pattern(task_id: str) -> str:
    """Return a glob pattern that matches all context keys for a task."""
    return f"{_KEY_PREFIX}:{task_id}:*"


class ContextStore:
    """Async, Redis-backed shared context store.

    All values are JSON-serialised before storage and deserialised on
    retrieval, so any JSON-compatible Python value can be stored.

    Additionally exposes Redis Pub/Sub helpers for real-time event
    broadcasting between agents.
    """

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client
        self._default_ttl: int = settings.redis.context_ttl_seconds
        self._pubsub: aioredis.client.PubSub | None = None

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
        """Gracefully close the Redis connection and any active Pub/Sub."""
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    # ------------------------------------------------------------------
    # Key/Value API
    # ------------------------------------------------------------------

    async def set(
        self,
        task_id: str,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Store a JSON-serialisable *value* under *task_id*/*key*.

        Parameters:
            task_id: The owning task identifier.
            key: An arbitrary string key scoped to the task.
            value: Any JSON-serialisable Python object.
            ttl: Time-to-live in seconds.  Defaults to the configured
                 ``context_ttl_seconds``.
        """
        r = await self._get_redis()
        rkey = _context_key(task_id, key)
        effective_ttl = ttl if ttl is not None else self._default_ttl

        try:
            payload = json.dumps(value)
            if effective_ttl > 0:
                await r.set(rkey, payload, ex=effective_ttl)
            else:
                await r.set(rkey, payload)
            logger.debug("Set context %s = %s (ttl=%s)", rkey, payload[:120], effective_ttl)
        except (TypeError, ValueError) as exc:
            raise ContextStoreError(
                f"Failed to serialise value for context key '{rkey}': {exc}",
                details={"task_id": task_id, "key": key},
            ) from exc
        except aioredis.RedisError as exc:
            raise ContextStoreError(
                f"Redis error writing context key '{rkey}': {exc}",
                details={"task_id": task_id, "key": key},
            ) from exc

    async def get(self, task_id: str, key: str) -> Any:
        """Retrieve a value by *task_id* and *key*.

        Returns ``None`` if the key does not exist or has expired.
        """
        r = await self._get_redis()
        rkey = _context_key(task_id, key)

        try:
            raw = await r.get(rkey)
            if raw is None:
                return None
            return json.loads(raw)
        except aioredis.RedisError as exc:
            raise ContextStoreError(
                f"Redis error reading context key '{rkey}': {exc}",
                details={"task_id": task_id, "key": key},
            ) from exc

    async def delete(self, task_id: str, key: str) -> None:
        """Delete a single context key."""
        r = await self._get_redis()
        rkey = _context_key(task_id, key)

        try:
            await r.delete(rkey)
            logger.debug("Deleted context key %s", rkey)
        except aioredis.RedisError as exc:
            raise ContextStoreError(
                f"Redis error deleting context key '{rkey}': {exc}",
                details={"task_id": task_id, "key": key},
            ) from exc

    async def get_all(self, task_id: str) -> dict[str, Any]:
        """Return every context key/value pair stored for a task.

        Keys are returned without the namespace prefix (i.e. just the
        user-supplied portion).
        """
        r = await self._get_redis()
        pattern = _context_pattern(task_id)
        prefix = f"{_KEY_PREFIX}:{task_id}:"

        try:
            result: dict[str, Any] = {}
            keys: list[str] = []
            async for rkey in r.scan_iter(match=pattern):
                keys.append(rkey)

            if not keys:
                return result

            raw_values = await r.mget(keys)
            for rkey, raw in zip(keys, raw_values):
                if raw is not None:
                    short_key = rkey[len(prefix):]
                    result[short_key] = json.loads(raw)

            return result
        except aioredis.RedisError as exc:
            raise ContextStoreError(
                f"Redis error reading all context for task '{task_id}': {exc}",
                details={"task_id": task_id},
            ) from exc

    async def cleanup(self, task_id: str) -> int:
        """Delete *all* context keys belonging to a task.

        Returns the number of keys removed.
        """
        r = await self._get_redis()
        pattern = _context_pattern(task_id)

        try:
            keys: list[str] = []
            async for rkey in r.scan_iter(match=pattern):
                keys.append(rkey)

            if not keys:
                return 0

            count = await r.delete(*keys)
            logger.info("Cleaned up %d context key(s) for task %s", count, task_id)
            return count
        except aioredis.RedisError as exc:
            raise ContextStoreError(
                f"Redis error cleaning up context for task '{task_id}': {exc}",
                details={"task_id": task_id},
            ) from exc

    # ------------------------------------------------------------------
    # Pub/Sub API
    # ------------------------------------------------------------------

    async def publish(self, channel: str, message: dict) -> int:
        """Publish a JSON *message* to a Redis Pub/Sub *channel*.

        Returns the number of subscribers that received the message.
        """
        r = await self._get_redis()

        try:
            payload = json.dumps(message)
            receivers = await r.publish(channel, payload)
            logger.debug("Published to '%s' (%d receivers)", channel, receivers)
            return receivers
        except aioredis.RedisError as exc:
            raise ContextStoreError(
                f"Redis error publishing to channel '{channel}': {exc}",
                details={"channel": channel},
            ) from exc

    async def subscribe(self, channel: str) -> aioredis.client.PubSub:
        """Subscribe to a Redis Pub/Sub *channel*.

        Returns the ``PubSub`` object.  Callers iterate over messages
        with ``async for message in pubsub.listen():``.

        Example::

            pubsub = await store.subscribe("task:events")
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    data = json.loads(msg["data"])
                    ...
        """
        r = await self._get_redis()

        try:
            self._pubsub = r.pubsub()
            await self._pubsub.subscribe(channel)
            logger.info("Subscribed to channel '%s'", channel)
            return self._pubsub
        except aioredis.RedisError as exc:
            raise ContextStoreError(
                f"Redis error subscribing to channel '{channel}': {exc}",
                details={"channel": channel},
            ) from exc
