from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.events import get_event_bus
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageResponse
from app.services import message_service

router = APIRouter(prefix="/api/messages", tags=["messages"])


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
    return await message_service.send_message(db, user.id, data, get_event_bus())


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
