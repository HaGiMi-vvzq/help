"""轻量事件总线 — 替代 agentmemory 的 hooks 机制。

FastAPI 中每个请求可以注入 EventBus，在关键操作点触发事件：
- 用户注册 → 更新技能图谱
- 发布需求 → 记行为日志
- 查看匹配 → 记行为日志
- 反馈 → 记行为日志 + 检查是否触发 LLM 反思
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event: str, handler: EventHandler) -> None:
        self._handlers[event].append(handler)

    async def emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        data = data or {}
        for handler in self._handlers.get(event, []):
            try:
                await handler(event, data)
            except Exception:
                logger.exception("Event handler failed for %s", event)

    async def emit_background(self, event: str, data: dict[str, Any] | None = None) -> None:
        asyncio.create_task(self.emit(event, data))


_global_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus
