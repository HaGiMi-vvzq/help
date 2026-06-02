import logging

from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.agents.base import BaseAgent
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


def is_discover_need_request(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False

    discover_tokens = (
        "\u60f3\u627e\u9700\u6c42",
        "\u60f3\u627e\u9879\u76ee",
        "\u60f3\u52a0\u5165",
        "\u60f3\u53c2\u4e0e",
        "\u6709\u6ca1\u6709\u9700\u6c42",
        "\u6709\u6ca1\u6709\u9879\u76ee",
        "\u627e\u9ed1\u5ba2\u677e",
        "\u627e\u7ec4\u961f",
        "\u627e\u73b0\u6709",
        "\u73b0\u6709\u7684\u9700\u6c42",
        "\u5df2\u6709\u9700\u6c42",
        "\u770b\u770b\u6709\u6ca1\u6709",
    )
    if any(token in text for token in discover_tokens):
        return True

    discovery_intent_markers = ("\u73b0\u6709", "\u5df2\u6709", "\u6709\u6ca1\u6709", "\u52a0\u5165", "\u53c2\u4e0e")
    need_markers = ("\u9700\u6c42", "\u9879\u76ee", "\u7ec4\u961f", "\u961f\u4f0d")
    return any(token in text for token in discovery_intent_markers) and any(
        token in text for token in need_markers
    )


def _is_platform_identity_question(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    platform_markers = ("平台", "产品", "系统", "项目", "agent", "ai", "你")
    identity_markers = (
        "一句话",
        "总结",
        "能做什么",
        "最大特色",
        "特色",
        "亮点",
        "价值",
        "优势",
        "区别",
        "介绍",
        "定位",
    )
    return any(marker in text for marker in platform_markers) and any(marker in text for marker in identity_markers)


def _heuristic_intent(message: str) -> tuple[str, float, str] | None:
    text = (message or "").strip()
    lowered = text.lower()
    if not text:
        return ("chat", 0.2, "empty_message")
    if _is_platform_identity_question(text):
        return ("chat", 0.96, "platform_identity_question")

    publish_tokens = ("\u53d1\u5e03", "\u9700\u6c42", "\u7ec4\u961f", "\u62db\u52df", "\u62db\u4eba", "\u6c42\u52a9", "\u627e\u961f\u53cb", "\u6280\u80fd\u4ea4\u6362")
    match_tokens = ("\u5339\u914d", "\u5019\u9009", "\u4eba\u9009", "\u63a8\u8350", "\u5408\u9002\u7684\u4eba")
    upload_tokens = ("\u4e0a\u4f20", "\u6587\u4ef6", "\u9644\u4ef6", "pdf", "docx", "txt", "\u6587\u6863")
    refine_tokens = ("\u4f18\u5316", "\u6da6\u8272", "\u6539\u5199", "\u7ec6\u5316", "\u5b8c\u5584")
    if any(token in text for token in upload_tokens):
        return ("upload_file", 0.95, "keyword_upload")
    if is_discover_need_request(text):
        return ("discover_needs", 0.95, "keyword_discover")
    if "我会" in text and any(token in text for token in ("想找", "想加入", "想参与", "有没有")):
        return ("discover_needs", 0.88, "skill_based_discover")
    if any(token in text for token in match_tokens):
        return ("view_matches", 0.92, "keyword_matches")
    if any(token in text for token in refine_tokens):
        return ("refine_need", 0.9, "keyword_refine")
    if any(token in text for token in publish_tokens):
        return ("publish_need", 0.94, "keyword_publish")
    if lowered.startswith("/plan") or "\u8ba1\u5212" in text:
        return ("refine_need", 0.7, "keyword_plan")
    return None


class IntentAnalyzerAgent(BaseAgent):
    name = "IntentAnalyzerAgent"
    description = "Analyze user intent and route the next agent action."

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        await self.think("Analyzing user intent...")

        message = input_data.get("message", "")
        extracted = input_data.get("extracted_info")
        user_context = input_data.get("user_context", "")

        try:
            semantic_router = SkillRegistry.get("semantic_router")
            result = await semantic_router.execute(
                {
                    "message": message,
                    "user_context": user_context,
                    "file_context": str(extracted or ""),
                }
            )
            return {
                "intent": result.get("intent", "chat"),
                "confidence": result.get("confidence", 0.5),
                "summary": result.get("summary", ""),
                "next_action": result.get("next_action"),
                "semantic_frame": result.get("semantic_frame"),
                "safety_level": result.get("safety_level"),
                "rationale": result.get("rationale"),
            }
        except KeyError:
            logger.warning("semantic_router skill is not registered; falling back to built-in intent analyzer")
        except Exception:
            logger.exception("Semantic router failed; falling back to built-in intent analyzer")

        heuristic = _heuristic_intent(message)
        if heuristic is not None:
            intent, confidence, summary = heuristic
            return {"intent": intent, "confidence": confidence, "summary": summary}

        client = get_ai_client()
        cfg = route("intent_analysis")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        ctx_parts = []
        if isinstance(extracted, dict):
            title = extracted.get("title", "")
            summary = extracted.get("summary", "")
            ctx_parts.append(f"Extracted file info: {title} - {summary}")
            if extracted.get("potential_needs"):
                ctx_parts.append(f"Potential needs: {len(extracted['potential_needs'])}")
        if user_context:
            ctx_parts.append(f"User context: {user_context[:200]}")

        ctx_str = "; ".join(ctx_parts) if ctx_parts else "no extra context"
        system = (
            "You classify the user's intent. "
            "Return one of: publish_need, refine_need, view_matches, upload_file, discover_needs, chat. "
            "Output JSON: {intent, confidence, summary}."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"User message: {message}\nContext: {ctx_str}"},
        ]

        try:
            result = await adapter.chat_with_json(
                messages,
                temperature=cfg["temperature"],
                max_tokens=cfg["max_tokens"],
            )
            return {
                "intent": result.get("intent", "chat"),
                "confidence": result.get("confidence", 0.5),
                "summary": result.get("summary", ""),
            }
        except Exception:
            logger.exception("Intent analysis failed")
            return {"intent": "chat", "confidence": 0.3, "summary": ""}
