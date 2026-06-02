import hashlib
import logging

from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class EmbedSkill(BaseSkill):
    name = "embedding"
    description = "将文本转为语义向量（Qwen3-Embedding-0.6B 本地模型，无模型时降级）"
    version = "1.0.0"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "待向量化的文本"}},
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {"embedding": {"type": "array", "items": {"type": "number"}}},
    }
    tags = ["nlp", "embedding", "local"]

    async def execute(self, input_data: dict) -> dict:
        text = input_data["text"]
        try:
            from app.adapters.qwen_adapter import get_qwen_embed
            adapter = get_qwen_embed()
            embedding = await adapter.embed_single(text)
            return {"embedding": embedding}
        except Exception:
            logger.warning("Qwen3-Embedding unavailable, using fallback embedding")
            return {"embedding": self._hash_embed(text)}

    @staticmethod
    def _hash_embed(text: str, dim: int = 128) -> list[float]:
        """简单的哈希嵌入降级方案（基于标签哈希生成伪向量）。
        匹配精度不如真实模型，但能让系统在没有模型时基本运行。
        """
        import numpy as np
        words = text.lower().replace(",", " ").split()
        vec = np.zeros(dim, dtype=float)
        for w in words:
            h = hashlib.md5(w.encode()).digest()
            for i in range(dim):
                vec[i] += (h[i % len(h)] - 128) / 1280.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
