from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.skills.registry import SkillRegistry


class FileReaderAgent(BaseAgent):
    name = "FileReaderAgent"
    description = "读取上传文件，提取关键信息"

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        file_id = input_data["file_id"]
        db: AsyncSession = input_data["db"]

        from app.models.agent import AgentFile
        from sqlalchemy import select as _s

        r = await db.execute(_s(AgentFile).where(AgentFile.id == file_id))
        f = r.scalar_one_or_none()
        if f is None:
            return {"success": False, "error": "文件不存在"}

        await self.think(f"正在分析文件: {f.filename}")

        skill = SkillRegistry.get("file_reader")
        result = await skill.execute({"text": f.content_text, "filename": f.filename})

        extracted = result.get("extracted", {})
        f.extracted_info = extracted
        await db.commit()

        if context and context.get("event_bus"):
            await context["event_bus"].emit_background("agent_file_processed", {
                "file_id": file_id, "session_id": f.session_id,
                "filename": f.filename, "extracted": extracted,
            })

        return {"success": True, "extracted": extracted, "filename": f.filename}
