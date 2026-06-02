from abc import ABC, abstractmethod


class BaseLLMAdapter(ABC):
    provider: str

    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str: ...

    @abstractmethod
    async def chat_with_json(self, messages: list[dict], **kwargs) -> dict: ...

    @abstractmethod
    def supports_reasoning(self) -> bool: ...

    @abstractmethod
    def token_cost_per_1k(self) -> tuple[float, float]: ...


class BaseEmbeddingAdapter(ABC):
    provider: str
    dimension: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]: ...
