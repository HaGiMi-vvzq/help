from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.models.message import Message
from app.schemas.message import ConversationPreview, MessageCreate, MessageResponse


async def send_message(
    db: AsyncSession, sender_id: int, data: MessageCreate,
    event_bus: EventBus | None = None,
) -> MessageResponse:
    msg = Message(
        need_id=data.need_id,
        sender_id=sender_id,
        receiver_id=data.receiver_id,
        content=data.content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    if event_bus:
        await event_bus.emit_background("message_sent", {
            "sender_id": sender_id, "receiver_id": data.receiver_id, "need_id": data.need_id,
        })

    return MessageResponse.model_validate(msg)


async def get_conversation(
    db: AsyncSession, user_a_id: int, user_b_id: int, need_id: int | None = None,
) -> list[MessageResponse]:
    query = (
        select(Message)
        .where(
            or_(
                (Message.sender_id == user_a_id) & (Message.receiver_id == user_b_id),
                (Message.sender_id == user_b_id) & (Message.receiver_id == user_a_id),
            )
        )
        .order_by(Message.created_at)
    )
    if need_id:
        query = query.where(Message.need_id == need_id)
    result = await db.execute(query)
    messages = result.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]


def conversation_partner_expr(user_id: int):
    """Return the other participant for messages involving the current user."""
    return case(
        (Message.sender_id == user_id, Message.receiver_id),
        else_=Message.sender_id,
    )


async def get_conversations(
    db: AsyncSession, user_id: int,
) -> list[ConversationPreview]:
    from sqlalchemy import func

    other_user_id = conversation_partner_expr(user_id).label("other_user_id")

    sub = (
        select(
            Message.id,
            Message.need_id,
            Message.sender_id,
            Message.receiver_id,
            other_user_id,
            Message.content,
            Message.created_at,
            func.row_number()
            .over(
                partition_by=(conversation_partner_expr(user_id), Message.need_id),
                order_by=Message.created_at.desc(),
            )
            .label("rn"),
        )
        .where(
            or_(Message.sender_id == user_id, Message.receiver_id == user_id),
            Message.sender_id != Message.receiver_id,  # exclude system notifications
        )
        .subquery()
    )

    result = await db.execute(
        select(sub).where(sub.c.rn == 1).order_by(sub.c.created_at.desc())
    )
    rows = result.all()

    previews = []
    from app.models.user import User

    for row in rows:
        other_id = row.other_user_id
        user_result = await db.execute(select(User).where(User.id == other_id))
        other_user = user_result.scalar_one_or_none()
        previews.append(
            ConversationPreview(
                other_user_id=other_id,
                other_username=other_user.username if other_user else "未知",
                need_id=row.need_id,
                last_message=row.content[:50],
                last_time=row.created_at,
            )
        )
    return previews
