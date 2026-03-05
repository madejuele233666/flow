"""事件总线 (Event Bus) — 模块间解耦的核心枢纽.

所有模块之间的通信通过事件总线进行，而不是直接调用。
这允许任意模块在不知道彼此存在的情况下进行协作。

Phase 5 升级：
- 前台事件 (emit)        : await 全部处理器，保证顺序与一致性
- 后台事件 (emit_background) : Fire-and-Forget，不阻塞主业务回路
- 死信回调 (dead_letter_callback) : 超出重试次数的失败事件可外挂处理

用法示例:
    bus = EventBus()
    bus.subscribe(EventType.TASK_CREATED, my_handler)
    await bus.emit(EventType.TASK_CREATED, {"task_id": 1})

    # 非关键路径事件（截屏、Webhook 通知等）
    bus.emit_background(EventType.CONTEXT_CAPTURED, {"task_id": 1})
"""

from __future__ import annotations

import asyncio
import inspect
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
# 后台事件工作器 — 纯异步消费队列，与 EventBus 完全解耦
# ---------------------------------------------------------------------------

@dataclass
class _DeadLetterEntry:
    """死信记录 — 超出重试上限的失败事件."""

    event: Event
    handler_name: str
    error: Exception
    attempts: int


class BackgroundEventWorker:
    """后台事件消费器 — 非阻塞 Fire-and-Forget 事件处理.

    设计要点：
    - 拥有自己的 asyncio.Queue，与 EventBus 的前台路径完全隔离。
    - 失败自动重试（次数可配），超限后推入死信回调。
    - 通过 start() / stop() 管理生命周期，适配未来的 Daemon 模式。

    用法：
        worker = BackgroundEventWorker(max_retries=3)
        worker.start()
        worker.enqueue(event, [handler_a, handler_b])
        # ... 应用退出时
        await worker.stop()
    """

    def __init__(
        self,
        max_retries: int = 2,
        dead_letter_callback: Callable[[_DeadLetterEntry], None] | None = None,
    ) -> None:
        self._queue: asyncio.Queue[tuple[Event, list[Callable]]] = asyncio.Queue()
        self._max_retries = max_retries
        self._dead_letter_callback = dead_letter_callback or self._default_dead_letter
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        """启动后台消费循环."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._consume_loop())
        logger.debug("BackgroundEventWorker started")

    async def stop(self) -> None:
        """优雅关闭 — 等待队列排空后退出."""
        self._running = False
        if self._task:
            # 写入哨兵值通知循环结束
            await self._queue.put((None, []))  # type: ignore[arg-type]
            await self._task
            self._task = None
        logger.debug("BackgroundEventWorker stopped")

    def enqueue(self, event: Event, handlers: list[Callable]) -> None:
        """将事件与处理器列表投入后台队列. 非阻塞调用，绝不 await."""
        try:
            self._queue.put_nowait((event, handlers))
        except asyncio.QueueFull:
            logger.warning("background queue full, dropping event %s", event.type.value)

    # ── 内部实现 ──

    async def _consume_loop(self) -> None:
        """持续消费队列直至收到停止信号."""
        while self._running:
            item = await self._queue.get()
            event, handlers = item
            if event is None:  # 哨兵值
                break
            for handler in handlers:
                await self._execute_with_retry(event, handler)
            self._queue.task_done()

    async def _execute_with_retry(self, event: Event, handler: Callable) -> None:
        """带限次重试的安全执行."""
        handler_name = getattr(handler, "__qualname__", repr(handler))
        for attempt in range(1, self._max_retries + 1):
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    await asyncio.to_thread(handler, event)
                return  # 成功，结束
            except Exception as exc:
                logger.warning(
                    "background handler %s failed (attempt %d/%d): %s",
                    handler_name, attempt, self._max_retries, exc,
                )
                if attempt == self._max_retries:
                    self._dead_letter_callback(_DeadLetterEntry(
                        event=event,
                        handler_name=handler_name,
                        error=exc,
                        attempts=attempt,
                    ))

    @staticmethod
    def _default_dead_letter(entry: _DeadLetterEntry) -> None:
        """默认死信处理 — 仅记录日志，不崩溃."""
        logger.error(
            "DEAD LETTER: handler %s failed %d times for %s: %s",
            entry.handler_name, entry.attempts, entry.event.type.value, entry.error,
        )


# ---------------------------------------------------------------------------
# 事件总线
# ---------------------------------------------------------------------------

class EventBus:
    """进程内的发布/订阅事件总线.

    Phase 5 升级：
    - emit()            : 前台同步路径，await 全部处理器完成
    - emit_background() : 后台异步路径，投入 Worker 队列后立即返回
    - 两条路径共享同一份订阅者注册表，但执行方式完全隔离

    线程安全暂不考虑（CLI 单线程 + asyncio 场景）。
    """

    def __init__(
        self,
        background_worker: BackgroundEventWorker | None = None,
    ) -> None:
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}
        self._bg_worker = background_worker

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

    async def emit(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        """发布前台事件 — 等待全部处理器完成后返回.

        适用于业务关键路径（如状态变更广播），调用方需要保证一致性。
        """
        event = Event(type=event_type, data=data or {})
        handlers = self._subscribers.get(event_type, [])
        logger.debug("emit %s → %d handlers", event_type.value, len(handlers))

        if not handlers:
            return

        async def _run_handler(h: Callable) -> None:
            try:
                if inspect.iscoroutinefunction(h):
                    await h(event)
                else:
                    await asyncio.to_thread(h, event)
            except Exception:
                logger.exception("handler %s failed for %s", h.__qualname__, event_type.value)

        await asyncio.gather(*[_run_handler(h) for h in handlers])

    def emit_background(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        """发布后台事件 — 投入队列后立即返回，绝不阻塞调用方.

        适用于非关键路径（截屏保存、Webhook 通知、统计打点等）。
        若无 BackgroundEventWorker 注入，则静默降级为日志警告。
        """
        event = Event(type=event_type, data=data or {})
        handlers = self._subscribers.get(event_type, [])

        if not handlers:
            return

        if self._bg_worker:
            self._bg_worker.enqueue(event, handlers)
        else:
            logger.warning(
                "emit_background called without BackgroundEventWorker, "
                "falling back to fire-and-forget for %s",
                event_type.value,
            )
            # 优雅降级：不 await，不阻塞
            for h in handlers:
                asyncio.ensure_future(self._safe_fire(h, event))

    def clear(self) -> None:
        """清空全部订阅（主要用于测试）."""
        self._subscribers.clear()

    # ── 内部辅助 ──

    @staticmethod
    async def _safe_fire(handler: Callable, event: Event) -> None:
        """完全静默的安全执行 — 仅用于无 Worker 的降级场景."""
        try:
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                await asyncio.to_thread(handler, event)
        except Exception:
            logger.exception("fire-and-forget handler %s failed", handler.__qualname__)
