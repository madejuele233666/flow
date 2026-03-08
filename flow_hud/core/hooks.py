"""HUD 钩子系统 (Hook System) — pluggy 启发的类型化钩子框架.

对标主引擎 hooks.py — 全能力复刻（HudHookStrategy×5 + HookBreaker + HudHookManager）。

【防腐规定】该文件内严禁出现任何 PySide6 或外设相关的 import。

执行策略:
    PARALLEL   : 全部执行，互不影响（默认）
    WATERFALL  : 链式传递，插件原地修改 payload
    BAIL       : 第一个非 None 结果胜出，后续跳过
    BAIL_VETO  : 全部执行，任一返回 False 则否决（一票否决权）
    COLLECT    : 收集所有返回值为列表

HUD 系统钩子:
    before_state_transition    : BAIL_VETO — 插件返回 False 可阻止状态转移
    on_after_state_transition  : PARALLEL  — 状态转移完成后并发通知
    before_widget_register     : WATERFALL — 插件可修改目标 UI 插槽

用法:
    mgr = HudHookManager(hook_timeout=0.5, failure_threshold=5, recovery_timeout=60)
    mgr.register(my_plugin)   # 自动扫描 my_plugin 上与 HUD_HOOK_SPECS 同名的方法
    approved = mgr.call(\"before_state_transition\", VetoTransitionPayload(...))
"""

from __future__ import annotations

import inspect
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 执行策略
# ---------------------------------------------------------------------------

class HudHookStrategy(str, Enum):
    """钩子执行策略（借鉴 Webpack Tapable）."""

    PARALLEL  = "parallel"   # 全部执行，忽略返回值
    WATERFALL = "waterfall"  # 链式传递，可原地修改 payload
    BAIL      = "bail"       # 第一个非 None 结果胜出
    BAIL_VETO = "bail_veto"  # 全部执行，任一 False 否决
    COLLECT   = "collect"    # 收集所有返回值


# ---------------------------------------------------------------------------
# 钩子规格声明
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HudHookSpec:
    """单个钩子的元信息."""

    name: str
    strategy: HudHookStrategy = HudHookStrategy.PARALLEL
    description: str = ""


# HUD 系统钩子注册表 — 插件只需实现同名方法即可自动挂载
HUD_HOOK_SPECS: dict[str, HudHookSpec] = {
    "before_state_transition": HudHookSpec(
        name="before_state_transition",
        strategy=HudHookStrategy.BAIL_VETO,
        description="状态转移前一票否决，插件返回 False 可阻止转移",
    ),
    "on_after_state_transition": HudHookSpec(
        name="on_after_state_transition",
        strategy=HudHookStrategy.PARALLEL,
        description="状态转移后并发通知",
    ),
    "before_widget_register": HudHookSpec(
        name="before_widget_register",
        strategy=HudHookStrategy.WATERFALL,
        description="UI 插槽注册前，插件可修改目标插槽",
    ),
}


# ---------------------------------------------------------------------------
# 熔断器 — 轻量级实现，无外部依赖
# ---------------------------------------------------------------------------

class _BreakerState(str, Enum):
    CLOSED    = "closed"     # 正常
    OPEN      = "open"       # 熔断（拒绝调用）
    HALF_OPEN = "half_open"  # 试探恢复中


