"""WebSocket routes for real-time task and agent activity updates.

Provides both global and per-task WebSocket connections.  The
``ConnectionManager`` maintains active connections and supports
broadcasting events to all subscribers or only to those watching
a specific task.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.core.models import WSEvent

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time event delivery.

    Supports two connection modes:
    - **Global**: connects to ``/ws`` and receives all events.
    - **Per-task**: connects to ``/ws/{task_id}`` and receives only
      events for that specific task.
    """

    def __init__(self) -> None:
        # task_id -> list of WebSocket connections watching that task.
        self.active_connections: dict[str, list[WebSocket]] = {}
        # Connections that receive all events.
        self.global_connections: list[WebSocket] = []

    async def connect(
        self,
        websocket: WebSocket,
        task_id: str | None = None,
    ) -> None:
        """Accept a WebSocket connection and register it.

        Parameters:
            websocket: The incoming WebSocket connection.
            task_id: If provided, the connection is scoped to events for
                this task.  If ``None``, the connection receives all events.
        """
        await websocket.accept()

        if task_id is not None:
            if task_id not in self.active_connections:
                self.active_connections[task_id] = []
            self.active_connections[task_id].append(websocket)
            logger.info("ws_connected", task_id=task_id, scope="task")
        else:
            self.global_connections.append(websocket)
            logger.info("ws_connected", scope="global")

    def disconnect(
        self,
        websocket: WebSocket,
        task_id: str | None = None,
    ) -> None:
        """Remove a WebSocket connection from the tracked set.

        Safe to call even if the connection was already removed.
        """
        if task_id is not None:
            conns = self.active_connections.get(task_id, [])
            if websocket in conns:
                conns.remove(websocket)
            # Clean up empty lists.
            if not conns and task_id in self.active_connections:
                del self.active_connections[task_id]
            logger.info("ws_disconnected", task_id=task_id, scope="task")
        else:
            if websocket in self.global_connections:
                self.global_connections.remove(websocket)
            logger.info("ws_disconnected", scope="global")

    async def broadcast(self, event: WSEvent) -> None:
        """Send an event to all global connections and to connections
        watching the event's task.

        Failed sends (broken connections) are silently discarded and the
        connection is unregistered.
        """
        message = event.model_dump_json()

        # Send to global subscribers.
        stale_global: list[WebSocket] = []
        for ws in self.global_connections:
            try:
                await ws.send_text(message)
            except Exception:
                stale_global.append(ws)

        for ws in stale_global:
            self.disconnect(ws)

        # Send to task-specific subscribers.
        await self._send_to_task_connections(event.task_id, message)

    async def send_to_task(self, task_id: str, event: WSEvent) -> None:
        """Send an event only to connections watching the given task.

        Also delivers the event to global subscribers.
        """
        message = event.model_dump_json()

        # Global subscribers always get a copy.
        stale_global: list[WebSocket] = []
        for ws in self.global_connections:
            try:
                await ws.send_text(message)
            except Exception:
                stale_global.append(ws)

        for ws in stale_global:
            self.disconnect(ws)

        await self._send_to_task_connections(task_id, message)

    async def _send_to_task_connections(
        self,
        task_id: str,
        message: str,
    ) -> None:
        """Internal helper to send a pre-serialised message to task subscribers."""
        conns = self.active_connections.get(task_id, [])
        stale: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws, task_id=task_id)

    @property
    def connection_count(self) -> int:
        """Total number of active connections (global + task-scoped)."""
        task_count = sum(len(conns) for conns in self.active_connections.values())
        return len(self.global_connections) + task_count


# Module-level singleton so other modules can import and use it.
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Global WebSocket endpoint.

    Clients connected here receive all events from the mesh. Clients
    can also send JSON messages with an ``action`` field to subscribe
    to specific task updates or request status pings.
    """
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"error": "Invalid JSON"})
                )
                continue

            action = data.get("action")

            if action == "ping":
                await websocket.send_text(
                    json.dumps({
                        "action": "pong",
                        "connections": manager.connection_count,
                    })
                )

            elif action == "subscribe" and "task_id" in data:
                # Additionally subscribe this connection to a specific task.
                task_id = data["task_id"]
                if task_id not in manager.active_connections:
                    manager.active_connections[task_id] = []
                if websocket not in manager.active_connections[task_id]:
                    manager.active_connections[task_id].append(websocket)
                await websocket.send_text(
                    json.dumps({
                        "action": "subscribed",
                        "task_id": task_id,
                    })
                )

            elif action == "unsubscribe" and "task_id" in data:
                task_id = data["task_id"]
                conns = manager.active_connections.get(task_id, [])
                if websocket in conns:
                    conns.remove(websocket)
                await websocket.send_text(
                    json.dumps({
                        "action": "unsubscribed",
                        "task_id": task_id,
                    })
                )

            else:
                await websocket.send_text(
                    json.dumps({
                        "error": "Unknown action",
                        "supported_actions": ["ping", "subscribe", "unsubscribe"],
                    })
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Also remove from any task-specific subscriptions.
        for task_id in list(manager.active_connections.keys()):
            manager.disconnect(websocket, task_id=task_id)


@router.websocket("/ws/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str) -> None:
    """Per-task WebSocket endpoint.

    Clients connected here receive only events related to the specified
    ``task_id``.  Useful for dashboards or UIs that show the progress
    of a single task.
    """
    await manager.connect(websocket, task_id=task_id)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"error": "Invalid JSON"})
                )
                continue

            action = data.get("action")

            if action == "ping":
                await websocket.send_text(
                    json.dumps({
                        "action": "pong",
                        "task_id": task_id,
                        "connections": len(
                            manager.active_connections.get(task_id, [])
                        ),
                    })
                )
            else:
                await websocket.send_text(
                    json.dumps({
                        "error": "Unknown action",
                        "supported_actions": ["ping"],
                    })
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id=task_id)
