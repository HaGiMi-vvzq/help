import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.file_reader_agent import FileReaderAgent
from app.agents.match_watcher_agent import MatchWatcherAgent
from app.agents.need_creator_agent import NeedCreatorAgent
from app.core.database import async_session
from app.models.agent import AgentTask
from app.models.user import User
from app.services import agent_service, match_engine, need_service

logger = logging.getLogger(__name__)

SUPPORTED_TASK_TYPES = {
    "analyze_file",
    "draft_need",
    "publish_need",
    "draft_message",
}


def build_draft_from_follow_up_state(collected: dict[str, Any]) -> dict[str, str]:
    draft_type = str(collected.get("type") or "组队")
    title = str(collected.get("title") or "新需求").strip() or "新需求"
    description = str(collected.get("description") or "").strip() or "请补充需求描述"
    requirements = str(collected.get("requirements") or "").strip()
    if requirements and requirements not in description:
        description = f"{description}\n\n期望技能/方向：{requirements}"
    selection_mode = str(collected.get("selection_mode") or "single")
    if selection_mode not in {"single", "multi"}:
        selection_mode = "single"
    return {
        "type": draft_type,
        "title": title,
        "description": description,
        "selection_mode": selection_mode,
    }


async def execute_task(
    db: AsyncSession,
    task_id: int,
    *,
    user: User | None = None,
    event_bus=None,
) -> AgentTask | None:
    task = await agent_service.get_task(db, task_id)
    if task is None:
        return None
    if task.task_type not in SUPPORTED_TASK_TYPES:
        return task
    if task.status != "running":
        task = await agent_service.run_task(db, task_id)
    try:
        result = await _dispatch_task(db, task, user=user, event_bus=event_bus)
        return await agent_service.update_task(db, task.id, "done", result=result)
    except Exception as exc:
        logger.exception("Agent task execution failed: %s", task.task_type)
        return await agent_service.update_task(
            db,
            task.id,
            "failed",
            error=str(exc),
            error_code=f"{(task.task_type or 'task').upper()}_ERROR",
        )


async def _dispatch_task(
    db: AsyncSession,
    task: AgentTask,
    *,
    user: User | None,
    event_bus=None,
) -> dict[str, Any]:
    if task.task_type == "analyze_file":
        return await _execute_analyze_file(db, task, event_bus=event_bus)
    if task.task_type == "draft_need":
        if user is None:
            raise ValueError("draft_need requires user")
        return await _execute_draft_need(db, task, user=user)
    if task.task_type == "publish_need":
        if user is None:
            raise ValueError("publish_need requires user")
        return await _execute_publish_need(db, task, user=user, event_bus=event_bus)
    if task.task_type == "draft_message":
        if user is None:
            raise ValueError("draft_message requires user")
        return await _execute_draft_message(task, user=user)
    raise ValueError(f"Unsupported task type: {task.task_type}")


async def _execute_analyze_file(
    db: AsyncSession,
    task: AgentTask,
    *,
    event_bus=None,
) -> dict[str, Any]:
    file_id = int((task.input_data or {}).get("file_id") or task.file_id or 0)
    if not file_id:
        raise ValueError("analyze_file missing file_id")
    file_obj = await agent_service.get_file(db, file_id)
    if file_obj is None:
        raise ValueError("file not found")
    reader = FileReaderAgent()
    result = await reader.execute({"file_id": file_id, "db": db}, {"event_bus": event_bus})
    extracted = result.get("extracted", {})
    await agent_service.update_file_info(db, file_id, extracted_info=extracted)
    return extracted


async def _execute_draft_need(
    db: AsyncSession,
    task: AgentTask,
    *,
    user: User,
) -> dict[str, Any]:
    input_data = task.input_data or {}
    follow_up = input_data.get("follow_up")
    if isinstance(follow_up, dict):
        draft = build_draft_from_follow_up_state(follow_up)
        return {"drafts": [draft], "source": "follow_up"}

    file_id = int(input_data.get("file_id") or task.file_id or 0)
    if file_id:
        file_obj = await agent_service.get_file(db, file_id)
        if file_obj is None:
            raise ValueError("file not found")
        extracted_info = file_obj.extracted_info or {}
        creator = NeedCreatorAgent()
        result = await creator.execute({"extracted_info": extracted_info, "user": user, "db": db})
        return {"drafts": result.get("drafts", []), "source": "file"}

    raise ValueError("draft_need missing usable input")


async def _execute_publish_need(
    db: AsyncSession,
    task: AgentTask,
    *,
    user: User,
    event_bus=None,
) -> dict[str, Any]:
    from app.schemas.need import NeedCreate

    drafts = list((task.input_data or {}).get("drafts") or [])
    if not drafts:
        raise ValueError("publish_need missing drafts")

    created: list[dict[str, Any]] = []
    for draft in drafts:
        data = NeedCreate(
            type=draft.get("type", "组队"),
            title=draft.get("title", ""),
            description=draft.get("description", ""),
            selection_mode=draft.get("selection_mode", "single"),
        )
        need = await need_service.create_need(db, user, data, event_bus)
        created.append({"id": need.id, "title": need.title, "type": need.type})
        match_engine.schedule_matching(need.id, event_bus, notifier=_notify_matching_complete)
        watcher = MatchWatcherAgent()
        await watcher.execute(
            {"need_id": need.id, "session_id": task.session_id, "db_factory": async_session},
            {"event_bus": event_bus},
        )
    return {"needs": created, "count": len(created)}


async def _notify_matching_complete(need_id: int) -> None:
    from app.models.message import Message
    from app.models.need import Need
    from sqlalchemy import select

    async with async_session() as bg_db:
        result = await bg_db.execute(select(Need).where(Need.id == need_id))
        need = result.scalar_one_or_none()
        if need is None:
            return

        matches = await match_engine.get_matches(bg_db, need_id)
        bg_db.add(
            Message(
                need_id=need_id,
                sender_id=need.user_id,
                receiver_id=need.user_id,
                content=f"你的需求《{need.title}》匹配完成，共有{len(matches)}位候选人，点击查看结果。",
                is_read=False,
            )
        )
        await bg_db.commit()


async def _run_matching_in_background(need_id: int, event_bus=None) -> None:
    async with async_session() as bg_db:
        await match_engine.run_matching(bg_db, need_id, event_bus)


async def _execute_draft_message(task: AgentTask, *, user: User) -> dict[str, Any]:
    from app.services.agent_planner import handle_draft_message

    input_data = task.input_data or {}
    message = await handle_draft_message(
        need_title=str(input_data.get("need_title") or ""),
        match_name=str(input_data.get("match_name") or ""),
        match_skills=list(input_data.get("match_skills") or []),
        match_reason=str(input_data.get("match_reason") or ""),
        user_name=user.username,
    )
    return {"message": message}
