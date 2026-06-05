import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.events import get_event_bus
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageResponse
from app.services import message_service

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])
logger = logging.getLogger(__name__)

# WebSocket connection registry: user_id -> list of WebSocket connections
_ws_connections: dict[int, list[WebSocket]] = {}


async def notify_user(user_id: int, event: str, data: dict) -> None:
    """Push a real-time event to all WebSocket connections for a user."""
    conns = _ws_connections.get(user_id, [])
    payload = json.dumps({"event": event, "data": data}, ensure_ascii=False)
    dead = []
    for ws in conns:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        conns.remove(ws)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    """WebSocket for real-time message notifications."""
    from app.core.security import decode_access_token
    payload = decode_access_token(token)
    if not payload:
        await ws.close(code=4001, reason="Invalid token")
        return

    user_id = payload.get("user_id")
    if not user_id:
        await ws.close(code=4001, reason="Invalid token")
        return

    await ws.accept()
    _ws_connections.setdefault(user_id, []).append(ws)
    logger.debug("WebSocket connected: user_id=%d", user_id)

    try:
        while True:
            # Keep alive — wait for client messages (we ignore them, just keep connection open)
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WebSocket error for user_id=%d", user_id, exc_info=True)
    finally:
        conns = _ws_connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        logger.debug("WebSocket disconnected: user_id=%d", user_id)


@router.get("/notifications")
async def get_notifications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回未读消息数和最近消息预览。"""
    count_result = await db.execute(
        select(func.count()).select_from(Message).where(
            Message.receiver_id == user.id, Message.is_read == False
        )
    )
    unread = count_result.scalar() or 0

    recent_result = await db.execute(
        select(Message).where(Message.receiver_id == user.id)
        .order_by(Message.created_at.desc()).limit(5)
    )
    recent = recent_result.scalars().all()

    from app.models.user import User as U
    items = []
    for m in recent:
        # Self-sent messages are system notifications
        if m.sender_id == m.receiver_id:
            sender_name = "系统"
        else:
            sender = (await db.execute(select(U).where(U.id == m.sender_id))).scalar_one_or_none()
            sender_name = sender.username if sender else "未知"
        items.append({
            "id": m.id, "sender_name": sender_name,
            "content": m.content[:60], "time": str(m.created_at),
            "need_id": m.need_id, "is_read": m.is_read,
        })

    return {"count": unread, "items": items}


@router.post("/read/{other_user_id}")
async def mark_read(
    other_user_id: int,
    need_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记与某用户的对话为已读。"""
    query = (
        select(Message).where(
            Message.sender_id == other_user_id,
            Message.receiver_id == user.id,
            Message.is_read == False,
        )
    )
    if need_id:
        query = query.where(Message.need_id == need_id)
    result = await db.execute(query)
    for m in result.scalars():
        m.is_read = True
    await db.commit()
    return {"ok": True}


@router.post("", response_model=MessageResponse)
async def send_message(
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Content moderation
    from app.guardrails.content_moderator import moderate_message
    mod_result = moderate_message(data.content)
    if mod_result.blocked:
        raise HTTPException(400, detail=f"消息包含违规内容（{', '.join(mod_result.reasons)}）")

    msg = await message_service.send_message(db, user.id, data, get_event_bus())

    # Audit log
    from app.services.audit_service import log_message_sent
    asyncio.create_task(log_message_sent(user.id, msg.id, data.receiver_id))

    return msg


@router.get("/conversations")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await message_service.get_conversations(db, user.id)


@router.get("/{other_user_id}")
async def get_conversation(
    other_user_id: int,
    need_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await message_service.get_conversation(db, user.id, other_user_id, need_id)
