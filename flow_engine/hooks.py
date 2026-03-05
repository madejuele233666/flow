"""钩子系统 (Hook System) — pluggy 启发的类型化钩子框架.

设计来源：
- pytest/pluggy: 框架声明钩子签名，插件选择性实现
- Webpack/Tapable: 不同钩子有不同执行策略

Phase 4 升级：
- 熔断器保护：第三方插件钩子执行超时自动熔断
- 全部阈值从 PluginBreakerConfig 注入，零 Magic Numbers
- safe_mode 一键跳过全部第三方钩子

Phase 5 升级：
- BAIL_VETO 策略：插件返回 False 即可一票否决状态流转
- before_task_transition 钩子：状态转移的前置拦截点

执行策略：
- parallel   : 全部执行，互不影响（默认）
- waterfall  : 链式传递，前一个结果传给下一个，可拦截
- bail       : 第一个非 None 结果胜出，后续跳过
- bail_veto  : 全部执行，任一返回 False 则否决（一票否决权）
- collect    : 收集所有返回值为列表
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 执行策略
# ---------------------------------------------------------------------------

class HookStrategy(str, Enum):
    """钩子执行策略（借鉴 Webpack Tapable）."""

    PARALLEL = "parallel"        # 全部执行，忽略返回值
    WATERFALL = "waterfall"      # 链式传递，可修改/拦截
    BAIL = "bail"                # 第一个非 None 结果胜出
    BAIL_VETO = "bail_veto"      # 全部执行，任一 False 否决
    COLLECT = "collect"          # 收集所有返回值


# ---------------------------------------------------------------------------
# 钩子规格声明
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HookSpec:
    """单个钩子的元信息."""

    name: str
    strategy: HookStrategy = HookStrategy.PARALLEL
    description: str = ""


# 全部系统钩子的注册表
# 插件只需实现同名方法即可自动挂载
HOOK_SPECS: dict[str, HookSpec] = {
    # ── 状态转移生命周期 ──
    "on_before_transition": HookSpec(
        name="on_before_transition",
        strategy=HookStrategy.WATERFALL,
        description="状态转移前，可拦截/修改目标状态",
    ),
    "on_after_transition": HookSpec(
        name="on_after_transition",
        strategy=HookStrategy.PARALLEL,
        description="状态转移后通知",
    ),
    "on_transition_error": HookSpec(
        name="on_transition_error",
        strategy=HookStrategy.PARALLEL,
        description="状态转移失败时通知",
    ),

    # ── 任务生命周期 ──
    "on_task_created": HookSpec(
        name="on_task_created",
        strategy=HookStrategy.PARALLEL,
        description="任务创建后",
    ),
    "on_task_deleted": HookSpec(
        name="on_task_deleted",
        strategy=HookStrategy.PARALLEL,
        description="任务删除后",
    ),

    # ── 上下文 ──
    "on_context_captured": HookSpec(
        name="on_context_captured",
        strategy=HookStrategy.PARALLEL,
        description="桌面快照捕获后",
    ),
    "on_context_restored": HookSpec(
        name="on_context_restored",
        strategy=HookStrategy.PARALLEL,
        description="桌面快照恢复后",
    ),

    # ── 调度 ──
    "on_rank_factor": HookSpec(
        name="on_rank_factor",
        strategy=HookStrategy.COLLECT,
        description="收集引力排序因子分数",
    ),
    "on_suggest_next": HookSpec(
        name="on_suggest_next",
        strategy=HookStrategy.BAIL,
        description="推荐下一个任务（第一个非 None 胜出）",
    ),

    # ── 存储 ──
    "on_before_save": HookSpec(
        name="on_before_save",
        strategy=HookStrategy.WATERFALL,
        description="保存前可修改任务数据",
    ),
    "on_after_save": HookSpec(
        name="on_after_save",
        strategy=HookStrategy.PARALLEL,
        description="保存后通知",
    ),

    # ── 专注 ──
    "on_focus_break": HookSpec(
        name="on_focus_break",
        strategy=HookStrategy.PARALLEL,
        description="建议休息时通知",
    ),

    # ── Phase 5: 状态流转拦截 ──
    "before_task_transition": HookSpec(
        name="before_task_transition",
        strategy=HookStrategy.BAIL_VETO,
        description="状态转移前的一票否决拦截点。返回 False 可阻止转移",
    ),
}


# ---------------------------------------------------------------------------
# 熔断器 — 轻量级实现，无外部依赖
# ---------------------------------------------------------------------------

class _BreakerState(str, Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断（拒绝调用）
    HALF_OPEN = "half_open"  # 试探恢复中


class HookBreaker:
    """单个 handler 级别的熔断器.

    所有阈值参数从外部配置注入，不含任何硬编码数值。
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
        if self._state == _BreakerState.OPEN:
            import time
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._state = _BreakerState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = _BreakerState.CLOSED

    def record_failure(self) -> None:
        import time
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = _BreakerState.OPEN
            logger.warning(
                "breaker OPEN: %d consecutive failures (threshold=%d)",
                self._failure_count, self._failure_threshold,
            )

    @property
    def is_open(self) -> bool:
        return self.state == _BreakerState.OPEN


# ---------------------------------------------------------------------------
# 钩子管理器（带熔断与超时保护，全异步）
# ---------------------------------------------------------------------------

