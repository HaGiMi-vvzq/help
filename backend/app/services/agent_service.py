"""Agent 会话/消息/任务/文件 CRUD。"""

import os
import logging

from sqlalchemy import delete, desc, select as _s
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentFile, AgentMessage, AgentSession, AgentTask
from app.models.user import User

logger = logging.getLogger(__name__)

# ── Task lifecycle ──

VALID_TASK_TRANSITIONS = {
    "pending":    {"running", "waiting_user", "cancelled"},
    "running":    {"waiting_user", "done", "failed", "cancelled"},
    "waiting_user": {"running", "done", "failed", "cancelled"},
    "done":       set(),
    "failed":     {"running", "cancelled"},  # retry or give up
    "cancelled":  set(),
}


def validate_transition(current: str, next_status: str) -> None:
    valid = VALID_TASK_TRANSITIONS.get(current, set())
    if next_status not in valid:
        raise ValueError(f"Invalid task status transition: {current} -> {next_status}")


# ── Session ──

async def create_session(db: AsyncSession, user: User, title: str = "新对话") -> AgentSession:
    s = AgentSession(user_id=user.id, title=title)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def get_session(db: AsyncSession, session_id: int) -> AgentSession | None:
    r = await db.execute(_s(AgentSession).where(AgentSession.id == session_id))
    return r.scalar_one_or_none()


async def update_session_planning_state(
    db: AsyncSession,
    session_id: int,
    patch: dict,
    *,
    replace: bool = False,
) -> AgentSession | None:
    session = await get_session(db, session_id)
    if session is None:
        return None
    if replace:
        session.planning_state = patch
    else:
        state = dict(session.planning_state or {})
        state.update(patch)
        session.planning_state = state
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, user_id: int) -> list[AgentSession]:
    r = await db.execute(
        _s(AgentSession).where(AgentSession.user_id == user_id)
        .order_by(desc(AgentSession.updated_at))
    )
    return list(r.scalars().all())


async def delete_session(db: AsyncSession, session_id: int) -> None:
    """删除会话及其所有关联数据。"""
    # Break self-referencing FK first, then cascade
    from sqlalchemy import update
    await db.execute(update(AgentTask).where(AgentTask.session_id == session_id).values(parent_task_id=None))
    await db.flush()
    await db.execute(delete(AgentTask).where(AgentTask.session_id == session_id))
    await db.execute(delete(AgentMessage).where(AgentMessage.session_id == session_id))
    await db.execute(delete(AgentFile).where(AgentFile.session_id == session_id))
    await db.execute(delete(AgentSession).where(AgentSession.id == session_id))
    await db.commit()


# ── Messages ──

async def add_message(
    db: AsyncSession, session_id: int, role: str, content: str,
    token_count: int | None = None, extra_metadata: dict | None = None,
) -> AgentMessage:
    m = AgentMessage(session_id=session_id, role=role, content=content, token_count=token_count, extra_metadata=extra_metadata)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    # touch session
    r = await db.execute(_s(AgentSession).where(AgentSession.id == session_id))
    s = r.scalar_one_or_none()
    if s:
        s.updated_at = m.created_at
        await db.commit()
    return m


async def get_messages(db: AsyncSession, session_id: int, limit: int = 50) -> list[AgentMessage]:
    r = await db.execute(
        _s(AgentMessage).where(AgentMessage.session_id == session_id)
        .order_by(desc(AgentMessage.created_at), desc(AgentMessage.id)).limit(limit)
    )
    messages = list(r.scalars().all())
    messages.reverse()
    return messages


async def get_recent_messages(db: AsyncSession, session_id: int, limit: int = 10) -> list[AgentMessage]:
    return await get_messages(db, session_id, limit)


async def count_messages(db: AsyncSession, session_id: int) -> int:
    from sqlalchemy import func
    r = await db.execute(
        _s(func.count()).select_from(AgentMessage).where(AgentMessage.session_id == session_id)
    )
    return r.scalar() or 0


# ── Tasks ──

