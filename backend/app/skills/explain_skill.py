from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.skills.base import BaseSkill


class ExplainSkill(BaseSkill):
    name = "explain_recommendation"
    description = "为匹配结果生成打分和推荐理由"
    version = "1.0.0"
    input_schema = {
        "type": "object",
        "properties": {
            "need_description": {"type": "string"},
            "need_tags": {"type": "array", "items": {"type": "string"}},
            "candidates": {"type": "array", "items": {"type": "object"}},
            "knowledge_context": {"type": "string", "default": ""},
            "match_memory_context": {"type": "string", "default": ""},
        },
        "required": ["need_description", "need_tags", "candidates"],
    }
    output_schema = {
        "type": "object",
        "properties": {"results": {"type": "array", "items": {"type": "object"}}},
    }
    tags = ["nlp", "ranking", "explanation"]

    async def execute(self, input_data: dict) -> dict:
        need_description = input_data["need_description"]
        need_tags = input_data["need_tags"]
        candidates = input_data["candidates"]
        knowledge_context = input_data.get("knowledge_context", "")
        match_memory = input_data.get("match_memory_context", "")

        client = get_ai_client()
        cfg = route("rerank")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        candidates_text = ""
        for idx, c in enumerate(candidates):
            c_id = c.get("id", idx)
            c_name = c.get("username", f"候选人{idx}")
            c_tags = ", ".join(c.get("skill_tags", []))
            c_bio = c.get("bio", "")
            c_school = c.get("school", "")
            candidates_text += f"候选人{idx+1}: id={c_id}, 用户名={c_name}, 技能=[{c_tags}], bio={c_bio}, 学校={c_school}, 向量相似度={c.get('similarity', 0)}\n"

        system_prompt = (
            "你是校园技能匹配专家。基于需求与候选人画像的语义关联度、技能互补性和协作潜力，"
            "为每位候选人打分并给出推荐理由。\n"
            "分析步骤：① 对比需求标签与候选人技能的重合度 "
            "② 检查候选人的经验相关性 ③ 评估双方是否互补 ④ 综合打分（0-100）"
        )

        user_prompt = (
            f"需求描述: {need_description}\n"
            f"需求标签: {need_tags}\n"
            f"技能知识库上下文: {knowledge_context}\n"
            f"历史相似成功案例: {match_memory}\n\n"
            f"候选人列表:\n{candidates_text}\n\n"
            "请返回 JSON 数组（直接输出，不要 markdown 代码块）: "
            '[{"user_id": <id>, "score": <0-100>, "reason": "<≤25字>", "complementarity": "<互补点>"}]\n'
            "只输出 Top 5。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        results = await adapter.chat_with_json(messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
        if isinstance(results, list):
            return {"results": results}
        if isinstance(results, dict) and "results" in results:
            return {"results": results["results"]}
        return {"results": []}
