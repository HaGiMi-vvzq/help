import numpy as np

from app.skills.base import BaseSkill


class MatchSkill(BaseSkill):
    name = "vector_match"
    description = "用余弦相似度从候选池中检索 Top-N 匹配"
    version = "1.0.0"
    input_schema = {
        "type": "object",
        "properties": {
            "query_embedding": {"type": "array", "items": {"type": "number"}},
            "candidates": {"type": "array", "items": {"type": "object"}},
            "top_k": {"type": "integer", "default": 10},
        },
        "required": ["query_embedding", "candidates"],
    }
    output_schema = {
        "type": "object",
        "properties": {"matches": {"type": "array", "items": {"type": "object"}}},
    }
    tags = ["search", "similarity"]

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        a_arr = np.array(a)
        b_arr = np.array(b)
        dot = np.dot(a_arr, b_arr)
        norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
        if norm == 0:
            return 0.0
        return float(dot / norm)

    async def execute(self, input_data: dict) -> dict:
        query_emb = input_data["query_embedding"]
        candidates = input_data["candidates"]
        top_k = input_data.get("top_k", 10)

        scored = []
        for c in candidates:
            emb = c.get("embedding")
            if emb is None:
                continue
            sim = self.cosine_similarity(query_emb, emb)
            scored.append({**c, "similarity": round(sim, 4)})

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return {"matches": scored[:top_k]}
