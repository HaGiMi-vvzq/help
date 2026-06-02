from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.need import Need
from app.models.user import User
from app.skills.registry import SkillRegistry

OPEN_STATUS = "\u5f00\u653e"
KEYWORD_HINTS = (
    "\u7b97\u6cd5",
    "\u7b97\u6cd5\u6bd4\u8d5b",
    "\u7b97\u6cd5\u7ade\u8d5b",
    "\u7ade\u8d5b",
    "ACM",
    "\u5237\u9898",
    "\u9ed1\u5ba2\u677e",
    "\u53ef\u89c6\u5316",
    "\u6570\u636e\u5206\u6790",
    "\u524d\u7aef",
    "\u540e\u7aef",
    "\u8bbe\u8ba1",
    "\u8def\u6f14",
    "\u5efa\u6a21",
)


def _build_reason(overlap: list[str], similarity: float, need: Need) -> str:
    if overlap:
        focus = ", ".join(overlap[:3])
        return f"The requirement overlaps with your skills in {focus}, so it is a strong collaboration fit."
    if similarity >= 0.75:
        return f"Your background is close to the overall direction of {need.title}, so it is worth reaching out."
    return f"This {need.type} opportunity is adjacent to your experience and is worth a follow-up chat."


def _keyword_similarity(query_text: str, need: Need, query_tags: list[str]) -> float:
    haystack = " ".join(
        part
        for part in [
            need.title or "",
            need.description or "",
            need.type or "",
            " ".join(need.req_tags or []),
        ]
        if part
    )
    matched = 0
    for term in list(KEYWORD_HINTS) + list(query_tags):
        if term and term in query_text and term in haystack:
            matched += 1
    if matched == 0:
        return 0.0
    return min(0.95, 0.55 + matched * 0.12)


async def recommend_needs_for_user(
    db: AsyncSession,
    user: User,
    message: str,
    *,
    top_k: int = 4,
) -> list[dict]:
    result = await db.execute(
        select(Need).where(
            Need.user_id != user.id,
            Need.status == OPEN_STATUS,
            Need.need_embedding.isnot(None),
        )
    )
    open_needs = result.scalars().all()
    if not open_needs:
        return []

    query_text = " ".join(
        part for part in [message.strip(), user.bio or "", " ".join(user.skill_tags or [])] if part
    ).strip()
    if not query_text:
        query_text = " ".join(user.skill_tags or []) or (user.bio or "")
    if not query_text:
        return []

    embed_skill = SkillRegistry.get("embedding")
    match_skill = SkillRegistry.get("vector_match")
    tag_skill = SkillRegistry.get("tag_extraction")

    query_embedding = user.profile_embedding
    if not query_embedding:
        query_embedding = (await embed_skill.execute({"text": query_text}))["embedding"]

    query_tags = (await tag_skill.execute({"text": query_text})).get("tags", []) or (user.skill_tags or [])

    match_result = await match_skill.execute(
        {
            "query_embedding": query_embedding,
            "candidates": [
                {
                    "need_id": need.id,
                    "title": need.title,
                    "description": need.description,
                    "type": need.type,
                    "req_tags": need.req_tags or [],
                    "selection_mode": need.selection_mode or "single",
                    "owner_id": need.user_id,
                    "embedding": need.need_embedding,
                }
                for need in open_needs
            ],
            "top_k": max(top_k * 2, top_k),
        }
    )

    need_map = {need.id: need for need in open_needs}
    owner_result = await db.execute(select(User).where(User.id.in_({need.user_id for need in open_needs})))
    owner_map = {owner.id: owner for owner in owner_result.scalars().all()}

    vector_scores = {
        raw.get("need_id"): float(raw.get("similarity") or 0)
        for raw in match_result.get("matches", [])
    }

    scored: list[dict] = []
    for need in open_needs:
        keyword_similarity = _keyword_similarity(query_text, need, query_tags)
        similarity = max(vector_scores.get(need.id, 0.0), keyword_similarity)
        if similarity <= 0:
            continue
        need = need_map.get(need.id)
        if need is None:
            continue
        req_tags = need.req_tags or []
        overlap = [tag for tag in query_tags if tag in req_tags]
        overlap_ratio = len(overlap) / max(len(req_tags), 1)
        blended = similarity * 0.75 + overlap_ratio * 0.25
        owner = owner_map.get(need.user_id)
        scored.append(
            {
                "need_id": need.id,
                "title": need.title,
                "type": need.type,
                "owner_id": need.user_id,
                "owner_name": owner.username if owner else "",
                "selection_mode": need.selection_mode or "single",
                "req_tags": req_tags,
                "score": blended,
                "reason": _build_reason(overlap, similarity, need),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    top_items = scored[:top_k]
    if not top_items:
        return []

    max_score = top_items[0]["score"] or 1.0
    min_score = top_items[-1]["score"] if len(top_items) > 1 else max_score
    score_range = (max_score - min_score) or 1.0
    for index, item in enumerate(top_items):
        normalized = int(((item["score"] - min_score) / score_range) * 35 + 65)
        if index == 0:
            normalized = max(normalized, 90)
        item["score"] = min(100, max(60, normalized))
    return top_items