async def create_task(
    db: AsyncSession, session_id: int, goal: str,
    parent_id: int | None = None, agent: str = "",
    task_type: str | None = None, input_data: dict | None = None,
    need_id: int | None = None, match_id: int | None = None,
    file_id: int | None = None,
) -> AgentTask:
    t = AgentTask(
        session_id=session_id, parent_task_id=parent_id, task_type=task_type,
        goal=goal, assigned_agent=agent,
        input_data=input_data, need_id=need_id, match_id=match_id,
        file_id=file_id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def update_task(
    db: AsyncSession, task_id: int, status: str,
    result: dict | None = None, error: str | None = None,
    error_code: str | None = None, increment_retry: bool = False,
) -> AgentTask | None:
    r = await db.execute(_s(AgentTask).where(AgentTask.id == task_id))
    t = r.scalar_one_or_none()
    if t:
        validate_transition(t.status, status)
        t.status = status
        if result is not None:
            t.result = result
        if error is not None:
            t.error = error
        if error_code is not None:
            t.error_code = error_code
        if increment_retry:
            t.retry_count = (t.retry_count or 0) + 1
        await db.commit()
        await db.refresh(t)
    return t


async def update_task_input_data(
    db: AsyncSession,
    task_id: int,
    input_data: dict,
) -> AgentTask | None:
    task = await get_task(db, task_id)
    if task is None:
        return None
    task.input_data = input_data
    await db.commit()
    await db.refresh(task)
    return task


async def run_task(db: AsyncSession, task_id: int) -> AgentTask | None:
    """Mark a task as running (creating a retry if it was failed)."""
    r = await db.execute(_s(AgentTask).where(AgentTask.id == task_id))
    t = r.scalar_one_or_none()
    if t:
        increment = t.status == "failed"
        validate_transition(t.status, "running")
        t.status = "running"
        if increment:
            t.retry_count = (t.retry_count or 0) + 1
        await db.commit()
        await db.refresh(t)
    return t


async def get_task(db: AsyncSession, task_id: int) -> AgentTask | None:
    r = await db.execute(_s(AgentTask).where(AgentTask.id == task_id))
    return r.scalar_one_or_none()


async def get_tasks(db: AsyncSession, session_id: int) -> list[AgentTask]:
    r = await db.execute(
        _s(AgentTask).where(AgentTask.session_id == session_id).order_by(AgentTask.created_at)
    )
    return list(r.scalars().all())


def build_task_tree(tasks: list[AgentTask]) -> list[dict]:
    """Build a parent-child task tree from a flat task list."""
    task_map: dict[int, dict] = {}
    roots: list[dict] = []

    for t in tasks:
        node = _task_to_dict(t)
        node["children"] = []
        task_map[t.id] = node

    for t in tasks:
        node = task_map[t.id]
        if t.parent_task_id and t.parent_task_id in task_map:
            task_map[t.parent_task_id]["children"].append(node)
        else:
            roots.append(node)

    return roots


def _task_to_dict(t: AgentTask) -> dict:
    return {
        "id": t.id,
        "session_id": t.session_id,
        "parent_task_id": t.parent_task_id,
        "task_type": t.task_type,
        "goal": t.goal,
        "status": t.status,
        "assigned_agent": t.assigned_agent,
        "input_data": t.input_data,
        "result": t.result,
        "error": t.error,
        "error_code": t.error_code,
        "retry_count": t.retry_count or 0,
        "need_id": t.need_id,
        "match_id": t.match_id,
        "file_id": t.file_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


# ── Files ──

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _write_file(filepath: str, data: bytes) -> None:
    with open(filepath, "wb") as fh:
        fh.write(data)


async def save_file(
    db: AsyncSession, session_id: int, filename: str,
    file_type: str, content_text: str, raw_bytes: bytes,
) -> AgentFile:
    # Save to disk (non-blocking via executor)
    import asyncio
    filepath = os.path.join(UPLOAD_DIR, f"{session_id}_{filename}")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _write_file, filepath, raw_bytes)

    f = AgentFile(session_id=session_id, filename=filename, file_type=file_type, content_text=content_text)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


async def get_file(db: AsyncSession, file_id: int) -> AgentFile | None:
    r = await db.execute(_s(AgentFile).where(AgentFile.id == file_id))
    return r.scalar_one_or_none()


async def list_files(db: AsyncSession, session_id: int) -> list[AgentFile]:
    r = await db.execute(
        _s(AgentFile).where(AgentFile.session_id == session_id).order_by(desc(AgentFile.created_at))
    )
    return list(r.scalars().all())


async def update_file_info(
    db: AsyncSession, file_id: int, extracted_info: dict | None = None,
    embedding: list | None = None,
) -> AgentFile | None:
    r = await db.execute(_s(AgentFile).where(AgentFile.id == file_id))
    f = r.scalar_one_or_none()
    if f:
        if extracted_info:
            f.extracted_info = extracted_info
        if embedding:
            f.embedding = embedding
        await db.commit()
        await db.refresh(f)
    return f
