import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.knowledge.match_memory import MatchMemoryStore
from app.knowledge.skill_graph import get_skill_graph
from app.models.user import User

logger = logging.getLogger(__name__)


class SemanticSearchAgent(BaseAgent):
    name = "SemanticSearchAgent"
    description = "向量检索 + 知识库展开 Top 10 候选人"

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        await self.think("正在进行语义检索...")

        need_embedding = input_data["embedding"]
        tags = input_data.get("tags", [])
        db: AsyncSession = input_data["db"]

        graph = get_skill_graph()
        expanded = graph.expand_multi(tags) if tags else []

        result = await db.execute(select(User))
        users = result.scalars().all()

        candidates = []
        embedding_skill = None
        embeddings_updated = False
        for u in users:
            if input_data.get("exclude_user_id") and u.id == input_data["exclude_user_id"]:
                continue
            if u.profile_embedding is None:
                profile_text = " ".join(u.skill_tags or []) or (u.bio or "").strip()
                if not profile_text:
                    continue
                try:
                    if embedding_skill is None:
                        embedding_skill = self.use_skill("embedding")
                    embedding_result = await embedding_skill.execute({"text": profile_text})
                    u.profile_embedding = embedding_result["embedding"]
                    embeddings_updated = True
                except Exception:
                    logger.exception("Failed to lazily embed candidate user_id=%s", u.id)
                    continue
            candidates.append(
                {
                    "id": u.id,
                    "username": u.username,
                    "bio": u.bio or "",
                    "skill_tags": u.skill_tags or [],
                    "school": u.school or "",
                    "rating_score": u.rating_score,
                    "embedding": u.profile_embedding,
                }
            )

        if embeddings_updated:
            await db.commit()

        match_skill = self.use_skill("vector_match")
        result = await match_skill.execute(
            {"query_embedding": need_embedding, "candidates": candidates, "top_k": 6}
        )

        memory_context = await MatchMemoryStore.retrieve_similar(db, need_embedding)

        return {
            "candidates": result["matches"],
            "knowledge_context": f"关联技能: {expanded}" if expanded else "",
            "match_memory_context": str(memory_context) if memory_context else "",
        }
