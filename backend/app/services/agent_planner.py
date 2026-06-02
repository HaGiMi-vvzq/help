"""Agent planner/orchestrator helpers for chat, upload, planning, publish, and discovery flows."""

import asyncio
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.intent_analyzer_agent import IntentAnalyzerAgent, is_discover_need_request
from app.agents.planner_agent import PlannerAgent
from app.models.user import User
from app.services import (
    agent_executor,
    agent_memory,
    agent_service,
    need_discovery_service,
)
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)
_publish_inflight_sessions: set[int] = set()

_AGENT_TO_TASK_TYPE: dict[str, str] = {
    "FileReaderAgent": "analyze_file",
    "IntentAnalyzerAgent": "intent_analysis",
    "NeedCreatorAgent": "draft_need",
    "MatchWatcherAgent": "run_matching",
    "ConciergeAgent": "refine_need",
    "RerankAgent": "rerank_matches",
}

FOLLOW_UP_FIELDS = ("type", "title", "description", "requirements", "selection_mode")
PUBLISH_CONFIRM_TOKENS = (
    "\u53d1\u5e03",
    "\u786e\u8ba4\u53d1\u5e03",
    "\u5c31\u8fd9\u4e2a\uff0c\u53d1\u5e03",
    "\u53ef\u4ee5\u53d1\u5e03",
    "\u5e2e\u6211\u53d1\u5e03",
)
FOLLOW_UP_OPTION_MAP: dict[str, list[dict[str, str]]] = {
    "type": [
        {"label": "\u6c42\u52a9", "value": "\u6c42\u52a9"},
        {"label": "\u7ec4\u961f", "value": "\u7ec4\u961f"},
        {"label": "\u6280\u80fd\u4ea4\u6362", "value": "\u6280\u80fd\u4ea4\u6362"},
    ],
    "selection_mode": [
        {"label": "\u5355\u4eba", "value": "\u5355\u4eba"},
        {"label": "\u591a\u4eba", "value": "\u591a\u4eba"},
    ],
}


def _normalize_need_type(text: str) -> str | None:
    lowered = text.strip().lower()
    if any(token in text for token in ("\u6c42\u52a9", "\u5e2e\u5fd9", "\u534f\u52a9")):
        return "\u6c42\u52a9"
    if any(token in text for token in ("\u7ec4\u961f", "\u961f\u53cb", "\u62db\u4eba")):
        return "\u7ec4\u961f"
    if any(token in text for token in ("\u6280\u80fd\u4ea4\u6362", "\u4e92\u6362", "\u4ea4\u6362")):
        return "\u6280\u80fd\u4ea4\u6362"
    if lowered in {"single", "multi"}:
        return text.strip()
    return None


def _normalize_selection_mode(text: str) -> str | None:
    if any(token in text for token in ("\u591a\u4eba", "\u591a\u4f4d", "\u591a\u4e2a")):
        return "multi"
    if any(token in text for token in ("\u5355\u4eba", "1\u4eba", "\u4e00\u4e2a\u4eba", "\u53ea\u8981\u4e00\u4e2a")):
        return "single"
    normalized = text.strip().lower()
    if normalized in {"single", "multi"}:
        return normalized
    return None


def collect_need_follow_up(message: str, state: dict | None) -> dict:
    state = dict(state or {})
    collected = dict(state.get("collected") or {})
    pending_field = state.get("pending_field")
    text = message.strip()

    if not collected.get("description"):
        collected["description"] = text

    if pending_field == "type":
        collected["type"] = _normalize_need_type(text) or text
    elif pending_field == "title":
        collected["title"] = text
    elif pending_field == "description":
        collected["description"] = text
    elif pending_field == "requirements":
        selection_mode = _normalize_selection_mode(text)
        if selection_mode:
            collected["selection_mode"] = selection_mode
        else:
            collected["requirements"] = text
    elif pending_field == "selection_mode":
        collected["selection_mode"] = _normalize_selection_mode(text) or "single"
    else:
        collected["type"] = collected.get("type") or _normalize_need_type(text)
        collected["selection_mode"] = collected.get("selection_mode") or _normalize_selection_mode(text)

    missing_fields = [field for field in FOLLOW_UP_FIELDS if not str(collected.get(field) or "").strip()]
    if "selection_mode" in missing_fields and collected.get("selection_mode") in {"single", "multi"}:
        missing_fields.remove("selection_mode")

    next_field = missing_fields[0] if missing_fields else None
    return {
        "intent": "publish_need",
        "collected": collected,
        "missing_fields": missing_fields,
        "pending_field": next_field,
        "task_id": state.get("task_id"),
    }


