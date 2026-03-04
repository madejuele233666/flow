"""钩子系统 (Hook System) — pluggy 启发的类型化钩子框架.

设计来源：
- pytest/pluggy: 框架声明钩子签名，插件选择性实现
- Webpack/Tapable: 不同钩子有不同执行策略

框架通过 FlowHookSpec 声明全部可用钩子。
插件只需实现感兴趣的方法，HookManager 自动跳过未实现的。

执行策略：
- parallel  : 全部执行，互不影响（默认）
- waterfall : 链式传递，前一个结果传给下一个，可拦截
- bail      : 第一个非 None 结果胜出，后续跳过
- collect   : 收集所有返回值为列表
"""

from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 执行策略
# ---------------------------------------------------------------------------

class HookStrategy(str, Enum):
    """钩子执行策略（借鉴 Webpack Tapable）."""

    PARALLEL = "parallel"      # 全部执行，忽略返回值
    WATERFALL = "waterfall"    # 链式传递，可修改/拦截
    BAIL = "bail"              # 第一个非 None 结果胜出
    COLLECT = "collect"        # 收集所有返回值


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
}


# ---------------------------------------------------------------------------
# 钩子管理器
# ---------------------------------------------------------------------------

class HookManager:
    """钩子注册与调用中心.

    用法：
        mgr = HookManager()
        mgr.register(my_plugin)  # 自动扫描插件上的同名方法
        result = mgr.call("on_before_transition", task=task, target=state)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., Any]]] = {
            name: [] for name in HOOK_SPECS
        }

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

    def call(self, hook_name: str, **kwargs: Any) -> Any:
        """按策略执行钩子.

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
        spec = HOOK_SPECS.get(hook_name)
        if spec is None:
            logger.warning("unknown hook: %s", hook_name)
            return None

        handlers = self._handlers.get(hook_name, [])
        if not handlers:
            return [] if spec.strategy == HookStrategy.COLLECT else None

        strategy = spec.strategy

        if strategy == HookStrategy.PARALLEL:
            return self._call_parallel(hook_name, handlers, kwargs)
        elif strategy == HookStrategy.WATERFALL:
            return self._call_waterfall(hook_name, handlers, kwargs)
        elif strategy == HookStrategy.BAIL:
            return self._call_bail(hook_name, handlers, kwargs)
        elif strategy == HookStrategy.COLLECT:
            return self._call_collect(hook_name, handlers, kwargs)
        return None

    def _call_parallel(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> None:
        for handler in handlers:
            try:
                handler(**kwargs)
            except Exception:
                logger.exception("hook %s handler %s failed", name, handler)

    def _call_waterfall(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> Any:
        result = kwargs  # 初始传入参数作为第一轮输入
        for handler in handlers:
            try:
                ret = handler(**result) if isinstance(result, dict) else handler(result)
                if ret is not None:
                    result = ret  # 链式传递
            except Exception:
                logger.exception("hook %s handler %s failed", name, handler)
        return result

    def _call_bail(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> Any:
        for handler in handlers:
            try:
                ret = handler(**kwargs)
                if ret is not None:
                    return ret  # 第一个非 None 胜出
            except Exception:
                logger.exception("hook %s handler %s failed", name, handler)
        return None

    def _call_collect(
        self, name: str, handlers: list[Callable], kwargs: dict,
    ) -> list[Any]:
        results: list[Any] = []
        for handler in handlers:
            try:
                ret = handler(**kwargs)
                if ret is not None:
                    results.append(ret)
            except Exception:
                logger.exception("hook %s handler %s failed", name, handler)
        return results
