"""HUD 事件总线 (Event Bus) — 基于 Qt Signal/Slot 的跨线程安全实现.

对标主引擎 events.py — 全能力复刻，关键适配：
- 主引擎使用 asyncio 单线程路由，无需跨线程处理。
- HUD 面临 pynput 后台线程 → Qt 主线程的跨线程通信，
  必须使用 Qt Signal + Qt.QueuedConnection 作为唯一安全手段。
- HudBackgroundEventWorker 的队列从 asyncio.Queue 改为 queue.Queue
  （线程安全），消费循环跑在独立 threading.Thread 中。

双路径设计:
    emit()            : 前台同步路径 — Qt Signal 跨线程安全投递，等待 handler 完成
    emit_background() : 后台异步路径 — 投入 Worker 队列后立即返回

用法:
    bus = HudEventBus()
    bus.subscribe(HudEventType.MOUSE_GLOBAL_MOVE, my_handler)
    bus.emit(HudEventType.MOUSE_GLOBAL_MOVE, MouseMovePayload(x=100, y=200))
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal, Qt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 事件类型注册表
# ---------------------------------------------------------------------------

class HudEventType(str, Enum):
    """HUD 内所有事件类型的注册表.

    新增事件时，必须同步在 events_payload.py 中新增对应的载荷 dataclass。
    """

    MOUSE_GLOBAL_MOVE    = "mouse.global_move"      # 全局鼠标坐标更新
    STATE_TRANSITIONED   = "state.transitioned"     # HUD 状态转换完成广播
    IPC_MESSAGE_RECEIVED = "ipc.message_received"   # 来自 Flow Engine 的 IPC 消息
    WIDGET_REGISTERED    = "widget.registered"      # UI 插槽注册通知


# ---------------------------------------------------------------------------
# 事件容器
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HudEvent:
    """不可变的 HUD 事件容器.

    payload 为强类型载荷（如 MouseMovePayload），
    对标主引擎 Event(frozen=True) — type, timestamp, payload 结构完全一致。
    """

    type: HudEventType
    timestamp: datetime = field(default_factory=datetime.now)
    payload: Any = None


# ---------------------------------------------------------------------------
# 死信记录
# ---------------------------------------------------------------------------

@dataclass
class _DeadLetterEntry:
    """死信记录 — 超出重试上限的失败事件."""

    event: HudEvent
    handler_name: str
    error: Exception
    attempts: int


# ---------------------------------------------------------------------------
# 后台事件消费器 — 线程安全，适配 Qt 线程模型
# ---------------------------------------------------------------------------

class HudBackgroundEventWorker:
    """后台事件消费器 — 非阻塞 Fire-and-Forget 事件处理.

    对标主引擎 BackgroundEventWorker，关键适配：
    - 使用 queue.Queue（线程安全）代替 asyncio.Queue，适配 Qt 线程模型。
    - 消费循环运行在独立的 threading.Thread 中（非 asyncio 协程）。
    - 失败自动重试（次数可配），超限后推入死信回调。
    - 通过 start() / stop() 管理生命周期。

    用法:
        worker = HudBackgroundEventWorker(max_retries=2)
        worker.start()
        worker.enqueue(event, [handler_a, handler_b])
        # 退出时
        worker.stop(timeout=5.0)
    """

    _SENTINEL = object()  # 哨兵值，通知消费循环退出

    def __init__(
        self,
        max_retries: int = 2,
        dead_letter_callback: Callable[[_DeadLetterEntry], None] | None = None,
    ) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._max_retries = max_retries
        self._dead_letter_callback = dead_letter_callback or self._default_dead_letter
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """启动后台消费线程."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._consume_loop,
            name="HudBgEventWorker",
            daemon=True,  # 守护线程，主线程退出时自动销毁
        )
        self._thread.start()
        logger.debug("HudBackgroundEventWorker started")

    def stop(self, timeout: float = 5.0) -> None:
        """优雅关闭 — 等待队列排空后退出.

        Args:
            timeout: 等待线程退出的最大秒数。
        """
        self._running = False
        if self._thread and self._thread.is_alive():
            self._queue.put(self._SENTINEL)  # 写入哨兵值通知循环结束
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.debug("HudBackgroundEventWorker stopped")

    def enqueue(self, event: HudEvent, handlers: list[Callable]) -> None:
        """将事件与处理器列表投入后台队列. 非阻塞调用。"""
        try:
            self._queue.put_nowait((event, handlers))
        except queue.Full:
            logger.warning("background queue full, dropping event %s", event.type.value)

    # ── 内部实现 ──

    def _consume_loop(self) -> None:
        """持续消费队列直至收到停止信号."""
        while True:
            item = self._queue.get()
            if item is self._SENTINEL:
                break
            event, handlers = item
            for handler in handlers:
                self._execute_with_retry(event, handler)
            self._queue.task_done()

    def _execute_with_retry(self, event: HudEvent, handler: Callable) -> None:
        """带限次重试的安全执行."""
        handler_name = getattr(handler, "__qualname__", repr(handler))
        for attempt in range(1, self._max_retries + 1):
            try:
                handler(event)
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
# HUD 事件总线 — 跨线程安全，基于 Qt Signal/Slot
# ---------------------------------------------------------------------------

