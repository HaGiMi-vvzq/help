"""MCP Server — 将核心匹配能力暴露给 Claude Code。

每个 tool 直接调用 Skill/Agent 的本地实现，无需 HTTP 中转。
启动: python -m app.mcp.server
"""

import json
import os
import sqlite3
import asyncio
import logging

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
mcp = FastMCP("campus-match")

# Lazy init on first use
_skills_loaded = False


def _ensure_skills():
    global _skills_loaded
    if _skills_loaded:
        return
    from app.skills.registry import SkillRegistry
    from app.skills.tag_skill import TagSkill
    from app.skills.embed_skill import EmbedSkill
    from app.skills.match_skill import MatchSkill
    from app.skills.explain_skill import ExplainSkill
    from app.skills.moderate_skill import ModerateSkill

    SkillRegistry.register(TagSkill())
    SkillRegistry.register(EmbedSkill())
    SkillRegistry.register(MatchSkill())
    SkillRegistry.register(ExplainSkill())
    SkillRegistry.register(ModerateSkill())
    _skills_loaded = True


@mcp.tool
def analyze_skill_tags(text: str) -> str:
    """从自然语言描述中提取结构化技能标签。输入用户的自由描述，返回技能标签列表。"""
    _ensure_skills()
    from app.skills.registry import SkillRegistry

    tag_skill = SkillRegistry.get("tag_extraction")
    result = asyncio.run(tag_skill.execute({"text": text}))
    return json.dumps(result.get("tags", []), ensure_ascii=False)


@mcp.tool
def embed_text(text: str) -> str:
    """将文本转为语义向量。返回向量的前10个维度和总维度。"""
    _ensure_skills()
    from app.skills.registry import SkillRegistry

    embed_skill = SkillRegistry.get("embedding")
    result = asyncio.run(embed_skill.execute({"text": text}))
    emb = result.get("embedding", [])
    return json.dumps({"dim": len(emb), "preview": emb[:10], "note": "仅展示前10维"}, ensure_ascii=False)


@mcp.tool
def moderate_content(text: str) -> str:
    """检测用户输入是否包含不安全内容。返回审核结果。"""
    from app.guardrails.content_filter import ContentFilter

    ok, reason = asyncio.run(ContentFilter.check_input(text))
    return json.dumps({"safe": ok, "reason": reason}, ensure_ascii=False)


@mcp.tool
def search_users(need_description: str, top_k: int = 5) -> str:
    """根据需求描述搜索匹配用户。本地调用 Qwen3 embedding + 向量匹配。"""
    _ensure_skills()
    from app.skills.registry import SkillRegistry

    embed_skill = SkillRegistry.get("embedding")
    match_skill = SkillRegistry.get("vector_match")

    emb_result = asyncio.run(embed_skill.execute({"text": need_description}))
    query_emb = emb_result["embedding"]

    # Build mock candidates from registered users — for full DB access, use backend HTTP API
    candidates = []
    import sqlite3
    try:
        import os
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app.db")
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT id, username, skill_tags, bio, school, profile_embedding FROM users").fetchall()
        for r in rows:
            if r[5]:
                candidates.append({
                    "id": r[0], "username": r[1], "skill_tags": json.loads(r[2]) if r[2] else [],
                    "bio": r[3], "school": r[4], "embedding": json.loads(r[5]) if r[5] else None,
                })
        conn.close()
    except Exception:
        pass

    if not candidates:
        return json.dumps({"error": "No users in database. Run seed.py first."})

    result = asyncio.run(match_skill.execute(
        {"query_embedding": query_emb, "candidates": candidates, "top_k": top_k}
    ))
    matches = result["matches"]
    return json.dumps(
        [{"id": m["id"], "username": m.get("username", ""), "similarity": m["similarity"]} for m in matches],
        ensure_ascii=False, indent=2,
    )


@mcp.tool
def list_skills() -> str:
    """列出所有已注册的 AI 技能。"""
    _ensure_skills()
    from app.skills.registry import SkillRegistry

    skills = SkillRegistry.list_all()
    return json.dumps(skills, ensure_ascii=False, indent=2)


def run():
    mcp.run()


if __name__ == "__main__":
    run()
