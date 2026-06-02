import logging
from typing import Any

import app.prompts.semantic_router  # noqa: F401
from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.prompts.registry import PromptRegistry
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

INTENTS = {"publish_need", "discover_needs", "refine_need", "view_matches", "upload_file", "chat"}
NEXT_ACTIONS = {
    "start_publish_follow_up",
    "recommend_existing_needs",
    "refine_need",
    "show_matches",
    "request_file_upload",
    "answer_chat",
    "safety_refuse",
}


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _is_discover_request(text: str) -> bool:
    discover_tokens = (
        "想找需求",
        "想找项目",
        "想加入",
        "想参与",
        "有没有需求",
        "有没有项目",
        "找黑客松",
        "找组队",
        "找现有",
        "现有的需求",
        "已有需求",
        "看看有没有",
    )
    if _contains_any(text, discover_tokens):
        return True
    discovery_markers = ("现有", "已有", "有没有", "加入", "参与")
    need_markers = ("需求", "项目", "组队", "队伍")
    return _contains_any(text, discovery_markers) and _contains_any(text, need_markers)


def _is_platform_identity_question(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
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
    return _contains_any(normalized, platform_markers) and _contains_any(normalized, identity_markers)


def _entities_from_text(text: str) -> list[str]:
    candidates = (
        "ACM",
        "acm",
        "ICPC",
        "icpc",
        "蓝桥杯",
        "黑客松",
        "算法",
        "前端",
        "后端",
        "建模",
        "路演",
        "大创",
    )
    entities: list[str] = []
    for item in candidates:
        if item in text and item.upper() not in {entity.upper() for entity in entities}:
            entities.append(item.upper() if item.lower() in {"acm", "icpc"} else item)
    return entities


def _next_action_for_intent(intent: str) -> str:
    return {
        "publish_need": "start_publish_follow_up",
        "discover_needs": "recommend_existing_needs",
        "refine_need": "refine_need",
        "view_matches": "show_matches",
        "upload_file": "request_file_upload",
        "chat": "answer_chat",
    }.get(intent, "answer_chat")


def _missing_information(intent: str, text: str) -> list[str]:
    if intent != "publish_need":
        return []
    missing: list[str] = []
    if not _contains_any(text, ("求助", "组队", "技能交换")):
        missing.append("需求类型")
    if len(text) < 12 and not _entities_from_text(text):
        missing.append("需求标题")
    if not _contains_any(text, ("会", "技能", "方向", "负责", "算法", "前端", "后端", "建模", "路演", "文档")):
        missing.append("技能或方向要求")
    if not _contains_any(text, ("单人", "多人", "一个人", "多位")):
        missing.append("选择人数模式")
    return missing


def _heuristic_route(message: str, user_context: str = "", file_context: str = "") -> dict[str, Any] | None:
    text = (message or "").strip()
    lowered = text.lower()
    if not text:
        intent = "chat"
        confidence = 0.2
        rationale = "空消息"
    elif _is_platform_identity_question(text):
        intent = "chat"
        confidence = 0.96
        rationale = "用户询问平台定位或特色"
    elif _contains_any(text, ("攻击", "泄露联系方式", "绕过权限", "盗号")):
        intent = "chat"
        confidence = 0.9
        rationale = "触发安全风险词"
        return _build_route(text, intent, confidence, rationale, safety_level="caution")
    elif _contains_any(text, ("上传", "文件", "附件", "文档")) or any(ext in lowered for ext in ("pdf", "docx", "txt")):
        intent = "upload_file"
        confidence = 0.95
        rationale = "用户提到文件处理"
    elif _is_discover_request(text):
        intent = "discover_needs"
        confidence = 0.95
        rationale = "用户想找已有机会"
    elif "我会" in text and _contains_any(text, ("想找", "想加入", "想参与", "有没有")):
        intent = "discover_needs"
        confidence = 0.88
        rationale = "技能自述后寻找机会"
    elif _contains_any(text, ("匹配", "候选", "人选", "推荐", "合适的人")):
        intent = "view_matches"
        confidence = 0.9
        rationale = "用户想查看匹配"
    elif _contains_any(text, ("优化", "润色", "改写", "细化", "完善")):
        intent = "refine_need"
        confidence = 0.88
        rationale = "用户想修改内容"
    elif _contains_any(text, ("发布", "帮我发", "创建", "招募", "招人", "求助", "找队友", "组队", "技能交换")):
        intent = "publish_need"
        confidence = 0.92
        rationale = "用户想创建新需求"
    else:
        return None
    return _build_route(text, intent, confidence, rationale, user_context=user_context, file_context=file_context)


def _build_route(
    text: str,
    intent: str,
    confidence: float,
    rationale: str,
    *,
    user_context: str = "",
    file_context: str = "",
    safety_level: str = "safe",
) -> dict[str, Any]:
    wants_existing = intent == "discover_needs"
    wants_create = intent == "publish_need"
    target_object = "普通问题"
    if intent in {"publish_need", "discover_needs", "refine_need"}:
        target_object = "需求"
    elif intent == "view_matches":
        target_object = "匹配"
    elif intent == "upload_file":
        target_object = "文件"
    return {
        "intent": intent,
        "confidence": confidence,
        "next_action": "safety_refuse" if safety_level == "block" else _next_action_for_intent(intent),
        "summary": text[:80],
        "semantic_frame": {
            "user_goal": text[:80],
            "target_object": target_object,
            "wants_existing": wants_existing,
            "wants_create": wants_create,
            "missing_information": _missing_information(intent, text),
            "entities": _entities_from_text(" ".join([text, user_context, file_context])),
        },
        "safety_level": safety_level,
        "rationale": rationale,
    }


def _normalize_route(result: dict[str, Any], message: str) -> dict[str, Any]:
    intent = str(result.get("intent") or "chat")
    if intent not in INTENTS:
        intent = "chat"
    next_action = str(result.get("next_action") or _next_action_for_intent(intent))
    if next_action not in NEXT_ACTIONS:
        next_action = _next_action_for_intent(intent)
    confidence = result.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5
    semantic_frame = result.get("semantic_frame") if isinstance(result.get("semantic_frame"), dict) else {}
    return {
        "intent": intent,
        "confidence": max(0.0, min(1.0, confidence)),
        "next_action": next_action,
        "summary": str(result.get("summary") or message[:80]),
        "semantic_frame": {
            "user_goal": str(semantic_frame.get("user_goal") or message[:80]),
            "target_object": str(semantic_frame.get("target_object") or "普通问题"),
            "wants_existing": bool(semantic_frame.get("wants_existing", intent == "discover_needs")),
            "wants_create": bool(semantic_frame.get("wants_create", intent == "publish_need")),
            "missing_information": list(semantic_frame.get("missing_information") or []),
            "entities": list(semantic_frame.get("entities") or _entities_from_text(message)),
        },
        "safety_level": str(result.get("safety_level") or "safe"),
        "rationale": str(result.get("rationale") or ""),
    }


class SemanticRouterSkill(BaseSkill):
    name = "semantic_router"
    description = "Self-reason over a user message and route the Agent to the correct next action."
    version = "1.0.0"
    tags = ["prompt-engineering", "agent", "routing", "safety"]
    input_schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "user_context": {"type": "string"},
            "file_context": {"type": "string"},
        },
        "required": ["message"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "confidence": {"type": "number"},
            "next_action": {"type": "string"},
            "summary": {"type": "string"},
            "semantic_frame": {"type": "object"},
            "safety_level": {"type": "string"},
            "rationale": {"type": "string"},
        },
    }

    async def execute(self, input_data: dict) -> dict:
        message = str(input_data.get("message") or "")
        user_context = str(input_data.get("user_context") or "")
        file_context = str(input_data.get("file_context") or "")

        heuristic = _heuristic_route(message, user_context, file_context)
        if heuristic is not None:
            return heuristic

        client = get_ai_client()
        cfg = route("intent_analysis")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])
        messages = PromptRegistry.render(
            "semantic_router",
            {
                "message": message,
                "user_context": user_context[:500],
                "file_context": file_context[:500],
            },
        )
        try:
            result = await adapter.chat_with_json(
                messages,
                temperature=cfg["temperature"],
                max_tokens=600,
            )
            return _normalize_route(result, message)
        except Exception:
            logger.exception("Semantic routing failed")
            return _build_route(message, "chat", 0.3, "语义路由失败，回退普通聊天")
