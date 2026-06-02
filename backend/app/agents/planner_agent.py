import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    description = "总控Agent: 拆解目标，调度子Agent执行任务链"

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        goal = input_data["goal"]
        session_id = input_data["session_id"]
        db: AsyncSession = input_data["db"]
        user = input_data["user"]

        await self.think(f"正在规划: {goal}")

        # Get session context for planner
        from app.models.agent import AgentMessage
        from sqlalchemy import select as _s
        r = await db.execute(
            _s(AgentMessage).where(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.desc()).limit(10)
        )
        recent = r.scalars().all()
        context_str = "\n".join([f"[{m.role}]: {m.content[:100]}" for m in reversed(recent)])

        skill = SkillRegistry.get("task_planner")
        plan_result = await skill.execute({"goal": goal, "context": context_str})

        tasks = plan_result.get("tasks", [])
        if isinstance(tasks, dict):
            tasks = tasks.get("tasks", [])
        if not tasks:
            tasks = [{"goal": "分析并确认用户需求", "assigned_agent": "IntentAnalyzerAgent"}]

        from app.models.agent import AgentTask
        parent_ids: dict[int, int] = {}

        for i, t in enumerate(tasks):
            goal_text = t.get("goal", t) if isinstance(t, dict) else str(t)
            agent_name = t.get("assigned_agent", "") if isinstance(t, dict) else ""
            depends_on = t.get("depends_on") if isinstance(t, dict) else None

            parent_id = None
            if depends_on is not None and isinstance(depends_on, int) and depends_on in parent_ids:
                parent_id = parent_ids[depends_on]

            task = AgentTask(
                session_id=session_id,
                parent_task_id=parent_id,
                goal=goal_text,
                assigned_agent=agent_name,
            )
            db.add(task)
            await db.commit()
            await db.refresh(task)
            parent_ids[i] = task.id

        return {"plan": tasks, "task_count": len(tasks), "success": True}
