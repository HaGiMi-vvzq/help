import re
import json

from app.adapters.base import BaseLLMAdapter, BaseEmbeddingAdapter
from app.integrations.client import AIClient


def _extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON from LLM output."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    # Try to find a JSON array or object if there's surrounding text
    bracket = text.find("[")
    brace = text.find("{")
    start = min(bracket if bracket >= 0 else len(text), brace if brace >= 0 else len(text))
    if start < len(text):
        text = text[start:]
    return json.loads(text)


class DeepSeekChatAdapter(BaseLLMAdapter):
    provider = "deepseek"

    def __init__(self, client: AIClient, model: str):
        self.client = client
        self.model = model

    async def chat(self, messages: list[dict], **kwargs) -> str:
        return await self.client.chat(messages, model=self.model, **kwargs)

    async def chat_with_json(self, messages: list[dict], **kwargs) -> dict:
        # 使用 DeepSeek JSON Output mode 确保合法 JSON
        raw = await self.client.chat(messages, model=self.model, json_mode=True, **kwargs)
        if not raw.strip():
            raise ValueError("Empty response from AI")
        return _extract_json(raw)

    def supports_reasoning(self) -> bool:
        return True

    def token_cost_per_1k(self) -> tuple[float, float]:
        return (0.001, 0.002)


class DeepSeekEmbedAdapter(BaseEmbeddingAdapter):
    """DeepSeek 暂不提供 Embedding API。此类保留用于未来扩展。
    实际使用 Qwen3EmbedAdapter (app/adapters/qwen_adapter.py)。
    """
    provider = "deepseek"
    dimension = 1024

    def __init__(self, client: AIClient):
        self.client = client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("DeepSeek 不支持 Embedding。请使用 Qwen3EmbedAdapter")

    async def embed_single(self, text: str) -> list[float]:
        raise NotImplementedError("DeepSeek 不支持 Embedding。请使用 Qwen3EmbedAdapter")
