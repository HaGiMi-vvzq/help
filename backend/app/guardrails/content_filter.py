class ContentFilter:
    SENSITIVE_PATTERNS = [
        "忽略之前的指令", "ignore previous instructions", "you are now DAN",
        "你现在是", "假装你是", "pretend you are",
        "<|im_start|>", "<|im_end|>",
    ]

    @classmethod
    async def check_input(cls, text: str) -> tuple[bool, str]:
        if not text or not text.strip():
            return False, "输入不能为空"
        if len(text) > 5000:
            return False, "输入过长"

        lower = text.lower()
        for p in cls.SENSITIVE_PATTERNS:
            if p.lower() in lower:
                return False, "输入包含不适当内容"

        return True, ""

    @classmethod
    async def llm_moderate(cls, text: str) -> tuple[bool, str]:
        """使用 DeepSeek Flash 进行 LLM 级内容审核。"""
        from app.adapters.deepseek_adapter import DeepSeekChatAdapter
        from app.integrations.client import get_ai_client
        from app.integrations.model_router import route

        client = get_ai_client()
        cfg = route("moderation")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        messages = [
            {"role": "system", "content": (
                "你是内容审核助手。判断用户输入是否包含以下不适当内容：\n"
                "1. 广告/垃圾信息 2. 人身攻击/骚扰 3. 色情内容 4. 违法信息 5. 无关内容\n"
                '输出纯 JSON: {"safe": true/false, "reason": "简短原因（安全时为空）"}'
            )},
            {"role": "user", "content": f"审核此内容: {text}"},
        ]

        try:
            result = await adapter.chat_with_json(
                messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"]
            )
            if isinstance(result, dict) and "safe" in result:
                return result.get("safe", True), result.get("reason", "")
            return True, ""
        except Exception:
            # fail-closed: 审核不可用时拒绝内容，防止未经审核的内容通过
            return False, "审核服务暂时不可用"
