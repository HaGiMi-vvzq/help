"""Agent 记忆管理: 上下文压缩、知识检索、用户记忆加载。"""

import logging

from sqlalchemy import desc, select as _s
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentFile, AgentMessage, AgentSession
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

SUMMARIZE_THRESHOLD = 20
KEEP_RECENT = 10


class ContextManager:
    """管理 Agent 对话上下文。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_chat_context(self, session_id: int) -> dict:
        """返回构建 prompt 所需的完整上下文。"""
        session = await self.db.execute(_s(AgentSession).where(AgentSession.id == session_id))
        s = session.scalar_one_or_none()
        if s is None:
            return {"session_summary": "", "history": "", "file_context": ""}

        # Check and summarize if needed
        await self._check_and_summarize(s)

        # Get recent messages
        msg_result = await self.db.execute(
            _s(AgentMessage).where(AgentMessage.session_id == session_id)
            .order_by(desc(AgentMessage.created_at)).limit(KEEP_RECENT)
        )
        recent = list(msg_result.scalars().all())
        recent.reverse()

        history_parts = []
        for m in recent:
            role_label = "用户" if m.role == "user" else "助手" if m.role == "assistant" else "系统"
            history_parts.append(f"[{role_label}]: {m.content}")

        # Get file context
        file_result = await self.db.execute(
            _s(AgentFile).where(AgentFile.session_id == session_id).order_by(desc(AgentFile.created_at)).limit(3)
        )
        files = file_result.scalars().all()
        file_parts = []
        for f in files:
            if f.extracted_info and isinstance(f.extracted_info, dict):
                ei = f.extracted_info
                file_parts.append(f"文件'{f.filename}': {ei.get('title','')} - {ei.get('summary','')[:200]}")
            else:
                file_parts.append(f"文件'{f.filename}': {f.content_text[:200]}")

        return {
            "session_summary": s.summary or "（新会话）",
            "history": "\n".join(history_parts),
            "file_context": "\n".join(file_parts) if file_parts else "（无上传文件）",
        }

    async def _check_and_summarize(self, session: AgentSession) -> None:
        """检查消息数，超阈值则触发摘要。"""
        from sqlalchemy import func
        memory_state = (session.planning_state or {}).get("_memory", {})
        summarized_until = int(memory_state.get("summarized_until_message_id") or 0)

        count_r = await self.db.execute(
            _s(func.count()).select_from(AgentMessage).where(
                AgentMessage.session_id == session.id,
                AgentMessage.id > summarized_until,
            )
        )
        count = count_r.scalar() or 0

        if count < SUMMARIZE_THRESHOLD:
            return

        msg_result = await self.db.execute(
            _s(AgentMessage).where(
                AgentMessage.session_id == session.id,
                AgentMessage.id > summarized_until,
            )
            .order_by(AgentMessage.created_at).limit(count - KEEP_RECENT)
        )
        to_summarize = list(msg_result.scalars().all())

        if not to_summarize:
            return

        messages = [{"role": m.role, "content": m.content} for m in to_summarize]

        try:
            skill = SkillRegistry.get("context_summarizer")
            result = await skill.execute({"messages": messages})
            new_summary = result.get("summary", "")

            if session.summary:
                session.summary = session.summary + "\n" + new_summary
            else:
                session.summary = new_summary
            planning_state = dict(session.planning_state or {})
            planning_state["_memory"] = {
                **dict(planning_state.get("_memory") or {}),
                "summarized_until_message_id": to_summarize[-1].id,
            }
            session.planning_state = planning_state
            await self.db.commit()
            logger.info("Summarized %d messages for session %d", len(to_summarize), session.id)
        except Exception:
            logger.exception("Summarization failed for session %d", session.id)

    async def search_knowledge(self, user_id: int, query_text: str, top_k: int = 3) -> list[dict]:
        """跨会话知识检索: 向量化查询 → 搜索 agent_files。"""
        # Get all sessions for this user
        sess_result = await self.db.execute(
            _s(AgentSession).where(AgentSession.user_id == user_id)
        )
        sessions = sess_result.scalars().all()
        session_ids = [s.id for s in sessions]
        if not session_ids:
            return []

        file_result = await self.db.execute(
            _s(AgentFile).where(AgentFile.session_id.in_(session_ids)).order_by(desc(AgentFile.created_at))
        )
        files = file_result.scalars().all()

        files_with_embedding = [f for f in files if f.embedding]
        if not files_with_embedding:
            return [{"id": f.id, "filename": f.filename, "extracted_info": f.extracted_info} for f in files[:top_k]]

        try:
            embed_skill = SkillRegistry.get("embedding")
            query_emb_result = await embed_skill.execute({"text": query_text})
            query_emb = query_emb_result["embedding"]

            scored = []
            for f in files_with_embedding:
                emb = f.embedding
                if emb and len(emb) == len(query_emb):
                    import numpy as np
                    a, b = np.array(query_emb), np.array(emb)
                    sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
                    scored.append((sim, f))
            scored.sort(key=lambda x: x[0], reverse=True)

            return [{"id": f.id, "filename": f.filename, "similarity": round(s, 3), "extracted_info": f.extracted_info} for s, f in scored[:top_k]]
        except Exception:
            logger.exception("Knowledge search failed")
            return []

    async def load_user_memory(self, user_id: int) -> str:
        """加载用户长期记忆。"""
        from app.models.user import User
        from app.services.user_context import build_user_context

        r = await self.db.execute(_s(User).where(User.id == user_id))
        user = r.scalar_one_or_none()
        if user:
            return await build_user_context(self.db, user)
        return ""
