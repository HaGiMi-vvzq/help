from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.skills.base import BaseSkill


class FileReaderSkill(BaseSkill):
    name = "file_reader"
    description = "从上传文件的文本内容中提取关键信息"
    version = "1.0.0"

    async def execute(self, input_data: dict) -> dict:
        text = input_data["text"][:8000]
        filename = input_data.get("filename", "")

        client = get_ai_client()
        cfg = route("file_analysis")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        system = (
            "你是文件分析助手。从用户上传的文件中提取关键信息，"
            "结构化输出。关注：活动/比赛名称、主题领域、所需技能、"
            "截止日期、合作要求、奖励/成果、适合发布到平台的匹配需求。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"文件名: {filename}\n\n文件内容:\n{text}\n\n请提取关键信息，返回JSON：{{\"title\":\"赛事/活动名称\",\"category\":\"比赛/课程项目/创业/其他\",\"skills_needed\":[\"技能1\",\"技能2\"],\"deadline\":\"截止日期或空\",\"summary\":\"简要概括\",\"potential_needs\":[{{\"type\":\"求助/组队/技能交换\",\"title\":\"需求标题\",\"description\":\"需求描述\"}}]}}"},
        ]

        try:
            result = await adapter.chat_with_json(messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
            return {"extracted": result, "success": True}
        except Exception:
            return {"extracted": {"title": filename, "summary": text[:200]}, "success": False, "fallback": True}
