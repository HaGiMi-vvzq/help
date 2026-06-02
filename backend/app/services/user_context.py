"""用户上下文收集 — 为 AI 个性化提供用户画像数据。

收集用户在系统中的历史行为、偏好、写作风格，注入 prompt 实现"自进化"。
"""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.need import Need
from app.models.behavior import UserPreferenceProfile, UserBehaviorLog
from app.models.user import User


async def build_user_context(db: AsyncSession, user: User) -> str:
    """构建用户画像文本，供 AI 个性化生成/润色使用。"""
    parts = []

    # 1. 基本信息
    parts.append(f"用户名: {user.username}")
    if user.bio:
        parts.append(f"个人简介: {user.bio}")
    if user.skill_tags:
        parts.append(f"技能标签: {', '.join(user.skill_tags)}")
    if user.school:
        parts.append(f"学校: {user.school}")
    if user.extra:
        extra = user.extra
        if isinstance(extra, dict):
            if extra.get("campus"):
                parts.append(f"校区: {extra['campus']}")
            if extra.get("college"):
                parts.append(f"学院: {extra['college']}")
            if extra.get("major"):
                parts.append(f"专业: {extra['major']}")
            if extra.get("town"):
                parts.append(f"所在乡镇: {extra['town']}")

    # 2. 偏好向量（来自 LLM 反思）
    pref_result = await db.execute(
        select(UserPreferenceProfile).where(UserPreferenceProfile.user_id == user.id)
    )
    profile = pref_result.scalar_one_or_none()
    if profile:
        if profile.preference_vector:
            prefs = profile.preference_vector
            pref_strs = []
            for k, v in prefs.items():
                if isinstance(v, (int, float)) and v > 0.3:
                    pref_strs.append(f"{k}(权重{v:.1f})")
                elif isinstance(v, list):
                    pref_strs.append(f"{k}={v}")
            if pref_strs:
                parts.append(f"偏好模式: {', '.join(pref_strs)}")
        if profile.behavioral_tags:
            tags = profile.behavioral_tags
            if isinstance(tags, list) and tags:
                parts.append(f"行为特征: {', '.join(tags[:5])}")
        if profile.reflection_count > 0:
            parts.append(f"已自我进化 {profile.reflection_count} 次")

    # 3. 历史需求（写作风格参考）
    need_result = await db.execute(
        select(Need)
        .where(Need.user_id == user.id)
        .order_by(desc(Need.created_at))
        .limit(5)
    )
    past_needs = need_result.scalars().all()
    if past_needs:
        style_samples = []
        for n in past_needs[:3]:
            style_samples.append(f"- [{n.type}] {n.title}: {n.description[:80]}")
        parts.append(f"历史需求风格:\n" + "\n".join(style_samples))

    # 4. 近期行为统计
    log_result = await db.execute(
        select(UserBehaviorLog)
        .where(UserBehaviorLog.user_id == user.id)
        .order_by(desc(UserBehaviorLog.created_at))
        .limit(20)
    )
    logs = log_result.scalars().all()
    if logs:
        event_counts = {}
        for l in logs:
            event_counts[l.event_type] = event_counts.get(l.event_type, 0) + 1
        parts.append(f"近期行为: {event_counts}")

    return "\n".join(parts)
