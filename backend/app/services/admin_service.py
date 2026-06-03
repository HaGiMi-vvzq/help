"""Admin service: stats, user management, need management."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.need import Need
from app.models.message import Message
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_stats(db: AsyncSession) -> dict:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = await db.scalar(select(func.count()).select_from(User))
    active_users = await db.scalar(
        select(func.count()).select_from(User).where(User.is_active == True)
    )
    total_needs = await db.scalar(select(func.count()).select_from(Need))
    open_needs = await db.scalar(
        select(func.count()).select_from(Need).where(Need.status == "开放")
    )
    matched_needs = await db.scalar(
        select(func.count()).select_from(Need).where(Need.status == "已匹配")
    )
    total_messages = await db.scalar(select(func.count()).select_from(Message))
    today_users = await db.scalar(
        select(func.count()).select_from(User).where(User.created_at >= today)
    )
    today_needs = await db.scalar(
        select(func.count()).select_from(Need).where(Need.created_at >= today)
    )

    return {
        "total_users": total_users or 0,
        "active_users": active_users or 0,
        "total_needs": total_needs or 0,
        "open_needs": open_needs or 0,
        "matched_needs": matched_needs or 0,
        "total_messages": total_messages or 0,
        "today_users": today_users or 0,
        "today_needs": today_needs or 0,
    }


async def list_users(db: AsyncSession, page: int = 1, page_size: int = 20) -> dict:
    offset = (page - 1) * page_size
    total = await db.scalar(select(func.count()).select_from(User))
    users = (
        await db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    return {
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "is_active": u.is_active,
                "school": u.school,
                "bio": u.bio,
                "skill_tags": u.skill_tags,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "total": total or 0,
    }


async def update_user(db: AsyncSession, user_id: int, data: dict) -> User | None:
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        return None
    if "role" in data and data["role"] is not None:
        user.role = data["role"]
    if "is_active" in data and data["is_active"] is not None:
        user.is_active = data["is_active"]
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> bool:
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        return False
    if user.role == "admin":
        raise ValueError("不能删除管理员账号")
    # Clean up related data
    from app.models.need_application import NeedApplication
    from app.models.match import Match
    from app.models.agent import AgentSession, AgentTask, AgentFile, AgentMessage
    from app.models.message import Message

    await db.execute(delete(NeedApplication).where(
        (NeedApplication.applicant_user_id == user_id)
    ))
    await db.execute(delete(Match).where(Match.user_id == user_id))
    await db.execute(delete(Need).where(Need.user_id == user_id))
    await db.execute(delete(Message).where(
        (Message.sender_id == user_id) | (Message.receiver_id == user_id)
    ))
    # Clean up agent data
    sessions = (await db.execute(
        select(AgentSession.id).where(AgentSession.user_id == user_id)
    )).scalars().all()
    for sid in sessions:
        await db.execute(delete(AgentTask).where(AgentTask.session_id == sid))
        await db.execute(delete(AgentFile).where(AgentFile.session_id == sid))
        await db.execute(delete(AgentMessage).where(AgentMessage.session_id == sid))
    await db.execute(delete(AgentSession).where(AgentSession.user_id == user_id))

    await db.delete(user)
    await db.commit()
    return True


async def list_needs(db: AsyncSession, page: int = 1, page_size: int = 20) -> dict:
    offset = (page - 1) * page_size
    total = await db.scalar(select(func.count()).select_from(Need))
    needs = (
        await db.execute(
            select(Need, User.username)
            .join(User, Need.user_id == User.id)
            .order_by(Need.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).all()

    return {
        "items": [
            {
                "id": n.id,
                "user_id": n.user_id,
                "username": username,
                "type": n.type,
                "title": n.title,
                "description": n.description[:200] if n.description else "",
                "status": n.status,
                "selection_mode": n.selection_mode or "single",
                "created_at": n.created_at.isoformat(),
            }
            for n, username in needs
        ],
        "total": total or 0,
    }


async def update_need_status(db: AsyncSession, need_id: int, status: str) -> Need | None:
    need = await db.scalar(select(Need).where(Need.id == need_id))
    if not need:
        return None
    valid_statuses = {"开放", "已匹配", "已关闭"}
    if status not in valid_statuses:
        raise ValueError(f"无效状态: {status}，有效状态: {valid_statuses}")
    need.status = status
    await db.commit()
    await db.refresh(need)
    return need


async def delete_need(db: AsyncSession, need_id: int) -> bool:
    need = await db.scalar(select(Need).where(Need.id == need_id))
    if not need:
        return False
    from app.models.need_application import NeedApplication
    from app.models.match import Match
    from app.models.message import Message

    await db.execute(delete(NeedApplication).where(NeedApplication.need_id == need_id))
    await db.execute(delete(Match).where(Match.need_id == need_id))
    await db.execute(delete(Message).where(Message.need_id == need_id))
    from app.services.match_engine import cancel_matching
    await cancel_matching(need_id)
    await db.delete(need)
    await db.commit()
    return True
