from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    name: str
    version: str
    system_prompt: str
    user_prompt_template: str
    few_shot_examples: list[dict] = field(default_factory=list)
    output_schema: dict = field(default_factory=dict)

    def render(self, variables: dict) -> list[dict]:
        messages = []
        messages.append({"role": "system", "content": self.system_prompt})

        for ex in self.few_shot_examples:
            messages.append({"role": "user", "content": ex["input"]})
            messages.append({"role": "assistant", "content": ex["output"]})

        user_content = self.user_prompt_template.format(**variables)
        messages.append({"role": "user", "content": user_content})

        return messages


class PromptRegistry:
    _templates: dict[str, PromptTemplate] = {}

    @classmethod
    def register(cls, template: PromptTemplate) -> None:
        cls._templates[template.name] = template

    @classmethod
    def render(cls, name: str, variables: dict) -> list[dict]:
        if name not in cls._templates:
            raise KeyError(f"Prompt '{name}' not found")
        return cls._templates[name].render(variables)

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._templates.keys())
