from app.agents.base import BaseAgent


class TagExtractionAgent(BaseAgent):
    name = "TagExtractionAgent"
    description = "从自然语言文本中提取结构化技能标签"

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        await self.think("正在提取技能标签...")

        moderate = self.use_skill("content_moderation")
        mod_result = await moderate.execute({"text": input_data["text"]})
        if not mod_result["safe"]:
            return {"tags": [], "safe": False, "reason": mod_result["reason"]}

        tag_skill = self.use_skill("tag_extraction")
        result = await tag_skill.execute({"text": input_data["text"]})
        result["safe"] = True
        return result
