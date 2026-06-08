"""WebSocket route for real-time schedule synchronization."""
import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.ws import manager
from app.core.security import verify_token, TokenTypeError
from app.db.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


async def _authenticate_ws(token: str, db: AsyncSession) -> UUID | None:
    """Validate a JWT access token and return the user_id."""
    try:
        payload = verify_token(token, expected_type="access")
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = UUID(user_id_str)
        # Verify the user actually exists
        result = await db.execute(select(User).where(User.id == user_id))
        if result.scalars().first() is None:
            return None
        return user_id
    except (TokenTypeError, Exception):
        return None


@router.websocket("/ws/schedule")
async def websocket_schedule(
    websocket: WebSocket,
    token: str = Query(...),
):
    """Persistent WebSocket for live schedule updates.

    Authenticate on connect; the manager broadcasts ``schedule_updated``
    and ``reoptimization_completed`` events whenever the user's schedule
    changes (behavior completion, skip, or re-optimization).
    """
    # Authenticate — accept the socket first so the client receives close
    # frames with status codes on failure.
    async for db in get_db():
        user_id = await _authenticate_ws(token, db)
        break

    if user_id is None:
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await manager.connect(websocket, user_id)

    try:
        # Keep the connection alive; clients may send pings or acks.
        while True:
            data = await websocket.receive_text()
            # Respond to client pings with a pong containing the raw data
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, user_id)
