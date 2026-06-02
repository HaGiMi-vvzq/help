from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.core.events import EventBus
from app.models.user import User
from app.schemas.auth import AuthResponse, RegisterRequest
from app.schemas.user import UserResponse
from app.skills.registry import SkillRegistry
from app.knowledge.skill_graph import get_skill_graph


async def register(
    db: AsyncSession, data: RegisterRequest, event_bus: EventBus | None = None
) -> AuthResponse:
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise ValueError("用户名已存在")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        bio=data.bio,
        school=data.school,
    )

    if data.bio:
        tag_skill = SkillRegistry.get("tag_extraction")
        tags_result = await tag_skill.execute({"text": data.bio})
        tags = tags_result.get("tags", [])
        if tags:
            user.skill_tags = tags
            embed_skill = SkillRegistry.get("embedding")
            emb_result = await embed_skill.execute({"text": " ".join(tags)})
            user.profile_embedding = emb_result["embedding"]
            graph = get_skill_graph()
            graph.add_co_occurrence(tags)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    if event_bus:
        await event_bus.emit_background("user_registered", {"user_id": user.id, "username": user.username})

    token = create_access_token({"user_id": user.id})
    return AuthResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


async def login(db: AsyncSession, username: str, password: str) -> AuthResponse:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("用户名或密码错误")

    token = create_access_token({"user_id": user.id})
    return AuthResponse(access_token=token, user=UserResponse.model_validate(user))
