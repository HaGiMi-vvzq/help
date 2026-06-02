import logging

from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class BaseAgent:
    name: str
    description: str

    async def execute(self, input_data: dict, context: dict | None = None) -> dict:
        raise NotImplementedError

    async def think(self, step: str) -> None:
        logger.info("[%s] %s", self.name, step)

    def use_skill(self, name: str) -> "BaseSkill":
        from app.skills.base import BaseSkill
        return SkillRegistry.get(name)