class HookManager:
    """钩子注册与调用中心.

    Phase 4 增强：
    - 每个 handler 绑定独立的 HookBreaker（熔断器）
    - 超时控制通过 hook_timeout 参数注入
    - safe_mode=True 时自动跳过全部第三方钩子

    用法：
        mgr = HookManager(hook_timeout=0.5, failure_threshold=5, recovery_timeout=60)
        mgr.register(my_plugin)
        result = mgr.call("on_before_transition", task=task, target=state)
    """

    def __init__(
        self,
        hook_timeout: float = 0.5,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        safe_mode: bool = False,
    ) -> None:
        self._handlers: dict[str, list[Callable[..., Any]]] = {
            name: [] for name in HOOK_SPECS
        }
        # 每个 handler 独立的熔断器
        self._breakers: dict[int, HookBreaker] = {}

        # 从配置注入的参数 — 零 Magic Numbers
        self._hook_timeout = hook_timeout
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._safe_mode = safe_mode

    def register(self, implementor: object) -> list[str]:
        """扫描 implementor 上与 HOOK_SPECS 同名的方法并注册.

        Returns:
            成功注册的钩子名列表（用于日志/调试）。
        """
        registered: list[str] = []
        for hook_name in HOOK_SPECS:
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
        for hook_name in HOOK_SPECS:
            method = getattr(implementor, hook_name, None)
            if method in self._handlers.get(hook_name, []):
                self._handlers[hook_name].remove(method)
                self._breakers.pop(id(method), None)

    async def call(self, hook_name: str, **kwargs: Any) -> Any:
        """按策略执行钩子（带熔断保护，全异步并发）.

        Args:
            hook_name: 钩子名称（必须在 HOOK_SPECS 中声明）。
            **kwargs: 传给钩子方法的参数。

        Returns:
            根据策略不同：
            - PARALLEL: None
            - WATERFALL: 最终链式结果
            - BAIL: 第一个非 None 结果
            - COLLECT: 所有返回值的列表
        """
        if self._safe_mode:
            return None

        spec = HOOK_SPECS.get(hook_name)
        if spec is None:
            logger.warning("unknown hook: %s", hook_name)
            return None

        handlers = self._handlers.get(hook_name, [])
        if not handlers:
            return [] if spec.strategy == HookStrategy.COLLECT else None

        strategy = spec.strategy

        if strategy == HookStrategy.PARALLEL:
            return await self._call_parallel(hook_name, handlers, kwargs)
        elif strategy == HookStrategy.WATERFALL:
            return await self._call_waterfall(hook_name, handlers, kwargs)
        elif strategy == HookStrategy.BAIL:
            return await self._call_bail(hook_name, handlers, kwargs)
        elif strategy == HookStrategy.BAIL_VETO:
            return await self._call_bail_veto(hook_name, handlers, kwargs)
        elif strategy == HookStrategy.COLLECT:
            return await self._call_collect(hook_name, handlers, kwargs)
        return None

    async def _safe_call(self, handler: Callable, kwargs: dict) -> Any:
        """带熔断 + 超时保护的安全调用. 支持 sync/async handler。"""
        breaker = self._breakers.get(id(handler))
        if breaker and breaker.is_open:
            logger.debug("breaker OPEN for %s, skipping", handler)
            return None

        try:
            if inspect.iscoroutinefunction(handler):
                result = await asyncio.wait_for(handler(**kwargs), timeout=self._hook_timeout)
            else:
                result = await asyncio.wait_for(asyncio.to_thread(handler, **kwargs), timeout=self._hook_timeout)
                
            if breaker:
                breaker.record_success()
            return result
        except TimeoutError:
            logger.warning("hook handler %s timed out (limit=%.2fs)", handler, self._hook_timeout)
            if breaker:
                breaker.record_failure()
            return None
        except Exception:
            logger.exception("hook handler %s failed", handler)
            if breaker:
                breaker.record_failure()
            return None

    async def _call_parallel(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> None:
        tasks = [self._safe_call(handler, kwargs) for handler in handlers]
        await asyncio.gather(*tasks)

    async def _call_waterfall(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> dict[str, Any]:
        """瀑布流执行 — 纯函数式 kwargs 更新.

        约定：
        - handler 始终接收完整的 **current_kwargs。
        - handler 返回 None → 不修改任何参数。
        - handler 返回 dict → 合并到 current_kwargs（覆盖同名键）。
        - 最终返回累积更新后的完整 kwargs 字典。

        调用方按需从返回的字典中取出被修改的值。
        HookManager 本身不关心具体键名，实现彻底解耦。
        """
        current_kwargs = dict(kwargs)  # 浅拷贝，避免污染原始参数
        for handler in handlers:
            ret = await self._safe_call(handler, current_kwargs)
            if isinstance(ret, dict):
                current_kwargs.update(ret)
        return current_kwargs

    async def _call_bail(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> Any:
        for handler in handlers:
            ret = await self._safe_call(handler, kwargs)
            if ret is not None:
                return ret  # 第一个非 None 胜出
        return None

    async def _call_collect(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> list[Any]:
        tasks = [self._safe_call(handler, kwargs) for handler in handlers]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def _call_bail_veto(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> bool:
        """一票否决执行 — 全部 handler 并发执行，任一返回 False 即否决.

        设计要点：
        - 所有 handler 都会被执行（不像 bail 那样早退）。
        - handler 返回 None 或 True 视为同意；仅返回 False 视为否决。
        - 返回 True 表示全部通过，False 表示被否决。
        """
        tasks = [self._safe_call(handler, kwargs) for handler in handlers]
        results = await asyncio.gather(*tasks)
        # 任一 handler 显式返回 False → 否决
        for result in results:
            if result is False:
                logger.info("hook %s vetoed by handler", name)
                return False
        return True
