from abc import ABC, abstractmethod


class BaseSkill(ABC):
    name: str
    description: str
    version: str = "1.0.0"

    input_schema: dict
    output_schema: dict

    tags: list[str] = []

    @abstractmethod
    async def execute(self, input_data: dict) -> dict: ...

    def to_openai_function(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }
