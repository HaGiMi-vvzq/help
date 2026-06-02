import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import SkillCooccurrence


class SkillGraph:
    def __init__(self):
        self._graph: dict[str, dict[str, int]] = defaultdict(dict)

    def add_co_occurrence(self, tags: list[str]) -> None:
        for i, a in enumerate(tags):
            for b in tags[i + 1 :]:
                if a == b:
                    continue
                key = (a, b) if a < b else (b, a)
                self._graph[key[0]][key[1]] = self._graph[key[0]].get(key[1], 0) + 1

    async def load_from_db(self, db: AsyncSession) -> None:
        result = await db.execute(select(SkillCooccurrence))
        for row in result.scalars():
            a, b = row.skill_a, row.skill_b
            key = (a, b) if a < b else (b, a)
            self._graph[key[0]][key[1]] = row.count

    async def save_to_db(self, db: AsyncSession) -> None:
        for skill_a, related in self._graph.items():
            for skill_b, count in related.items():
                a, b = (skill_a, skill_b) if skill_a < skill_b else (skill_b, skill_a)
                result = await db.execute(
                    select(SkillCooccurrence).where(
                        SkillCooccurrence.skill_a == a, SkillCooccurrence.skill_b == b
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.count = count
                else:
                    db.add(SkillCooccurrence(skill_a=a, skill_b=b, count=count))
        await db.commit()

    def expand(self, tag: str, depth: int = 1) -> list[str]:
        if depth <= 0:
            return []
        # 正向边: graph[tag] → {related_skill: count}
        related = list(self._graph.get(tag, {}).keys())
        # 反向边: 其他 tag 作为 outer_key 时，此 tag 作为 value
        for outer_key, inner_dict in self._graph.items():
            if tag in inner_dict and outer_key not in related:
                related.append(outer_key)
        if depth > 1:
            for r in related[:]:
                related.extend(self.expand(r, depth - 1))
        return list(set(related))

    def expand_multi(self, tags: list[str]) -> list[str]:
        results = set()
        for tag in tags:
            results.update(self.expand(tag))
        return list(results - set(tags))

    def to_file(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._graph, f, ensure_ascii=False, indent=2)

    def from_file(self, path: str) -> None:
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                self._graph = defaultdict(dict, {k: dict(v) for k, v in data.items()})

    def __len__(self) -> int:
        return sum(len(v) for v in self._graph.values())


_skill_graph: SkillGraph | None = None


def get_skill_graph() -> SkillGraph:
    global _skill_graph
    if _skill_graph is None:
        _skill_graph = SkillGraph()
    return _skill_graph
