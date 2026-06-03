from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.core.events import EventBus
from app.models.user import User
from app.schemas.auth import AuthResponse, RegisterRequest
from app.schemas.user import UserResponse
from app.skills.registry import SkillRegistry
from app.knowledge.skill_graph import get_skill_graph


MIN_PASSWORD_LENGTH = 6


def validate_password_strength(password: str) -> str | None:
    """Return error message if password is too weak, None if acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"密码长度不能少于 {MIN_PASSWORD_LENGTH} 位"
    if len(password) > 128:
        return "密码长度不能超过 128 位"
    if " " in password:
        return "密码不能包含空格"
    return None


def validate_username(username: str) -> str | None:
    """Return error message if username is invalid, None if acceptable."""
    username = username.strip()
    if len(username) < 2:
        return "用户名长度不能少于 2 位"
    if len(username) > 20:
        return "用户名长度不能超过 20 位"
    if not username.replace("_", "").replace("-", "").isalnum():
        return "用户名只能包含字母、数字、下划线和连字符"
    return None


async def register(
    db: AsyncSession, data: RegisterRequest, event_bus: EventBus | None = None
) -> AuthResponse:
    # Validate username
    if err := validate_username(data.username):
        raise ValueError(err)

    # Validate password strength
    if err := validate_password_strength(data.password):
        raise ValueError(err)

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