class HookBreaker:
    """单个 handler 级别的熔断器.

    所有阈值参数从外部配置注入，不含任何硬编码数值。
    三态自动恢复: OPEN → HALF_OPEN（超过 recovery_timeout 后）→ CLOSED（成功后）。
    """

    def __init__(
        self,
        failure_threshold: int,
        recovery_timeout: float,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._state = _BreakerState.CLOSED
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> _BreakerState:
        """返回当前熔断器状态，自动处理时间窗口恢复."""
        if self._state == _BreakerState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._state = _BreakerState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        """记录成功，重置熔断器到 CLOSED 状态."""
        self._failure_count = 0
        self._state = _BreakerState.CLOSED

    def record_failure(self) -> None:
        """记录失败，达到阈值时触发熔断."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = _BreakerState.OPEN
            logger.warning(
                "HookBreaker OPEN: %d consecutive failures (threshold=%d)",
                self._failure_count, self._failure_threshold,
            )

    @property
    def is_open(self) -> bool:
        """返回熔断器是否处于 OPEN 状态（拒绝调用）."""
        return self.state == _BreakerState.OPEN


# ---------------------------------------------------------------------------
# HUD 钩子管理器
# ---------------------------------------------------------------------------

class HudHookManager:
    """HUD 钩子注册与调用中心.

    对标主引擎 HookManager — 完整功能复刻:
    - 每个 handler 绑定独立的 HookBreaker（熔断器）
    - 超时控制通过 hook_timeout 参数注入
    - safe_mode=True 时自动跳过全部钩子
    - dev_mode=True 时异常直接上抛，不静默

    用法:
        mgr = HudHookManager(hook_timeout=0.5, failure_threshold=5, recovery_timeout=60)
        mgr.register(my_plugin)
        result = mgr.call(\"before_state_transition\", VetoTransitionPayload(...))
    """

    def __init__(
        self,
        hook_timeout: float = 0.5,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        safe_mode: bool = False,
        dev_mode: bool = False,
    ) -> None:
        self._handlers: dict[str, list[Callable[..., Any]]] = {
            name: [] for name in HUD_HOOK_SPECS
        }
        # 每个 handler 独立的熔断器，以 id(handler) 为键
        self._breakers: dict[int, HookBreaker] = {}

        # 从配置注入的参数 — 零 Magic Numbers
        self._hook_timeout = hook_timeout
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._safe_mode = safe_mode
        self._dev_mode = dev_mode

    @property
    def safe_mode(self) -> bool:
        return self._safe_mode

    @property
    def dev_mode(self) -> bool:
        return self._dev_mode

    def register(self, implementor: object) -> list[str]:
        """扫描 implementor 上与 HUD_HOOK_SPECS 同名的方法并注册.

        Returns:
            成功注册的钩子名列表（用于日志/调试）。
        """
        registered: list[str] = []
        for hook_name in HUD_HOOK_SPECS:
            method = getattr(implementor, hook_name, None)
            if method is not None and callable(method):
                self._handlers[hook_name].append(method)
                # 为每个 handler 创建独立熔断器
                self._breakers[id(method)] = HookBreaker(
                    failure_threshold=self._failure_threshold,
                    recovery_timeout=self._recovery_timeout,
                )
                registered.append(hook_name)
        if registered:
            name = getattr(implementor, "name", type(implementor).__name__)
            logger.info("hooks registered for %s: %s", name, registered)
        return registered

    def unregister(self, implementor: object) -> None:
        """移除某个实现者的全部钩子."""
        for hook_name in HUD_HOOK_SPECS:
            method = getattr(implementor, hook_name, None)
            if method in self._handlers.get(hook_name, []):
                self._handlers[hook_name].remove(method)
                self._breakers.pop(id(method), None)

    def call(self, hook_name: str, payload: Any = None) -> Any:
        """按策略执行钩子（带熔断保护）.

        Note: HudHookManager 使用同步执行（非 async），以适配 Qt 主线程模型。
        主引擎使用 asyncio.gather，HUD 使用同步顺序执行（Qt 已提供事件循环）。

        Args:
            hook_name: 钩子名称（必须在 HUD_HOOK_SPECS 中声明）。
            payload: 强类型载荷对象（dataclass 实例）。

        Returns:
            根据策略不同：
            - PARALLEL   : None
            - WATERFALL  : 原样返回 payload（已被插件原地修改）
            - BAIL       : 第一个非 None 结果
            - BAIL_VETO  : True/False
            - COLLECT    : 所有返回值的列表
        """
        if self._safe_mode:
            return None

        spec = HUD_HOOK_SPECS.get(hook_name)
        if spec is None:
            logger.warning("unknown hook: %s", hook_name)
            return None

        handlers = self._handlers.get(hook_name, [])
        if not handlers:
            return [] if spec.strategy == HudHookStrategy.COLLECT else None

        strategy = spec.strategy

        if strategy == HudHookStrategy.PARALLEL:
            return self._call_parallel(hook_name, handlers, payload)
        elif strategy == HudHookStrategy.WATERFALL:
            return self._call_waterfall(hook_name, handlers, payload)
        elif strategy == HudHookStrategy.BAIL:
            return self._call_bail(hook_name, handlers, payload)
        elif strategy == HudHookStrategy.BAIL_VETO:
            return self._call_bail_veto(hook_name, handlers, payload)
        elif strategy == HudHookStrategy.COLLECT:
            return self._call_collect(hook_name, handlers, payload)
        return None

    def _safe_call(self, handler: Callable, payload: Any) -> Any:
        """带熔断 + 超时保护的安全调用.

        支持 sync handler（HUD 环境中钩子应为同步，以配合 Qt 主线程）。
        dev_mode=True 时异常直接上抛，不静默、不熔断。
        """
        breaker = self._breakers.get(id(handler))
        if breaker and breaker.is_open:
            logger.debug("HookBreaker OPEN for %s, skipping", handler)
            return None

        try:
            import signal as _signal_mod

            # 使用 threading.Timer 实现超时（兼容非主线程调用和 POSIX/Windows）
            result_container: list[Any] = [None]
            exc_container: list[BaseException | None] = [None]
            done_event = __import__("threading").Event()

            def _run() -> None:
                try:
                    result_container[0] = handler(payload)
                except Exception as e:
                    exc_container[0] = e
                finally:
                    done_event.set()

            # 在主线程中直接调用（最常见场景），避免不必要的线程开销
            # 若 handler 本身是同步的，直接调用即可；只有超时才用 Timer
            import threading
            t = threading.Thread(target=_run, daemon=True)
            t.start()
            finished = done_event.wait(timeout=self._hook_timeout)

            if not finished:
                if self._dev_mode:
                    raise TimeoutError(
                        f"hook handler {handler} timed out (limit={self._hook_timeout:.2f}s)"
                    )
                logger.warning(
                    "hook handler %s timed out (limit=%.2fs)", handler, self._hook_timeout
                )
                if breaker:
                    breaker.record_failure()
                return None

            if exc_container[0] is not None:
                if self._dev_mode:
                    raise exc_container[0]
                logger.exception("hook handler %s failed: %s", handler, exc_container[0])  # type: ignore[arg-type]
                if breaker:
                    breaker.record_failure()
                return None

            if breaker:
                breaker.record_success()
            return result_container[0]

        except TimeoutError:
            if self._dev_mode:
                raise
            logger.warning("hook handler %s timed out", handler)
            if breaker:
                breaker.record_failure()
            return None
        except Exception:
            if self._dev_mode:
                raise
            logger.exception("hook handler %s failed", handler)
            if breaker:
                breaker.record_failure()
            return None

    def _call_parallel(
        self, name: str, handlers: list[Callable], payload: Any,
    ) -> None:
        """并发执行所有 handler — 实际为顺序执行（Qt 主线程中无需并发）."""
        for handler in handlers:
            self._safe_call(handler, payload)

    def _call_waterfall(
        self, name: str, handlers: list[Callable], payload: Any,
    ) -> Any:
        """瀑布流执行 — 原地修改模式.

        约定：handler 接收可变 dataclass，通过原地修改属性来变更数据。
        handler 的返回值被忽略，所有修改都发生在 payload 本体上。
        最终返回被全部 handler 修改过的同一个 payload 对象。
        """
        for handler in handlers:
            self._safe_call(handler, payload)
        return payload

    def _call_bail(
        self, name: str, handlers: list[Callable], payload: Any,
    ) -> Any:
        """第一个非 None 结果胜出，后续跳过."""
        for handler in handlers:
            ret = self._safe_call(handler, payload)
            if ret is not None:
                return ret
        return None

    def _call_collect(
        self, name: str, handlers: list[Callable], payload: Any,
    ) -> list[Any]:
        """收集所有返回值为列表."""
        results = []
        for handler in handlers:
            ret = self._safe_call(handler, payload)
            if ret is not None:
                results.append(ret)
        return results

    def _call_bail_veto(
        self, name: str, handlers: list[Callable], payload: Any,
    ) -> bool:
        """一票否决执行 — 全部 handler 执行，任一返回 False 即否决.

        设计要点：
        - 所有 handler 都会被执行（不像 bail 那样早退）。
        - handler 返回 None 或 True 视为同意；仅返回 False 视为否决。
        - 返回 True 表示全部通过，False 表示被否决。
        """
        vetoed = False
        for handler in handlers:
            result = self._safe_call(handler, payload)
            if result is False:
                logger.info("hook %s vetoed by handler %s", name, getattr(handler, "__qualname__", handler))
                vetoed = True
        return not vetoed
