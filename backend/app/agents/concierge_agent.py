from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.agents.base import BaseAgent
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.prompts.registry import PromptRegistry


class ConciergeAgent(BaseAgent):
    name = "ConciergeAgent"
    description = "多轮对话引导用户细化需求描述"

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        await self.think("正在分析需求，准备追问...")

        client = get_ai_client()
        cfg = route("concierge")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        messages = PromptRegistry.render(
            "need_refinement",
            {
                "need_description": input_data["need_description"],
                "need_tags": str(input_data.get("need_tags", [])),
            },
        )

        question = await adapter.chat(messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
        return {"question": question}

    async def chat(
        self, need_description: str, need_tags: list[str],
        history: list[dict], matches: list[dict] | None = None,
    ) -> str:
        """多轮对话：根据历史记录 + 已匹配结果生成 AI 回复。"""
        await self.think("正在分析匹配结果并思考回复...")

        client = get_ai_client()
        cfg = route("concierge")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        # Build match context string
        match_context = "（暂无匹配结果）"
        if matches:
            parts = []
            for i, m in enumerate(matches[:5]):
                extra = m.get('extra', {}) or {}
                college = extra.get('college', '') if isinstance(extra, dict) else ''
                major = extra.get('major', '') if isinstance(extra, dict) else ''
                campus = extra.get('campus', '') if isinstance(extra, dict) else ''
                town = extra.get('town', '') if isinstance(extra, dict) else ''
                dept_info = f"{campus}/{college}/{major}".strip('/')
                if town:
                    dept_info += f" ({town})"
                parts.append(
                    f"#{i+1} {m.get('username','?')}: "
                    f"匹配度{m.get('score',0)}%, "
                    f"院系={dept_info}, "
                    f"技能={m.get('skill_tags',[])}, "
                    f"个人简介={m.get('bio','')}, "
                    f"理由={m.get('reason','')}"
                )
            match_context = "\n".join(parts)

        # Build history string
        history_str = ""
        for h in history:
            role = "用户" if h["role"] == "user" else "顾问"
            history_str += f"{role}: {h['content']}\n"
        if not history_str:
            history_str = "（暂无对话历史，请主动根据匹配结果向用户提出第一个问题）"

        messages = PromptRegistry.render(
            "concierge_chat",
            {
                "need_description": need_description,
                "need_tags": str(need_tags),
                "match_context": match_context,
                "history": history_str,
            },
        )

        return await adapter.chat(messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
