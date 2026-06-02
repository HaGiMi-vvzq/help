import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.skill_graph import get_skill_graph
from app.models.user import User
from app.schemas.user import ProfileUpdate, UserResponse
from app.skills.registry import SkillRegistry


async def update_profile(
    db: AsyncSession, user: User, data: ProfileUpdate
) -> UserResponse:
    if data.username is not None:
        user.username = data.username

    if data.bio is not None:
        user.bio = data.bio

    if data.school is not None:
        user.school = data.school

    if data.extra is not None:
        try:
            user.extra = json.loads(data.extra)
        except (json.JSONDecodeError, TypeError):
            user.extra = data.extra

    if data.skill_tags is not None:
        user.skill_tags = data.skill_tags

    await db.commit()
    await db.refresh(user)

    # Run embedding in background (slow, don't block profile save)
    if data.skill_tags is not None and data.skill_tags:
        import asyncio
        _tags = list(data.skill_tags)
        _user_id = user.id
        async def _embed_bg():
            from app.core.database import async_session
            from app.models.user import User as U
            from sqlalchemy import select as _s
            async with async_session() as bg_db:
                try:
                    r = await bg_db.execute(_s(U).where(U.id == _user_id))
                    u = r.scalar_one_or_none()
                    if u:
                        embed_skill = SkillRegistry.get("embedding")
                        emb_result = await embed_skill.execute({"text": " ".join(_tags)})
                        u.profile_embedding = emb_result["embedding"]
                        graph = get_skill_graph()
                        graph.add_co_occurrence(_tags)
                        await bg_db.commit()
                except Exception:
                    import logging
                    logging.getLogger(__name__).warning("Background embedding failed")
        asyncio.create_task(_embed_bg())

    return UserResponse.model_validate(user)
