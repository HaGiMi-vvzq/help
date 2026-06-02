import asyncio
import logging
from pathlib import Path

from app.adapters.base import BaseEmbeddingAdapter

logger = logging.getLogger(__name__)


class Qwen3EmbedAdapter(BaseEmbeddingAdapter):
    """Qwen3-Embedding-0.6B 本地适配器。

    使用 sentence-transformers 加载，CPU 推理，零 API 费用。
    支持 MRL（Matryoshka Representation Learning），可按需截断维度。
    """

    provider = "qwen3"
    dimension = 1024  # 默认全维度

    def __init__(self, model_path: str = "model_cache/Qwen3-Embedding-0.6B", mrl_dim: int | None = None):
        self.model_path = model_path
        self.mrl_dim = mrl_dim
        self._model = None
        if mrl_dim:
            self.dimension = mrl_dim

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            path = Path(self.model_path)
            if not path.is_absolute():
                path = Path(__file__).parent.parent.parent / self.model_path

            logger.info("Loading Qwen3-Embedding from %s", path)
            self._model = SentenceTransformer(
                str(path.resolve()),
                trust_remote_code=True,
            )

    def _encode(self, texts: list[str]) -> list[list[float]]:
        self._load()
        if self.mrl_dim:
            embeddings = self._model.encode(
                texts,
                normalize_embeddings=True,
                truncate_dim=self.mrl_dim,
            )
        else:
            embeddings = self._model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._encode, texts)

    async def embed_single(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]


class Qwen3RerankAdapter:
    """Qwen3-Reranker-0.6B 本地适配器。

    Cross-encoder 架构，对 (query, document) 对直接打分。
    比 embedding + cosine 更准，适合 Stage 2 精排。
    """

    def __init__(self, model_path: str = "model_cache/Qwen3-Reranker-0.6B"):
        self.model_path = model_path
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            path = Path(self.model_path)
            if not path.is_absolute():
                path = Path(__file__).parent.parent.parent / self.model_path

            logger.info("Loading Qwen3-Reranker from %s", path)
            self._model = CrossEncoder(
                str(path.resolve()),
                trust_remote_code=True,
            )

    def _predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        self._load()
        scores = self._model.predict(pairs)
        return [float(s) for s in scores]

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        loop = asyncio.get_running_loop()
        pairs = [(query, doc) for doc in documents]
        return await loop.run_in_executor(None, self._predict, pairs)


_qwen_embed: Qwen3EmbedAdapter | None = None
_qwen_rerank: Qwen3RerankAdapter | None = None


def get_qwen_embed() -> Qwen3EmbedAdapter:
    global _qwen_embed
    if _qwen_embed is None:
        from app.core.config import settings
        mrl_dim = settings.QWEN_EMBED_MRL_DIM if settings.QWEN_EMBED_MRL_DIM > 0 else None
        _qwen_embed = Qwen3EmbedAdapter(
            model_path=settings.QWEN_EMBED_PATH,
            mrl_dim=mrl_dim,
        )
    return _qwen_embed


def get_qwen_rerank() -> Qwen3RerankAdapter:
    global _qwen_rerank
    if _qwen_rerank is None:
        from app.core.config import settings
        _qwen_rerank = Qwen3RerankAdapter(model_path=settings.QWEN_RERANK_PATH)
    return _qwen_rerank
