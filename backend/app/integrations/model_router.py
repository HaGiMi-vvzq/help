from app.core.config import settings

ROUTING_RULES = {
    "tag_extraction": {"model": settings.DEEPSEEK_FLASH_MODEL, "temperature": 0.1, "max_tokens": 500, "timeout": 15},
    "rerank": {"model": settings.DEEPSEEK_PRO_MODEL, "temperature": 0.3, "max_tokens": 2000, "timeout": 30},
    "concierge": {"model": settings.DEEPSEEK_PRO_MODEL, "temperature": 0.7, "max_tokens": 1000, "timeout": 30},
    "reflection": {"model": settings.DEEPSEEK_PRO_MODEL, "temperature": 0.3, "max_tokens": 1500, "timeout": 30},
    "moderation": {"model": settings.DEEPSEEK_FLASH_MODEL, "temperature": 0.0, "max_tokens": 200, "timeout": 10},
    "file_analysis": {"model": settings.DEEPSEEK_FLASH_MODEL, "temperature": 0.1, "max_tokens": 800, "timeout": 30},
    "summarization": {"model": settings.DEEPSEEK_FLASH_MODEL, "temperature": 0.2, "max_tokens": 300, "timeout": 15},
    "agent_planner": {"model": settings.DEEPSEEK_PRO_MODEL, "temperature": 0.3, "max_tokens": 1000, "timeout": 30},
    "agent_chat": {"model": settings.DEEPSEEK_PRO_MODEL, "temperature": 0.7, "max_tokens": 1500, "timeout": 45},
    "intent_analysis": {"model": settings.DEEPSEEK_FLASH_MODEL, "temperature": 0.1, "max_tokens": 300, "timeout": 10},
}

DEFAULT_RULE = {"model": settings.DEEPSEEK_FLASH_MODEL, "temperature": 0.3, "max_tokens": 1000, "timeout": 20}


def route(task: str) -> dict:
    return ROUTING_RULES.get(task, DEFAULT_RULE)
