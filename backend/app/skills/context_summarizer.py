from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.skills.base import BaseSkill


class ContextSummarizerSkill(BaseSkill):
    name = "context_summarizer"
    description = "对长对话历史进行摘要压缩"
    version = "1.0.0"

    async def execute(self, input_data: dict) -> dict:
        messages = input_data["messages"]

        text = ""
        for m in messages:
            role = "用户" if m.get("role") == "user" else "助手"
            text += f"{role}: {m.get('content', '')}\n"

        client = get_ai_client()
        cfg = route("summarization")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        prompt = (
            "请将以下对话总结为一段200-400字的紧凑摘要，保留关键信息：\n"
            "- 用户的核心目标和需求\n- 已确认的细节\n- 已完成的步骤\n"
            "- 待处理的事项\n\n对话:\n" + text
        )

        messages_list = [{"role": "user", "content": prompt}]
        try:
            summary = await adapter.chat(messages_list, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
            return {"summary": summary.strip(), "success": True}
        except Exception:
            return {"summary": text[-400:], "success": False}
