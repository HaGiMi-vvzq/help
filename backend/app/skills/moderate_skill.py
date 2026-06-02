from app.skills.base import BaseSkill


class ModerateSkill(BaseSkill):
    name = "content_moderation"
    description = "检测用户输入是否包含敏感内容或越狱提示"
    version = "1.0.0"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {"safe": {"type": "boolean"}, "reason": {"type": "string"}},
    }
    tags = ["safety", "moderation"]

    JAILBREAK_PATTERNS = [
        "忽略之前的指令",
        "ignore previous instructions",
        "you are now DAN",
        "你现在是",
        "假装你是",
        "pretend you are",
        "不要输出",
        "do not output",
        "system prompt",
        "<|im_start|>",
    ]

    async def execute(self, input_data: dict) -> dict:
        text = input_data["text"].lower()

        for pattern in self.JAILBREAK_PATTERNS:
            if pattern.lower() in text:
                return {"safe": False, "reason": f"检测到潜在的提示注入模式"}

        if len(text) > 5000:
            return {"safe": False, "reason": "输入过长"}

        return {"safe": True, "reason": ""}