def get_follow_up_question(state: dict) -> str:
    field = state.get("pending_field")
    if field == "type":
        return "你想发布哪一种需求类型？回复“求助”“组队”或“技能交换”。"
    if field == "title":
        return "给这个需求起一个简短标题。"
    if field == "description":
        return "补充一下需求描述，说明要做什么、希望对方怎样参与。"
    if field == "requirements":
        return "你希望队友具备哪些技能或负责哪些方向？例如算法、前端、建模、文档、路演。"
    if field == "selection_mode":
        return "你希望只选 1 人还是允许多人参与？回复“单人”或“多人”。"
    return "我已经拿到关键信息，可以生成需求草稿了。"


def _build_follow_up_metadata(state: dict) -> dict:
    field = state.get("pending_field")
    metadata = {
        "type": "follow_up",
        "follow_up_field": field,
    }
    options = FOLLOW_UP_OPTION_MAP.get(str(field))
    if options:
        metadata["options"] = options
    return metadata


def _is_publish_confirmation(message: str) -> bool:
    text = (message or "").strip()
    return bool(text) and any(token in text for token in PUBLISH_CONFIRM_TOKENS)


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


def _platform_identity_reply(message: str) -> str:
    text = (message or "").strip()
    if "区别" in text or "优势" in text:
        return "我不是普通的需求发布栏，而是用 AI 理解意图、补全需求、语义匹配队友，并把申请和沟通串成闭环的校园协作撮合平台。"
    if "最大特色" in text or "特色" in text or "亮点" in text:
        return "我的最大特色是把 AI 从“写文案”推进到“撮合协作”：帮你澄清需求、匹配合适的人，也能反向发现适合你加入的机会。"
    return "这是一个用 AI 把校园里的需求、技能和同学连接起来的平台，能帮你发布协作需求、智能匹配队友，并推动双方进入申请和沟通。"


def _get_pending_drafts(planning_state: dict | None) -> list[dict]:
    raw = (planning_state or {}).get("pending_drafts")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _draft_item_signature(draft: dict) -> str:
    return json.dumps(draft, ensure_ascii=False, sort_keys=True)


def _split_selected_and_remaining_drafts(pending_drafts: list[dict], selected_drafts: list[dict]) -> tuple[list[dict], list[dict]]:
    if not selected_drafts:
        raise ValueError("select at least one draft")

    selected: list[dict] = []
    remaining = list(pending_drafts)
    for draft in selected_drafts:
        signature = _draft_item_signature(draft)
        match_index = next(
            (index for index, pending in enumerate(remaining) if _draft_item_signature(pending) == signature),
            None,
        )
        if match_index is None:
            raise ValueError("draft no longer pending")
        selected.append(remaining.pop(match_index))
    return selected, remaining


def _fallback_chat_reply(message: str, file_info: str) -> str:
    text = (message or "").strip()
    if _is_platform_identity_question(text):
        return _platform_identity_reply(text)
    if any(token in text for token in ("\u60f3\u627e\u9700\u6c42", "\u60f3\u52a0\u5165", "\u6709\u6ca1\u6709\u9879\u76ee", "\u60f3\u53c2\u4e0e")):
        return "可以。我会结合你的技能背景去找现有开放需求，并推荐更适合进一步沟通的项目。"
    if any(token in text for token in ("\u4e0a\u4f20", "\u9644\u4ef6", "\u6587\u6863", "pdf", "docx", "txt")):
        return "可以，直接上传 txt、docx 或 pdf。我会先提取要点，再帮你整理需求草稿。"
    if any(token in text for token in ("\u53d1\u5e03", "\u9700\u6c42", "\u7ec4\u961f", "\u6c42\u52a9", "\u627e\u961f\u53cb", "\u6280\u80fd\u4ea4\u6362")):
        return "可以。我先帮你整理成需求草稿；如果信息还不够，我会继续追问标题、描述和人数方式。"
    if file_info:
        return "我已经拿到文件上下文了。你可以直接说“帮我发布需求”或“帮我优化这条需求”。"
    if any(token in text for token in ("\u5339\u914d", "\u5019\u9009", "\u63a8\u8350", "\u4eba\u9009")):
        return "你可以去匹配结果页看候选人；如果愿意，我也可以继续帮你起草第一条联系消息。"
    return "我现在可以帮你分析文件、整理需求草稿、发布需求、起草联系消息，或者反向帮你查找合适的开放需求。"


