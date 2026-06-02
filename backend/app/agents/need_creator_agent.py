import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.agents.base import BaseAgent
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.models.user import User

logger = logging.getLogger(__name__)


class NeedCreatorAgent(BaseAgent):
    name = "NeedCreatorAgent"
    description = "根据分析结果自动创建和发布需求"

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        await self.think("正在创建需求...")

        extracted = input_data.get("extracted_info", {})
        user: User = input_data["user"]
        db: AsyncSession = input_data["db"]

        # Draft needs from extracted info
        client = get_ai_client()
        cfg = route("agent_chat")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        system = (
            "你是需求创建助手。根据文件分析结果和用户确认，生成平台需求发布表单。\n"
            "输出JSON数组: [{type: 求助/组队/技能交换, title, description, selection_mode: single/multi}]。"
        )
        user_prompt = (
            f"提取信息: {extracted}\n"
            f"用户技能: {user.skill_tags or '未知'}\n"
            f"用户学校: {user.school or '未知'}\n\n"
            "请生成需求草稿JSON数组。"
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        try:
            drafts = await adapter.chat_with_json(messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
        except Exception:
            logger.exception("Need draft generation failed")
            drafts = [{"type": "组队", "title": extracted.get("title", "新需求"), "description": extracted.get("summary", ""), "selection_mode": "single"}]

        if isinstance(drafts, dict):
            drafts = [drafts]
        if not isinstance(drafts, list) or not drafts:
            drafts = [{"type": "组队", "title": extracted.get("title", "新需求"), "description": extracted.get("summary", "自动生成的需求"), "selection_mode": "single"}]

        return {"drafts": drafts, "count": len(drafts)}
