from app.skills.base import BaseSkill


class SkillRegistry:
    _skills: dict[str, BaseSkill] = {}

    @classmethod
    def register(cls, skill: BaseSkill) -> None:
        cls._skills[skill.name] = skill

    @classmethod
    def get(cls, name: str) -> BaseSkill:
        if name not in cls._skills:
            raise KeyError(f"Skill '{name}' not found")
        return cls._skills[name]

    @classmethod
    def list_all(cls) -> list[dict]:
        return [
            {"name": s.name, "description": s.description, "version": s.version, "tags": s.tags}
            for s in cls._skills.values()
        ]

    @classmethod
    def compose(cls, *skill_names: str) -> "SkillPipeline":
        skills = [cls.get(name) for name in skill_names]
        return SkillPipeline(skills)


class SkillPipeline:
    def __init__(self, skills: list[BaseSkill]):
        self.skills = skills

    async def execute(self, input_data: dict) -> dict:
        data = input_data
        for skill in self.skills:
            data = await skill.execute(data)
        return data