def _fallback_draft_message(
    need_title: str,
    match_name: str,
    match_skills: list[str],
    match_reason: str,
    user_name: str,
) -> str:
    skills_text = ", ".join([skill for skill in match_skills if skill]) or "relevant skills"
    reason_text = match_reason.strip() if match_reason else f"{match_name} looks aligned with this need"
    return (
        f"Hi {match_name}, I am {user_name}. "
        f"I am working on {need_title}. I noticed your background includes {skills_text}, "
        f"and {reason_text}. If you are interested, let's discuss roles and timing."
    )


def _fallback_application_message(
    need_title: str,
    owner_name: str,
    user_name: str,
    user_skills: list[str],
    match_reason: str,
) -> str:
    skills_text = ", ".join([skill for skill in user_skills if skill]) or "relevant skills"
    reason_text = match_reason.strip() or "my background seems aligned with this need"
    return (
        f"Hi {owner_name or ''}, I am {user_name}. "
        f"I am interested in {need_title} and can contribute with {skills_text}. "
        f"{reason_text}. If it sounds suitable, I would love to discuss how I can join."
    ).strip()


async def handle_chat_message(
    db: AsyncSession,
    session_id: int,
    message: str,
    user: User,
    event_bus=None,
) -> dict:
    await agent_service.add_message(db, session_id, "user", message)
    session = await agent_service.get_session(db, session_id)
    planning_state = dict(session.planning_state or {}) if session else {}
    follow_up_state = planning_state.get("follow_up")

    if isinstance(follow_up_state, dict):
        return await _handle_follow_up_message(db, session_id, message, follow_up_state, user, event_bus)

    pending_drafts = _get_pending_drafts(planning_state)
    if pending_drafts and _is_publish_confirmation(message):
        result = await handle_confirm_publish(db, session_id, pending_drafts, user, event_bus)
        result["intent"] = "publish_need"
        return result

    ctx_mgr = agent_memory.ContextManager(db)
    ctx = await ctx_mgr.get_chat_context(session_id)
    user_context = await ctx_mgr.load_user_memory(user.id)

    intent_agent = IntentAnalyzerAgent()
    intent_result = await intent_agent.execute({"message": message, "user_context": user_context})
    intent = intent_result.get("intent", "chat")

    file_info = ""
    if ctx.get("file_context") and ctx["file_context"] != "（无上传文件）":
        file_info = ctx["file_context"]

    if intent == "publish_need" and not file_info:
        next_state = collect_need_follow_up(message, None)
        waiting_task = await agent_service.create_task(
            db,
            session_id,
            "补充需求信息后生成草稿",
            agent="NeedCreatorAgent",
            task_type="draft_need",
            input_data={"follow_up": next_state["collected"]},
        )
        await agent_service.update_task(db, waiting_task.id, "waiting_user")
        next_state["task_id"] = waiting_task.id
        await agent_service.update_session_planning_state(db, session_id, {"follow_up": next_state})
        reply = get_follow_up_question(next_state)
        metadata = _build_follow_up_metadata(next_state)
        await agent_service.add_message(db, session_id, "assistant", reply, extra_metadata=metadata)
        return {
            "reply": reply,
            "intent": intent,
            "drafts": None,
            "need_recommendations": None,
            "message_role": "assistant",
            "message_metadata": metadata,
        }

    if intent == "discover_needs":
        recommendations = await need_discovery_service.recommend_needs_for_user(db, user, message)
        if recommendations:
            reply = "我结合你的技能背景找到了一些更适合主动沟通的开放需求。你可以先查看需求详情，再决定是否申请加入。"
            await agent_service.add_message(
                db,
                session_id,
                "assistant",
                reply,
                extra_metadata={"type": "need_recommendations", "need_recommendations": recommendations},
            )
            return {
                "reply": reply,
                "intent": intent,
                "drafts": None,
                "need_recommendations": recommendations,
                "message_role": "assistant",
                "message_metadata": {"type": "need_recommendations", "need_recommendations": recommendations},
            }
        reply = "我暂时没有找到特别贴合的开放需求。你可以补充想做的方向、技能或时间安排，我再帮你缩小范围。"
        await agent_service.add_message(db, session_id, "assistant", reply)
        return {
            "reply": reply,
            "intent": intent,
            "drafts": None,
            "need_recommendations": [],
            "message_role": "assistant",
            "message_metadata": None,
        }

    reply = await _generate_chat_reply(message, user_context, ctx, file_info)
    await agent_service.add_message(db, session_id, "assistant", reply)

    drafts = None
    if intent == "publish_need":
        latest_file = await _get_latest_file(db, session_id)
        if latest_file and latest_file.extracted_info:
            task = await agent_service.create_task(
                db,
                session_id,
                "根据文件生成需求草稿",
                agent="NeedCreatorAgent",
                task_type="draft_need",
                input_data={"file_id": latest_file.id},
                file_id=latest_file.id,
            )
            executed = await agent_executor.execute_task(db, task.id, user=user, event_bus=event_bus)
            drafts = (executed.result or {}).get("drafts") if executed and executed.result else None
    if drafts:
        await agent_service.update_session_planning_state(db, session_id, {"pending_drafts": drafts})

    return {
        "reply": reply,
        "intent": intent,
        "drafts": drafts,
        "need_recommendations": None,
        "message_role": "assistant",
        "message_metadata": {"drafts": drafts} if drafts else None,
    }


