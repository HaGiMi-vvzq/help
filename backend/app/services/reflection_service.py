"""LLM 定期反思服务 — 自进化机制。

用户在累计 N 次反馈后，触发 LLM 分析行为模式，更新偏好权重。
借鉴 agentmemory 的 consolidation: Working → Semantic → Procedural。
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.models.behavior import UserBehaviorLog, UserPreferenceProfile
from app.models.match import Match

logger = logging.getLogger(__name__)

REFLECTION_TRIGGER_COUNT = 10


async def check_and_reflect(db: AsyncSession, user_id: int) -> dict | None:
    """检查是否达到反思阈值，若是则触发 LLM 反思。"""
    count_result = await db.execute(
        select(func.count()).select_from(UserBehaviorLog).where(UserBehaviorLog.user_id == user_id)
    )
    total_events = count_result.scalar() or 0

    profile_result = await db.execute(
        select(UserPreferenceProfile).where(UserPreferenceProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        return None

    # 每次反馈后检查：距离上次反思是否有足够新数据
    new_since_last = 0
    if profile.last_reflected_at:
        count_result = await db.execute(
            select(func.count())
            .select_from(UserBehaviorLog)
            .where(
                UserBehaviorLog.user_id == user_id,
                UserBehaviorLog.created_at > profile.last_reflected_at,
            )
        )
        new_since_last = count_result.scalar() or 0

    if new_since_last < REFLECTION_TRIGGER_COUNT:
        return None

    return await _run_reflection(db, user_id, profile)


async def _run_reflection(
    db: AsyncSession, user_id: int, profile: UserPreferenceProfile
) -> dict:
    """执行 LLM 反思，生成偏好调整。"""
    # Collect recent behavior data
    log_result = await db.execute(
        select(UserBehaviorLog)
        .where(UserBehaviorLog.user_id == user_id)
        .order_by(UserBehaviorLog.created_at.desc())
        .limit(50)
    )
    logs = log_result.scalars().all()

    match_result = await db.execute(
        select(Match).where(
            Match.need_id.in_(
                select(func.distinct(UserBehaviorLog.need_id)).where(
                    UserBehaviorLog.user_id == user_id,
                    UserBehaviorLog.need_id.isnot(None),
                )
            )
        )
    )
    matches = match_result.scalars().all()

    # Build reflection prompt
    behavior_summary = ""
    for log_item in logs:
        behavior_summary += (
            f"- event={log_item.event_type}, target_user={log_item.target_user_id}, "
            f"need={log_item.need_id}, time={log_item.created_at}\n"
        )

    feedback_summary = ""
    for m in matches:
        if m.feedback is not None:
            feedback_summary += f"- match_id={m.id}, score={m.score}, feedback={m.feedback}, reason={m.ai_reason}\n"

    system_prompt = (
        "你是用户行为分析专家。基于用户的行为日志和匹配反馈，"
        "分析用户在选择合作对象时的偏好模式。\n"
        "分析维度：① 同校 vs 跨校偏好 ② 技能互补 vs 同质偏好 "
        "③ 技术栈偏好 ④ 其他值得一提的模式\n"
        "输出 JSON，不要 markdown 代码块。"
    )

    user_prompt = (
        f"用户 ID={user_id}\n"
        f"当前偏好: {profile.preference_vector or '无'}\n\n"
        f"最近行为日志:\n{behavior_summary}\n\n"
        f"匹配反馈:\n{feedback_summary}\n\n"
        '输出 JSON:\n'
        '{"detected_preferences": {"同校偏好": <0-1>, "互补偏好": <0-1>, "技术偏好": ["..."]}, '
        '"behavioral_tags": ["..."], '
        '"strategy_adjustments": [{"action": "boost/penalize", "factor": "...", "weight": 1.0}]}'
    )

    client = get_ai_client()
    cfg = route("reflection")
    adapter = DeepSeekChatAdapter(client, model=cfg["model"])

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await adapter.chat_with_json(
            messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"]
        )
    except Exception:
        logger.exception("Reflection failed for user %d", user_id)
        return None

    # Update preference profile
    profile.preference_vector = result.get("detected_preferences", {})
    profile.behavioral_tags = result.get("behavioral_tags", [])
    profile.last_reflected_at = datetime.now(timezone.utc)
    profile.reflection_count += 1

    await db.commit()

    logger.info(
        "Reflection completed for user %d (#%d): %s",
        user_id, profile.reflection_count, profile.preference_vector,
    )

    return result
