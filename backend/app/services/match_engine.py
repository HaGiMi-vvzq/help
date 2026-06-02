import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import AgentOrchestrator
from app.core.events import EventBus
from app.knowledge.match_memory import MatchMemoryStore
from app.models.match import Match
from app.models.need import Need
from app.models.user import User
from app.schemas.match import MatchResult

logger = logging.getLogger(__name__)

_active_matching_tasks: dict[int, asyncio.Task] = {}
_matching_cancel_events: dict[int, asyncio.Event] = {}


def is_matching_active(need_id: int) -> bool:
    task = _active_matching_tasks.get(need_id)
    return bool(task and not task.done())


def schedule_matching(
    need_id: int,
    event_bus: EventBus | None = None,
    *,
    notifier: Callable[[int], Awaitable[None]] | None = None,
) -> asyncio.Task | None:
    existing = _active_matching_tasks.get(need_id)
    if existing and not existing.done():
        return existing

    cancel_event = asyncio.Event()
    _matching_cancel_events[need_id] = cancel_event

    async def runner() -> None:
        from app.core.database import async_session

        try:
            async with async_session() as bg_db:
                await run_matching(bg_db, need_id, event_bus, cancel_event=cancel_event)
                if cancel_event.is_set():
                    return
                if notifier is not None:
                    await notifier(need_id)
        except asyncio.CancelledError:
            logger.info("Matching task cancelled for need_id=%s", need_id)
            raise
        except Exception:
            logger.exception("Background matching failed for need_id=%s", need_id)
        finally:
            _active_matching_tasks.pop(need_id, None)
            _matching_cancel_events.pop(need_id, None)

    task = asyncio.create_task(runner(), name=f"need-matching-{need_id}")
    _active_matching_tasks[need_id] = task
    return task


async def cancel_matching(need_id: int) -> bool:
    task = _active_matching_tasks.get(need_id)
    cancel_event = _matching_cancel_events.get(need_id)
    if cancel_event is not None:
        cancel_event.set()

    if task is None or task.done():
        _active_matching_tasks.pop(need_id, None)
        _matching_cancel_events.pop(need_id, None)
        return False

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Error while awaiting cancelled matching task for need_id=%s", need_id)
    return True


async def run_matching(
    db: AsyncSession,
    need_id: int,
    event_bus: EventBus | None = None,
    *,
    cancel_event: asyncio.Event | None = None,
):
    """执行完整匹配 pipeline，写入 matches 表。"""
    result = await db.execute(select(Need).where(Need.id == need_id))
    need = result.scalar_one_or_none()
    if need is None:
        return
    if cancel_event and cancel_event.is_set():
        return

    need_description = need.description
    need_embedding = need.need_embedding
    need_tags = need.req_tags or []

    results = await AgentOrchestrator.run_matching_pipeline(
        db=db,
        need_description=need_description,
        need_embedding=need_embedding,
        need_tags=need_tags,
        exclude_user_id=need.user_id,
        _event_bus=event_bus,
    )
    if cancel_event and cancel_event.is_set():
        return

    latest_need_result = await db.execute(select(Need).where(Need.id == need_id))
    latest_need = latest_need_result.scalar_one_or_none()
    if latest_need is None:
        return

    # Delete old matches
    await db.execute(delete(Match).where(Match.need_id == need_id))

    # Save new results
    for r in results:
        match = Match(
            need_id=need_id,
            user_id=r["user_id"],
            score=float(r["score"]),
            ai_reason=r.get("reason", ""),
        )
        db.add(match)

    await db.commit()


async def get_matches(db: AsyncSession, need_id: int) -> list[MatchResult]:
    """获取缓存匹配结果，含用户详情。"""
    result = await db.execute(
        select(Match).where(Match.need_id == need_id).order_by(Match.score.desc())
    )
    matches = result.scalars().all()

    output = []
    for m in matches:
        user_result = await db.execute(select(User).where(User.id == m.user_id))
        user = user_result.scalar_one_or_none()
        output.append(
            MatchResult(
                user_id=m.user_id,
                score=m.score,
                reason=m.ai_reason,
                username=user.username if user else "",
                school=user.school or "",
                bio=user.bio or "",
                extra=user.extra if isinstance(user.extra, dict) else {},
                skill_tags=user.skill_tags or [],
            )
        )

    return output


async def run_matching_stream(db: AsyncSession, need_id: int, event_bus: EventBus | None = None):
    """SSE 流式匹配 — yields progress events + final results."""
    result = await db.execute(select(Need).where(Need.id == need_id))
    need = result.scalar_one_or_none()
    if need is None:
        yield f"data: {json.dumps({'stage': 'error', 'message': '需求不存在'})}\n\n"
        return

    queue: asyncio.Queue = asyncio.Queue()
    internal_bus = EventBus()

    async def on_progress(event: str, data: dict):
        await queue.put({"event": "progress", "data": data})

    internal_bus.on("matching_progress", on_progress)

    # Capture need data before spawning concurrent task
    need_desc = need.description
    need_emb = need.need_embedding
    need_tags_val = need.req_tags or []
    need_uid = need.user_id

    async def run_pipeline():
        from app.core.database import async_session
        async with async_session() as pipe_db:
            results = await AgentOrchestrator.run_matching_pipeline(
                db=pipe_db,
                need_description=need_desc,
                need_embedding=need_emb,
                need_tags=need_tags_val,
                exclude_user_id=need_uid,
                _event_bus=internal_bus,
            )

            await pipe_db.execute(delete(Match).where(Match.need_id == need_id))
            for r in results:
                pipe_db.add(
                    Match(
                        need_id=need_id,
                        user_id=r["user_id"],
                        score=float(r["score"]),
                        ai_reason=r.get("reason", ""),
                    )
                )
            await pipe_db.commit()
            await queue.put({"event": "done", "data": None})

            match_results = await get_matches(pipe_db, need_id)
            await queue.put({"event": "results", "data": [m.model_dump() for m in match_results]})

    task = asyncio.create_task(run_pipeline())

    while True:
        item = await queue.get()
        if item["event"] == "progress":
            yield f"data: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
        elif item["event"] == "results":
            yield f"data: {json.dumps({'stage': 'done', 'message': '匹配完成', 'data': {'results': item['data']}}, ensure_ascii=False)}\n\n"
            break
        elif item["event"] == "done":
            pass  # just signaling

    await task


async def record_feedback(
    db: AsyncSession, match_id: int, feedback: int, event_bus: EventBus | None = None
) -> None:
    """记录用户反馈，高分匹配写入记忆库。"""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if match is None:
        return

    match.feedback = feedback
    await db.commit()

    if event_bus:
        await event_bus.emit_background("feedback_received", {
            "match_id": match_id, "need_id": match.need_id,
            "user_id": match.user_id, "feedback": feedback,
        })

    # 高分匹配写入记忆
    if feedback >= 4:
        need_result = await db.execute(select(Need).where(Need.id == match.need_id))
        need = need_result.scalar_one_or_none()
        if need and need.need_embedding:
            await MatchMemoryStore.add_success(
                db=db,
                need_description=need.description,
                need_embedding=need.need_embedding,
                matched_user_id=match.user_id,
                score=match.score,
                ai_reason=match.ai_reason,
                feedback=feedback,
            )