class HudEventBus(QObject):
    """跨线程安全的 HUD 事件总线.

    对标主引擎 EventBus，关键适配：
    - 继承 QObject，使用 Qt Signal 作为底层跨线程路由机制。
    - _signal 使用 Qt.QueuedConnection 确保任何线程发出的信号
      都被安全压入 Qt 主事件队列，在主线程中执行 handler。
    - 这是解决 pynput 子线程 → Qt 主线程竞争的唯一安全手段。

    双路径:
        emit()            : 前台同步路径（通过 Qt Signal 跨线程安全投递）
        emit_background() : 后台异步路径（投入 Worker 队列后立即返回）
    """

    # Qt Signal 签名: (event_type_str: str, payload: object)
    # 使用 object 类型以接受任意 Python 对象（包括 frozen dataclass）
    _signal = Signal(str, object)

    def __init__(
        self,
        background_worker: HudBackgroundEventWorker | None = None,
    ) -> None:
        super().__init__()
        self._subscribers: dict[HudEventType, list[Callable]] = {}
        self._bg_worker = background_worker

        # QueuedConnection 确保跨线程安全：信号在主线程 event loop 中分发
        self._signal.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    # ── 公共 API ──

    def subscribe(self, event_type: HudEventType, handler: Callable) -> None:
        """注册事件监听器."""
        self._subscribers.setdefault(event_type, []).append(handler)
        logger.debug("subscribed %s → %s", event_type.value, getattr(handler, "__qualname__", repr(handler)))

    def unsubscribe(self, event_type: HudEventType, handler: Callable) -> None:
        """移除事件监听器."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event_type: HudEventType, payload: Any = None) -> None:
        """发布前台事件 — Qt Signal 确保跨线程安全.

        对标 payload-integrity.md — 强制实施载荷完整性：
        - 必须是 dataclass
        - 必须是 frozen=True（事件为只读通知）
        """
        if payload is not None:
            if not is_dataclass(payload):
                raise TypeError(f"Event payload must be a dataclass, got {type(payload)}")
            if not getattr(payload.__class__, "__dataclass_params__").frozen:
                raise TypeError(f"Event payload must be frozen (frozen=True), got {type(payload)}")

        logger.debug("emit %s", event_type.value)
        self._signal.emit(event_type.value, payload)

    def emit_background(self, event_type: HudEventType, payload: Any = None) -> None:
        """发布后台事件 — 投入 Worker 队列后立即返回，绝不阻塞调用方.

        适用于非关键路径（统计打点、日志上报等）。
        若无 HudBackgroundEventWorker 注入，则静默降级为日志警告。
        """
        event = HudEvent(type=event_type, payload=payload)
        handlers = list(self._subscribers.get(event_type, []))

        if not handlers:
            return

        if self._bg_worker:
            self._bg_worker.enqueue(event, handlers)
        else:
            logger.warning(
                "emit_background called without HudBackgroundEventWorker, "
                "dropping event %s",
                event_type.value,
            )

    def clear(self) -> None:
        """清空全部订阅（主要用于测试）."""
        self._subscribers.clear()

    # ── 内部辅助 ──

    def _dispatch(self, event_type_str: str, payload: Any) -> None:
        """Qt 主线程中实际执行订阅者回调.

        此方法由 Qt 事件系统在主线程中调用，保证线程安全。
        """
        try:
            event_type = HudEventType(event_type_str)
        except ValueError:
            logger.warning("unknown event type received in dispatch: %s", event_type_str)
            return

        event = HudEvent(type=event_type, payload=payload)
        handlers = list(self._subscribers.get(event_type, []))

        logger.debug("dispatch %s → %d handlers", event_type_str, len(handlers))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "handler %s failed for %s",
                    getattr(handler, "__qualname__", repr(handler)),
                    event_type_str,
                )
