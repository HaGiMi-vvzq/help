"""Backfill profile embeddings for users without one. Run from backend dir."""
import asyncio
from sqlalchemy import select
from app.core.database import async_session
from app.models.user import User
# Trigger skill registration (same as main.py)
from app.skills.registry import SkillRegistry
from app.skills.embed_skill import EmbedSkill
from app.skills.tag_skill import TagSkill
SkillRegistry.register(EmbedSkill())
SkillRegistry.register(TagSkill())

async def backfill():
    async with async_session() as db:
        users = (await db.execute(
            select(User).where(User.profile_embedding == None)
        )).scalars().all()

        if not users:
            print("All users already have profile embeddings.")
            return

        print(f"Backfilling embeddings for {len(users)} users...")
        embed_skill = SkillRegistry.get("embedding")

        for user in users:
            tags = user.skill_tags or []
            bio = user.bio or ""
            text = " ".join(tags) + " " + bio if tags or bio else user.username
            try:
                result = await embed_skill.execute({"text": text})
                user.profile_embedding = result.get("embedding")
                print(f"  {user.username}: embedding [{len(user.profile_embedding or [])} dims]")
            except Exception as e:
                print(f"  {user.username}: FAILED ({e})")

        await db.commit()
        print(f"Done. Updated {len(users)} users.")

if __name__ == "__main__":
    asyncio.run(backfill())
