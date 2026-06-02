import logging

from app.adapters.qwen_adapter import get_qwen_rerank
from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.agents.base import BaseAgent
from app.integrations.client import get_ai_client
from app.integrations.model_router import route

logger = logging.getLogger(__name__)


class RerankAgent(BaseAgent):
    """两阶段精排:
    Stage 2a: Qwen3-Reranker 本地交叉编码器打分 (免费, <100ms)
    Stage 2b: DeepSeek Chat 为 Top 5 生成推荐理由 (只调5次, 省token)
    """

    name = "RerankAgent"
    description = "Qwen3-Reranker 精排 + DeepSeek 推荐理由"

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        candidates = input_data["candidates"]
        need_description = input_data["need_description"]
        need_tags = input_data.get("need_tags", [])
        knowledge_context = input_data.get("knowledge_context", "")
        match_memory_context = input_data.get("match_memory_context", "")

        if not candidates:
            return {"results": []}

        # Stage 2a: Qwen3-Reranker 本地打分 (注入知识图谱展开的关联技能)
        await self.think("Qwen3-Reranker 正在本地精排...")

        # 将知识图谱上下文注入为候选文档的补充信息
        know_prefix = f"[知识图谱关联: {knowledge_context}] " if knowledge_context else ""

        try:
            reranker = get_qwen_rerank()
            docs = []
            for c in candidates:
                doc = (
                    f"{know_prefix}"
                    f"技能: {', '.join(c.get('skill_tags', []))}. "
                    f"{c.get('bio', '')}. 学校: {c.get('school', '')}"
                )
                docs.append(doc)

            scores = await reranker.rerank(need_description, docs)
            for i, c in enumerate(candidates):
                c["rerank_score"] = scores[i] if i < len(scores) else 0.0

            candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
            top5 = candidates[:5]
            await self.think(f"Reranker 完成, Top5 准备好, 最高分: {top5[0].get('rerank_score', 0):.3f}")
        except Exception:
            logger.exception("Qwen3-Reranker failed, falling back to vector similarity")
            candidates.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            top5 = candidates[:5]
            for c in top5:
                c["rerank_score"] = c.get("similarity", 0)

        # Stage 2b: DeepSeek 生成推荐理由 (仅 Top 5)
        await self.think("DeepSeek 正在生成推荐理由...")

        client = get_ai_client()
        cfg = route("rerank")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        top5_text = ""
        for idx, c in enumerate(top5):
            c_id = c.get("id", idx)
            c_name = c.get("username", f"用户{c_id}")
            c_tags = ", ".join(c.get("skill_tags", []))
            c_bio = c.get("bio", "")
            c_school = c.get("school", "")
            c_rerank = c.get("rerank_score", 0)
            top5_text += (
                f"候选人{idx+1}: id={c_id}, 用户名={c_name}, "
                f"技能=[{c_tags}], bio={c_bio}, 学校={c_school}, "
                f"Reranker评分={c_rerank:.3f}\n"
            )

        system_prompt = (
            "你是校园技能匹配专家。根据需求描述和候选人画像，为每位候选人写一句推荐理由。\n"
            "候选人已经按 Reranker 模型打分排序好了，你只需要为每人写推荐理由（≤25字）。\n"
            "说明为什么推荐此人，重点是技能匹配度和合作潜力。"
        )

        extra_know = f"\n技能知识库（关联技能）: {knowledge_context}" if knowledge_context else ""
        extra_mem = f"\n历史成功案例参考: {match_memory_context}" if match_memory_context else ""
        user_prompt = (
            f"需求: {need_description}\n"
            f"需求标签: {need_tags}{extra_know}{extra_mem}\n\n"
            f"已排序的Top 5候选人:\n{top5_text}\n\n"
            "返回 JSON 数组（直接输出，不要 markdown 代码块）:\n"
            '[{"user_id": <id>, "reason": "<≤25字>"}]\n'
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            reasons = await adapter.chat_with_json(
                messages,
                temperature=0.3,
                max_tokens=cfg["max_tokens"],
                timeout=8,
                max_retries=0,
            )
        except Exception:
            logger.exception("DeepSeek explanation failed, using fallback")
            reasons = []

        reason_map = {}
        if isinstance(reasons, list):
            for r in reasons:
                reason_map[r.get("user_id")] = r.get("reason", "技能高度匹配")

        # Normalize cross-encoder logits to 0-100 range
        raw_scores = [c.get("rerank_score", 0) for c in top5]
        min_s = min(raw_scores) if raw_scores else 0
        max_s = max(raw_scores) if raw_scores else 1
        score_range = max_s - min_s if max_s != min_s else 1

        results = []
        for c in top5:
            uid = c.get("id")
            raw = c.get("rerank_score", 0)
            normalized = int(((raw - min_s) / score_range) * 40 + 60)  # 60-100 range
            normalized = min(100, max(60, normalized))
            results.append({
                "user_id": uid,
                "score": normalized,
                "reason": reason_map.get(uid, "技能匹配度高"),
            })

        # Ensure first result is ~90-100
        if results:
            results[0]["score"] = max(90, results[0]["score"])

        return {"results": results}
