import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import MatchMemory


class MatchMemoryStore:
    @staticmethod
    async def add_success(
        db: AsyncSession,
        need_description: str,
        need_embedding: list[float],
        matched_user_id: int,
        score: float,
        ai_reason: str,
        feedback: int,
    ) -> None:
        entry = MatchMemory(
            need_description=need_description,
            need_embedding=need_embedding,
            matched_user_id=matched_user_id,
            score=score,
            ai_reason=ai_reason,
            feedback=feedback,
        )
        db.add(entry)
        await db.commit()

    @staticmethod
    async def retrieve_similar(
        db: AsyncSession, need_embedding: list[float], top_k: int = 3
    ) -> list[dict]:
        result = await db.execute(select(MatchMemory))
        records = result.scalars().all()
        if not records:
            return []

        scores = []
        query = np.array(need_embedding)
        for r in records:
            if r.need_embedding:
                emb = np.array(r.need_embedding)
                dot = float(np.dot(query, emb))
                norm = float(np.linalg.norm(query) * np.linalg.norm(emb))
                sim = dot / norm if norm > 0 else 0.0
                scores.append(
                    {
                        "need_description": r.need_description,
                        "ai_reason": r.ai_reason,
                        "score": r.score,
                        "similarity": sim,
                    }
                )

        scores.sort(key=lambda x: x["similarity"], reverse=True)
        return scores[:top_k]
