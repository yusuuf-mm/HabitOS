"""WebSocket connection manager for real-time schedule synchronization."""
import json
import logging
from typing import Dict, Set
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections, keyed by user ID.

    When a state mutation occurs (behavior completion, skip, re-opt),
    call ``broadcast_schedule_update(user_id)`` to push an invalidation
    signal to every connected client for that user.
    """

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    def _key(self, user_id: UUID) -> str:
        return str(user_id)

    async def connect(self, websocket: WebSocket, user_id: UUID) -> None:
        await websocket.accept()
        key = self._key(user_id)
        if key not in self._connections:
            self._connections[key] = set()
        self._connections[key].add(websocket)
        logger.info("WS connected: user=%s  (total=%d)", key, len(self._connections[key]))

    def disconnect(self, websocket: WebSocket, user_id: UUID) -> None:
        key = self._key(user_id)
        conns = self._connections.get(key)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[key]
            logger.info("WS disconnected: user=%s", key)

    async def broadcast_schedule_update(self, user_id: UUID) -> None:
        """Push a ``schedule_updated`` event to all of a user's connections."""
        key = self._key(user_id)
        conns = self._connections.get(key, set()).copy()
        if not conns:
            return

        payload = json.dumps({"type": "schedule_updated", "user_id": key})
        stale: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws, user_id)

    async def broadcast_reoptimization(self, user_id: UUID, run_id: str) -> None:
        """Push a ``reoptimization_completed`` event."""
        key = self._key(user_id)
        conns = self._connections.get(key, set()).copy()
        if not conns:
            return

        payload = json.dumps({
            "type": "reoptimization_completed",
            "user_id": key,
            "run_id": run_id,
        })
        stale: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws, user_id)


# Singleton — imported by the WS route and schedule endpoints.
manager = ConnectionManager()