async def _handle_follow_up_message(
    db: AsyncSession,
    session_id: int,
    message: str,
    follow_up_state: dict,
    user: User,
    event_bus=None,
) -> dict:
    if is_discover_need_request(message):
        await agent_service.update_session_planning_state(db, session_id, {"follow_up": None})
        collected = follow_up_state.get("collected") if isinstance(follow_up_state, dict) else {}
        prior_context = ""
        if isinstance(collected, dict):
            prior_context = " ".join(str(value) for value in collected.values() if value)
        discovery_query = " ".join(part for part in (prior_context, message) if part).strip() or message
        recommendations = await need_discovery_service.recommend_needs_for_user(db, user, discovery_query)
        metadata = {"type": "need_recommendations", "need_recommendations": recommendations}
        if recommendations:
            reply = "我结合你的技能背景找到了一些更适合主动沟通的开放需求。你可以先查看需求详情，再决定是否申请加入。"
        else:
            reply = "我暂时没有找到特别贴合的开放需求。你可以补充想做的方向、技能或时间安排，我再帮你缩小范围。"
            metadata = None
        await agent_service.add_message(db, session_id, "assistant", reply, extra_metadata=metadata)
        return {
            "reply": reply,
            "intent": "discover_needs",
            "drafts": None,
            "need_recommendations": recommendations,
            "message_role": "assistant",
            "message_metadata": metadata,
        }

    if _is_publish_confirmation(message) and follow_up_state.get("missing_fields"):
        reply = get_follow_up_question(follow_up_state)
        metadata = _build_follow_up_metadata(follow_up_state)
        await agent_service.add_message(db, session_id, "assistant", reply, extra_metadata=metadata)
        return {
            "reply": reply,
            "intent": "publish_need",
            "drafts": None,
            "need_recommendations": None,
            "message_role": "assistant",
            "message_metadata": metadata,
        }

    next_state = collect_need_follow_up(message, follow_up_state)
    if next_state["missing_fields"]:
        waiting_task_id = int(next_state.get("task_id") or 0)
        if waiting_task_id:
            await agent_service.update_task_input_data(db, waiting_task_id, {"follow_up": next_state["collected"]})
        await agent_service.update_session_planning_state(db, session_id, {"follow_up": next_state})
        reply = get_follow_up_question(next_state)
        metadata = _build_follow_up_metadata(next_state)
        await agent_service.add_message(db, session_id, "assistant", reply, extra_metadata=metadata)
        return {
            "reply": reply,
            "intent": "publish_need",
            "drafts": None,
            "need_recommendations": None,
            "message_role": "assistant",
            "message_metadata": metadata,
        }

    waiting_task_id = int(next_state.get("task_id") or 0)
    if waiting_task_id:
        await agent_service.update_task_input_data(db, waiting_task_id, {"follow_up": next_state["collected"]})
        await agent_service.run_task(db, waiting_task_id)
        executed = await agent_executor.execute_task(db, waiting_task_id, user=user, event_bus=event_bus)
    else:
        task = await agent_service.create_task(
            db,
            session_id,
            "根据补充信息生成需求草稿",
            agent="NeedCreatorAgent",
            task_type="draft_need",
            input_data={"follow_up": next_state["collected"]},
        )
        executed = await agent_executor.execute_task(db, task.id, user=user, event_bus=event_bus)

    drafts = (executed.result or {}).get("drafts") if executed and executed.result else None
    await agent_service.update_session_planning_state(
        db,
        session_id,
        {"follow_up": None, "pending_drafts": drafts or []},
    )
    reply = "我已经根据你的补充整理好需求草稿，确认后就可以发布。"
    metadata = {"type": "draft_ready", "drafts": drafts}
    await agent_service.add_message(
        db,
        session_id,
        "assistant",
        reply,
        extra_metadata=metadata,
    )
    return {
        "reply": reply,
        "intent": "publish_need",
        "drafts": drafts,
        "need_recommendations": None,
        "message_role": "assistant",
        "message_metadata": metadata,
    }


