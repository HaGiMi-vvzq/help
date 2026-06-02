"""Agent APIs for sessions, chat, planning, publish, workspace, and drafting helpers."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.events import get_event_bus
from app.models.agent import AgentTask
from app.models.match import Match
from app.models.message import Message
from app.models.need import Need
from app.models.user import User
from app.schemas.agent import (
    ChatRequest,
    ConfirmPublishRequest,
    PlanRequest,
    SearchKnowledgeRequest,
    SessionCreate,
)
from app.services import agent_executor, agent_memory, agent_planner, agent_service

router = APIRouter(prefix="/api/agent", tags=["agent"])


async def ensure_session_owner(db: AsyncSession, session_id: int, user_id: int):
    session = await agent_service.get_session(db, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(404, "session not found")
    return session


@router.post("/sessions")
async def create_session(
    data: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await agent_service.create_session(db, user, data.title)
    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "created_at": str(session.created_at),
    }


@router.get("/sessions")
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await agent_service.list_sessions(db, user.id)
    return [
        {
            "id": session.id,
            "title": session.title,
            "status": session.status,
            "summary": session.summary[:100] if session.summary else None,
            "created_at": str(session.created_at),
            "updated_at": str(session.updated_at),
        }
        for session in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await ensure_session_owner(db, session_id, user.id)
    messages = await agent_service.get_messages(db, session_id)
    tasks = await agent_service.get_tasks(db, session_id)
    return {
        "session": {
            "id": session.id,
            "title": session.title,
            "summary": session.summary,
            "planning_state": session.planning_state,
            "status": session.status,
            "user_id": session.user_id,
            "created_at": str(session.created_at),
            "updated_at": str(session.updated_at),
        },
        "messages": [
            {
                "id": message_obj.id,
                "role": message_obj.role,
                "content": message_obj.content,
                "extra_metadata": message_obj.extra_metadata,
                "created_at": str(message_obj.created_at),
            }
            for message_obj in messages
        ],
        "tasks": agent_service.build_task_tree(tasks),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_session_owner(db, session_id, user.id)
    await agent_service.delete_session(db, session_id)
    return {"ok": True}


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: int,
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_session_owner(db, session_id, user.id)
    result = await agent_planner.handle_chat_message(db, session_id, data.message, user, get_event_bus())
    return {
        "reply": result["reply"],
        "intent": result.get("intent"),
        "drafts": result.get("drafts"),
        "need_recommendations": result.get("need_recommendations"),
        "needs": result.get("needs"),
        "message_role": result.get("message_role"),
        "message_metadata": result.get("message_metadata"),
    }


@router.post("/sessions/{session_id}/upload")
async def upload_file(
    session_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_session_owner(db, session_id, user.id)
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if ext not in ("txt", "docx", "pdf"):
        raise HTTPException(400, "only txt, docx, and pdf are supported")

    raw_bytes = await file.read()
    if len(raw_bytes) > 5 * 1024 * 1024:
        raise HTTPException(400, "file must be smaller than 5MB")

    return await agent_planner.handle_file_upload(
        db,
        session_id,
        raw_bytes,
        filename,
        ext,
        user,
        get_event_bus(),
    )


@router.post("/sessions/{session_id}/plan")
async def trigger_plan(
    session_id: int,
    data: PlanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_session_owner(db, session_id, user.id)
    return await agent_planner.handle_plan(db, session_id, data.goal, user, get_event_bus())


@router.post("/sessions/{session_id}/confirm-publish")
async def confirm_publish(
    session_id: int,
    data: ConfirmPublishRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_session_owner(db, session_id, user.id)
    if data.draft is None:
        raise HTTPException(400, "draft is required")

    drafts: list[dict] = []
    raw = data.draft
    if isinstance(raw, list):
        drafts = [item.model_dump() if hasattr(item, "model_dump") else item for item in raw]
    elif hasattr(raw, "model_dump"):
        drafts = [raw.model_dump()]
    elif isinstance(raw, dict):
        drafts = [raw]

    try:
        return await agent_planner.handle_confirm_publish(db, session_id, drafts, user, get_event_bus())
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/sessions/{session_id}/tasks")
async def get_tasks(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_session_owner(db, session_id, user.id)
    tasks = await agent_service.get_tasks(db, session_id)
    return agent_service.build_task_tree(tasks)


@router.post("/sessions/{session_id}/tasks/{task_id}/retry")
async def retry_task(
    session_id: int,
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_session_owner(db, session_id, user.id)
    task = await agent_service.get_task(db, task_id)
    if task is None or task.session_id != session_id:
        raise HTTPException(404, "task not found")
    if task.status not in ("failed", "cancelled"):
        raise HTTPException(400, f"task can only be retried from failed/cancelled, current={task.status}")
    updated = await agent_executor.execute_task(db, task_id, user=user, event_bus=get_event_bus())
    return {"ok": True, "status": updated.status, "retry_count": updated.retry_count}


@router.get("/sessions/{session_id}/workspace")
async def get_workspace(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await ensure_session_owner(db, session_id, user.id)
    files = await agent_service.list_files(db, session_id)
    return {
        "memory": {
            "summary": session.summary,
            "follow_up": (session.planning_state or {}).get("follow_up"),
        },
        "files": [
            {
                "id": file_obj.id,
                "filename": file_obj.filename,
                "file_type": file_obj.file_type,
                "extracted_info": file_obj.extracted_info,
                "created_at": str(file_obj.created_at),
            }
            for file_obj in files
        ],
    }


@router.post("/sessions/{session_id}/memory/reset")
async def reset_memory(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await ensure_session_owner(db, session_id, user.id)
    session.summary = None
    planning_state = dict(session.planning_state or {})
    planning_state.pop("_memory", None)
    session.planning_state = planning_state
    await db.commit()
    await db.refresh(session)
    return {"ok": True}


@router.post("/search-knowledge")
async def search_knowledge(
    data: SearchKnowledgeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    context_manager = agent_memory.ContextManager(db)
    results = await context_manager.search_knowledge(user.id, data.query)
    return {"results": results}


@router.get("/suggestions/{session_id}")
async def get_suggestions(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await ensure_session_owner(db, session_id, user.id)
    suggestions: list[dict] = []

    follow_up = (session.planning_state or {}).get("follow_up")
    if follow_up:
        suggestions.append(
            {
                "id": f"follow-up-{session_id}",
                "text": "Continue filling in the requirement details so the agent can finish a publish-ready draft.",
                "action_type": "prefill",
                "payload": {"text": ""},
            }
        )

    task_result = await db.execute(
        select(AgentTask)
        .where(
            AgentTask.session_id == session_id,
            AgentTask.status.in_(("failed", "waiting_user")),
        )
        .order_by(AgentTask.updated_at.desc())
    )
    for task in task_result.scalars().all()[:2]:
        suggestions.append(
            {
                "id": f"task-{task.id}",
                "text": f"Task '{task.goal}' is currently {task.status}. Refresh the timeline to keep the flow moving.",
                "action_type": "refresh_tasks",
                "payload": {"task_id": task.id},
            }
        )

    needs_result = await db.execute(select(Need).where(Need.user_id == user.id, Need.status == "\u5f00\u653e"))
    for need in needs_result.scalars().all()[:3]:
        match_count_result = await db.execute(select(func.count()).select_from(Match).where(Match.need_id == need.id))
        match_count = match_count_result.scalar() or 0
        if match_count:
            suggestions.append(
                {
                    "id": f"need-{need.id}",
                    "text": f"'{need.title}' already has {match_count} candidate matches. It is a good moment to review them.",
                    "action_type": "navigate",
                    "payload": {"path": f"/needs/{need.id}/matches"},
                }
            )
        else:
            suggestions.append(
                {
                    "id": f"need-open-{need.id}",
                    "text": f"'{need.title}' is still open. You can keep polishing the description or invite more applicants.",
                    "action_type": "prefill",
                    "payload": {"text": f"帮我优化需求《{need.title}》的描述"},
                }
            )

    unread_result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.receiver_id == user.id, Message.is_read.is_(False))
    )
    unread_count = unread_result.scalar() or 0
    if unread_count:
        suggestions.append(
            {
                "id": f"unread-{user.id}",
                "text": f"You have {unread_count} unread messages. It is worth checking whether a match or applicant replied.",
                "action_type": "navigate",
                "payload": {"path": "/messages"},
            }
        )

    return {"suggestions": suggestions}


@router.post("/draft-message")
async def draft_message(
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.user_context import build_user_context

    user_context = await build_user_context(db, user)
    message = await agent_planner.handle_draft_message(
        need_title=data.get("need_title", ""),
        match_name=data.get("match_name", ""),
        match_skills=data.get("match_skills", []),
        match_reason=data.get("match_reason", ""),
        user_name=user.username,
        user_context=user_context,
    )
    return {"message": message}


@router.post("/draft-application-message")
async def draft_application_message(
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.user_context import build_user_context

    user_context = await build_user_context(db, user)
    message = await agent_planner.handle_draft_application_message(
        need_title=data.get("need_title", ""),
        need_type=data.get("need_type", ""),
        owner_name=data.get("owner_name", ""),
        user_name=user.username,
        user_skills=data.get("user_skills", []) or (user.skill_tags or []),
        match_reason=data.get("match_reason", ""),
        user_context=user_context,
    )
    return {"message": message}
