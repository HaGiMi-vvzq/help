import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tag_extraction_agent import TagExtractionAgent
from app.agents.semantic_search_agent import SemanticSearchAgent
from app.agents.rerank_agent import RerankAgent
from app.agents.concierge_agent import ConciergeAgent

logger = logging.getLogger(__name__)

tag_extraction_agent = TagExtractionAgent()
semantic_search_agent = SemanticSearchAgent()
rerank_agent = RerankAgent()
concierge_agent = ConciergeAgent()


class AgentOrchestrator:
    @staticmethod
    async def _get_cold_start_weight(db: AsyncSession, user_id: int) -> float:
        """冷启动渐进权重: 前5次纯语义(1.0) → 过渡(0.7) → 个性化(0.5)"""
        from sqlalchemy import func
        from app.models.match import Match
        from app.models.need import Need

        from sqlalchemy import select as _sel
        result = await db.execute(
            _sel(func.count())
            .select_from(Match)
            .join(Need, Match.need_id == Need.id)
            .where(Need.user_id == user_id)
        )
        count = result.scalar() or 0
        if count < 5:
            return 1.0
        if count < 15:
            return 0.7
        return 0.5

    @staticmethod
    async def _load_preferences(db: AsyncSession, user_id: int) -> dict:
        """加载用户偏好向量用于匹配调整"""
        from sqlalchemy import select as _sel
        from app.models.behavior import UserPreferenceProfile
        result = await db.execute(
            _sel(UserPreferenceProfile).where(UserPreferenceProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        return profile.preference_vector if profile and profile.preference_vector else {}

    @staticmethod
    async def run_matching_pipeline(
        db: AsyncSession,
        need_description: str,
        need_embedding: list[float] | None,
        need_tags: list[str] | None,
        exclude_user_id: int,
        _event_bus=None,
    ) -> list[dict]:
        progress: list[dict] = []

        async def emit(stage: str, message: str, data: dict | None = None):
            p = {"stage": stage, "message": message, "data": data or {}}
            progress.append(p)
            if _event_bus:
                await _event_bus.emit("matching_progress", p)

        # Stage 1: Tag Extraction Agent
        if not need_tags:
            await emit("tag_extraction", "正在分析需求标签...")
            tags_result = await tag_extraction_agent.execute({"text": need_description})
            if not tags_result.get("safe"):
                await emit("error", "内容审核未通过")
                return []
            need_tags = tags_result.get("tags", [])
            await emit("tag_extraction", f"提取到 {len(need_tags)} 个标签", {"tags": need_tags})
        else:
            await emit("tag_extraction", f"已有 {len(need_tags)} 个标签", {"tags": need_tags})

        # Stage 2: Semantic Search Agent
        if need_embedding:
            await emit("semantic_search", "正在语义检索候选人...")
            search_result = await semantic_search_agent.execute(
                {
                    "embedding": need_embedding,
                    "tags": need_tags,
                    "db": db,
                    "exclude_user_id": exclude_user_id,
                }
            )
            candidates = search_result["candidates"]
            knowledge_context = search_result["knowledge_context"]
            match_memory = search_result["match_memory_context"]
            await emit("semantic_search", f"找到 {len(candidates)} 位候选", {"count": len(candidates)})
        else:
            await emit("error", "需求向量不可用")
            return []

        if not candidates:
            await emit("done", "暂无匹配结果")
            return []

        # Stage 3: Rerank Agent (含冷启动 + 偏好调整)
        await emit("rerank", "正在AI精排并生成推荐理由...")
        rerank_result = await rerank_agent.execute(
            {
                "need_description": need_description,
                "need_tags": need_tags,
                "candidates": candidates,
                "knowledge_context": knowledge_context,
                "match_memory_context": match_memory,
            }
        )
        results = rerank_result.get("results", [])

        # 加载用户偏好并应用冷启动渐进调整
        semantic_weight = await AgentOrchestrator._get_cold_start_weight(db, exclude_user_id)
        preferences = await AgentOrchestrator._load_preferences(db, exclude_user_id)

        if preferences and semantic_weight < 1.0:
            pref_weight = 1.0 - semantic_weight
            for r in results:
                uid = r["user_id"]
                # 简单偏好加成: 同校偏好 +1~5分
                bonus = 0
                if "同校偏好" in preferences and preferences["同校偏好"] > 0.6:
                    # need to check school — pass from search
                    for c in candidates:
                        if c.get("id") == uid:
                            bonus += 3
                            break
                # 应用偏好权重
                r["score"] = min(100, int(r["score"] * semantic_weight + (r["score"] + bonus) * pref_weight))
        await emit("done", f"匹配完成，Top {len(results)}", {"results": results})

        return results

    @staticmethod
    async def run_concierge(need_description: str, need_tags: list[str] | None = None) -> dict:
        return await concierge_agent.execute(
            {"need_description": need_description, "need_tags": need_tags or []}
        )

    @staticmethod
    async def run_concierge_chat(
        need_description: str, need_tags: list[str],
        history: list[dict], matches: list[dict] | None = None,
    ) -> str:
        return await concierge_agent.chat(need_description, need_tags, history, matches)