async def _generate_chat_reply(message: str, user_context: str, ctx: dict, file_info: str) -> str:
    from app.adapters.deepseek_adapter import DeepSeekChatAdapter
    from app.integrations.client import get_ai_client
    from app.integrations.model_router import route
    from app.prompts.registry import PromptRegistry

    client = get_ai_client()
    cfg = route("agent_chat")
    adapter = DeepSeekChatAdapter(client, model=cfg["model"])
    chat_messages = PromptRegistry.render(
        "agent_chat",
        {
            "user_context": user_context[:500],
            "session_summary": ctx["session_summary"],
            "file_context": file_info,
            "history": ctx["history"][-1500:],
            "message": message,
        },
    )
    try:
        return await adapter.chat(chat_messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
    except Exception:
        logger.exception("Agent chat fallback engaged")
        return _fallback_chat_reply(message, file_info)


async def handle_file_upload(
    db: AsyncSession,
    session_id: int,
    file_bytes: bytes,
    filename: str,
    file_type: str,
    user: User,
    event_bus=None,
) -> dict:
    content_text = _extract_text(file_bytes, filename, file_type)
    agent_file = await agent_service.save_file(db, session_id, filename, file_type, content_text, file_bytes)

    try:
        embed_skill = SkillRegistry.get("embedding")
        emb_result = await embed_skill.execute({"text": content_text[:2000]})
        await agent_service.update_file_info(db, agent_file.id, embedding=emb_result["embedding"])
    except Exception:
        logger.exception("File embedding failed")

    analyze_task = await agent_service.create_task(
        db,
        session_id,
        f"分析文件 {filename}",
        task_type="analyze_file",
        agent="FileReaderAgent",
        input_data={"filename": filename, "file_type": file_type, "file_id": agent_file.id},
        file_id=agent_file.id,
    )
    executed = await agent_executor.execute_task(db, analyze_task.id, user=user, event_bus=event_bus)
    extracted = executed.result if executed and executed.result else {}

    drafts = None
    if extracted and (extracted.get("potential_needs") or extracted.get("summary")):
        draft_task = await agent_service.create_task(
            db,
            session_id,
            "根据文件生成需求草稿",
            task_type="draft_need",
            agent="NeedCreatorAgent",
            input_data={"file_id": agent_file.id},
            file_id=agent_file.id,
        )
        draft_exec = await agent_executor.execute_task(db, draft_task.id, user=user, event_bus=event_bus)
        drafts = (draft_exec.result or {}).get("drafts") if draft_exec and draft_exec.result else None

    if extracted and extracted.get("summary"):
        ai_msg = (
            f"我分析了文件《{filename}》，主要内容是：\n\n"
            f"**{extracted.get('title', '')}**\n"
            f"{extracted.get('summary', '')[:300]}\n"
        )
        if extracted.get("skills_needed"):
            ai_msg += f"\n所需技能：{', '.join(extracted['skills_needed'])}"
        if extracted.get("deadline"):
            ai_msg += f"\n截止日期：{extracted['deadline']}"
        if extracted.get("potential_needs"):
            ai_msg += "\n\n我已经整理出可发布的需求草稿，确认后就可以直接发布。"
    else:
        ai_msg = f"已收到文件《{filename}》（{file_type}），但未能自动提取关键信息。你可以直接描述需求，我继续帮你整理。"

    await agent_service.add_message(
        db,
        session_id,
        "assistant",
        ai_msg,
        extra_metadata={"type": "file_analysis", "drafts": drafts, "extracted": extracted},
    )
    if drafts:
        await agent_service.update_session_planning_state(db, session_id, {"pending_drafts": drafts})
    return {"reply": ai_msg, "file_id": agent_file.id, "extracted": extracted, "drafts": drafts}


async def handle_plan(
    db: AsyncSession,
    session_id: int,
    goal: str,
    user: User,
    event_bus=None,
) -> dict:
    planner = PlannerAgent()
    result = await planner.execute({"goal": goal, "session_id": session_id, "db": db, "user": user})

    tasks = result.get("plan", [])
    latest_file = await _get_latest_file(db, session_id)
    plan_msg = f"已为《{goal}》制定执行计划：\n"

    db_tasks: list[dict] = []
    task_id_map: dict[int, int] = {}
    for index, task_data in enumerate(tasks):
        goal_text = task_data.get("goal", task_data) if isinstance(task_data, dict) else str(task_data)
        assigned_agent = task_data.get("assigned_agent", "") if isinstance(task_data, dict) else ""
        depends_on = task_data.get("depends_on") if isinstance(task_data, dict) else None
        plan_msg += f"{index + 1}. {goal_text}" + (f" ({assigned_agent})" if assigned_agent else "") + "\n"

        parent_id = task_id_map.get(depends_on) if isinstance(depends_on, int) else None
        task_type = _AGENT_TO_TASK_TYPE.get(assigned_agent, "plan")
        input_data = {"goal": goal_text, "plan_index": index}
        if task_type == "draft_need" and latest_file:
            input_data["file_id"] = latest_file.id

        db_task = await agent_service.create_task(
            db,
            session_id,
            goal_text,
            parent_id=parent_id,
            agent=assigned_agent,
            task_type=task_type,
            input_data=input_data,
            file_id=latest_file.id if task_type == "draft_need" and latest_file else None,
        )
        task_id_map[index] = db_task.id

        if task_type == "draft_need" and latest_file:
            await agent_executor.execute_task(db, db_task.id, user=user, event_bus=event_bus)

        db_tasks.append(
            {
                "id": db_task.id,
                "goal": goal_text,
                "status": db_task.status,
                "assigned_agent": assigned_agent,
                "parent_task_id": parent_id,
                "task_type": task_type,
                "input_data": db_task.input_data,
                "retry_count": 0,
                "created_at": str(db_task.created_at),
                "updated_at": str(db_task.updated_at) if db_task.updated_at else None,
            }
        )

    await agent_service.add_message(db, session_id, "system", plan_msg, extra_metadata={"type": "plan"})
    return {"reply": plan_msg, "tasks": db_tasks}


async def handle_confirm_publish(
    db: AsyncSession,
    session_id: int,
    drafts: list[dict],
    user: User,
    event_bus=None,
) -> dict:
    session = await agent_service.get_session(db, session_id)
    planning_state = dict(session.planning_state or {}) if session else {}
    pending_drafts = _get_pending_drafts(planning_state)
    if not pending_drafts:
        raise ValueError("draft already published or no longer pending")
    selected_drafts, remaining_drafts = _split_selected_and_remaining_drafts(pending_drafts, drafts)
    if session_id in _publish_inflight_sessions:
        raise ValueError("publish already in progress")

    _publish_inflight_sessions.add(session_id)
    try:
        task = await agent_service.create_task(
            db,
            session_id,
            "发布需求草稿",
            task_type="publish_need",
            agent="NeedCreatorAgent",
            input_data={"drafts": selected_drafts},
        )
        executed = await agent_executor.execute_task(db, task.id, user=user, event_bus=event_bus)
        created = (executed.result or {}).get("needs") if executed and executed.result else []
        await agent_service.update_session_planning_state(
            db,
            session_id,
            {"pending_drafts": remaining_drafts, "follow_up": None},
        )
    finally:
        _publish_inflight_sessions.discard(session_id)

    summary = f"已成功发布 {len(created)} 个需求：\n"
    for item in created:
        summary += f"- [{item['type']}] {item['title']} (ID: {item['id']})\n"
    summary += "\n匹配已启动，结果出来后我会继续提醒你。"

    await agent_service.add_message(db, session_id, "system", summary, extra_metadata={"type": "publish_done"})
    return {
        "reply": summary,
        "needs": created,
        "message_role": "system",
        "message_metadata": {"type": "publish_done"},
    }


async def handle_draft_message(
    need_title: str,
    match_name: str,
    match_skills: list[str],
    match_reason: str,
    user_name: str,
    user_context: str = "",
) -> str:
    from app.adapters.deepseek_adapter import DeepSeekChatAdapter
    from app.integrations.client import get_ai_client
    from app.integrations.model_router import route
    from app.prompts.registry import PromptRegistry

    client = get_ai_client()
    cfg = route("agent_chat")
    adapter = DeepSeekChatAdapter(client, model=cfg["model"])
    messages = PromptRegistry.render(
            "agent_draft_message",
            {
                "need_title": need_title,
                "match_name": match_name,
                "match_skills": ", ".join(match_skills),
                "match_reason": match_reason,
                "user_name": user_name,
                "user_context": user_context,
            },
        )
    try:
        return await adapter.chat(messages, temperature=0.8, max_tokens=200)
    except Exception:
        logger.exception("Draft message fallback engaged")
        return _fallback_draft_message(
            need_title=need_title,
            match_name=match_name,
            match_skills=match_skills,
            match_reason=match_reason,
            user_name=user_name,
        )


async def handle_draft_application_message(
    need_title: str,
    need_type: str,
    owner_name: str,
    user_name: str,
    user_skills: list[str],
    match_reason: str,
    user_context: str = "",
) -> str:
    from app.adapters.deepseek_adapter import DeepSeekChatAdapter
    from app.integrations.client import get_ai_client
    from app.integrations.model_router import route

    client = get_ai_client()
    cfg = route("agent_chat")
    adapter = DeepSeekChatAdapter(client, model=cfg["model"])
    messages = [
        {
            "role": "system",
            "content": (
                "Write a concise first-contact application message for joining a collaboration need. "
                "Keep it warm, specific, and under 120 Chinese characters if possible."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Need title: {need_title}\n"
                f"Need type: {need_type}\n"
                f"Owner name: {owner_name}\n"
                f"Applicant name: {user_name}\n"
                f"Applicant skills: {', '.join(user_skills)}\n"
                f"Applicant context: {user_context[:500]}\n"
                f"Why it matches: {match_reason}\n"
            ),
        },
    ]
    try:
        return await adapter.chat(messages, temperature=0.7, max_tokens=180)
    except Exception:
        logger.exception("Draft application message fallback engaged")
        return _fallback_application_message(
            need_title=need_title,
            owner_name=owner_name,
            user_name=user_name,
            user_skills=user_skills,
            match_reason=match_reason,
        )


async def _get_latest_file(db: AsyncSession, session_id: int):
    from app.models.agent import AgentFile
    from sqlalchemy import desc, select as _s

    result = await db.execute(
        _s(AgentFile).where(AgentFile.session_id == session_id).order_by(desc(AgentFile.created_at)).limit(1)
    )
    return result.scalar_one_or_none()


def _extract_text(file_bytes: bytes, filename: str, file_type: str) -> str:
    if file_type == "txt":
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("gbk", errors="ignore")

    if file_type == "docx":
        try:
            from io import BytesIO
            from docx import Document

            doc = Document(BytesIO(file_bytes))
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])
        except Exception:
            return f"[unable to parse docx file: {filename}]"

    if file_type == "pdf":
        try:
            from io import BytesIO
            from PyPDF2 import PdfReader

            reader = PdfReader(BytesIO(file_bytes))
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception:
            return f"[unable to parse pdf file: {filename}]"

    return f"[unsupported file type: {file_type}]"
