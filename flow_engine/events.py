"""事件总线 (Event Bus) — 模块间解耦的核心枢纽.

所有模块之间的通信通过事件总线进行，而不是直接调用。
这允许任意模块在不知道彼此存在的情况下进行协作。

用法示例:
    bus = EventBus()
    bus.subscribe("task.started", my_handler)
    bus.emit("task.started", {"task_id": 1})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 事件定义
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    """系统内所有事件类型的注册表.

    新模块通过在此处添加事件类型来声明自身行为，而不是硬编码字符串。
    """

    # ── 任务生命周期 ──
    TASK_CREATED = "task.created"
    TASK_STATE_CHANGED = "task.state_changed"
    TASK_DELETED = "task.deleted"
    TASK_UPDATED = "task.updated"

    # ── 上下文 / 快照 ──
    CONTEXT_CAPTURED = "context.captured"
    CONTEXT_RESTORED = "context.restored"

    # ── 存储 ──
    STORAGE_SAVED = "storage.saved"
    STORAGE_COMMITTED = "storage.committed"

    # ── 调度 ──
    SCHEDULE_RECALCULATED = "schedule.recalculated"

    # ── 计时 ──
    FOCUS_TIMER_TICK = "focus.timer.tick"
    FOCUS_BREAK_SUGGESTED = "focus.break_suggested"


@dataclass(frozen=True)
class Event:
    """不可变的事件载荷."""

    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 处理器协议
# ---------------------------------------------------------------------------

class EventHandler(Protocol):
    """事件处理器的鸭子类型协议 — 任何可调用对象均可."""

    def __call__(self, event: Event) -> None: ...


# ---------------------------------------------------------------------------
# 事件总线
# ---------------------------------------------------------------------------

class EventBus:
    """进程内的发布/订阅事件总线.

    线程安全暂不考虑（CLI 单线程场景）。
    未来如需异步，可替换为 asyncio 版本，接口保持一致。
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}

    # ── 公共 API ──

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """注册事件监听器."""
        self._subscribers.setdefault(event_type, []).append(handler)
        logger.debug("subscribed %s → %s", event_type.value, handler.__qualname__)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """移除事件监听器."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        """发布事件，同步通知所有订阅者."""
        event = Event(type=event_type, data=data or {})
        handlers = self._subscribers.get(event_type, [])
        logger.debug("emit %s → %d handlers", event_type.value, len(handlers))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("handler %s failed for %s", handler.__qualname__, event_type.value)

    def clear(self) -> None:
        """清空全部订阅（主要用于测试）."""
        self._subscribers.clear()
