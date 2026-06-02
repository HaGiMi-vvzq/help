import asyncio
import logging

from sqlalchemy import select as _s
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.models.match import Match

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds
MAX_POLLS = 480  # max 4 hours


class MatchWatcherAgent(BaseAgent):
    name = "MatchWatcherAgent"
    description = "后台轮询匹配结果，完成后推送通知"

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        need_id = input_data["need_id"]
        session_id = input_data["session_id"]
        db_factory = input_data["db_factory"]

        async def poll():
            polls = 0
            while polls < MAX_POLLS:
                await asyncio.sleep(POLL_INTERVAL)
                polls += 1
                try:
                    async with db_factory() as db:
                        r = await db.execute(_s(Match).where(Match.need_id == need_id))
                        matches = r.scalars().all()
                        if matches:
                            from app.models.agent import AgentMessage
                            db.add(AgentMessage(
                                session_id=session_id,
                                role="system",
                                content=f"需求 #{need_id} 匹配完成，共{len(matches)}位候选人。",
                                extra_metadata={"type": "match_done", "need_id": need_id, "count": len(matches)},
                            ))
                            await db.commit()
                            if context and context.get("event_bus"):
                                await context["event_bus"].emit_background("agent_match_completed", {
                                    "session_id": session_id, "need_id": need_id,
                                    "match_count": len(matches),
                                })
                            return
                except Exception:
                    logger.exception("Match watcher poll error for need %d", need_id)

        asyncio.create_task(poll())
        return {"watching": True, "need_id": need_id, "poll_interval": POLL_INTERVAL}
