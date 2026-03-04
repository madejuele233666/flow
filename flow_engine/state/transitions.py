"""状态转移引擎 — 执行状态变化的复合逻辑.

此模块是状态机的"执行层"，负责：
1. 校验转移合法性（委托 machine.py）
2. 调用中间件钩子（before / after / error）
3. 执行 In Progress 的唯一排他（自动压栈）
4. 通过事件总线广播状态变更

设计要点：
- 不直接依赖存储层 — 通过注入的回调/事件总线与其他模块通信。
- HookManager 可选注入 — 不注入时退化为原版无钩子行为。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flow_engine.events import EventBus, EventType
from flow_engine.state.machine import (
    IllegalTransitionError,
    TaskState,
    can_transition,
)

if TYPE_CHECKING:
    from flow_engine.hooks import HookManager
    from flow_engine.storage.task_model import Task

logger = logging.getLogger(__name__)


class TransitionEngine:
    """状态转移引擎 — 所有状态变更的唯一入口.

    Attributes:
        event_bus: 事件总线，用于广播状态变更。
        hook_mgr: 钩子管理器（可选），用于调用 before/after 中间件。
    """

    def __init__(
        self,
        event_bus: EventBus,
        hook_mgr: HookManager | None = None,
    ) -> None:
        self._bus = event_bus
        self._hooks = hook_mgr

    async def transition(self, task: Task, target: TaskState) -> Task:
        """将 task 的状态转移到 target.

        执行流程：
        1. on_before_transition 钩子（waterfall，可拦截/修改目标状态）
        2. 合法性校验
        3. 状态变更
        4. 事件广播
        5. on_after_transition 钩子

        Args:
            task: 要转移状态的任务对象（会被就地修改）。
            target: 目标状态。

        Returns:
            状态已更新的 task（同一对象引用）。

        Raises:
            IllegalTransitionError: 如果转移不合法。
        """
        # ── 1. before 钩子 (waterfall: 可修改 target) ──
        if self._hooks:
            hook_result = await self._hooks.call(
                "on_before_transition",
                task=task, target_state=target,
            )
            # waterfall 返回的可能是修改后的 target
            if isinstance(hook_result, TaskState):
                target = hook_result

        # ── 2. 合法性校验 ──
        if not can_transition(task.state, target):
            error = IllegalTransitionError(task.state, target)
            if self._hooks:
                await self._hooks.call(
                    "on_transition_error",
                    task=task, target_state=target, error=error,
                )
            raise error

        # ── 3. 状态变更 ──
        old_state = task.state
        task.state = target
        task.touch()

        logger.info("Task #%s: %s → %s", task.id, old_state.value, target.value)

        # ── 4. 事件广播 ──
        self._bus.emit(EventType.TASK_STATE_CHANGED, {
            "task_id": task.id,
            "old_state": old_state,
            "new_state": target,
        })

        # ── 5. after 钩子 (parallel: 全部通知) ──
        if self._hooks:
            await self._hooks.call(
                "on_after_transition",
                task=task, old_state=old_state, new_state=target,
            )

        return task

    async def ensure_single_active(
        self,
        all_tasks: list[Task],
        new_active_id: int,
    ) -> list[Task]:
        """确保同一时刻只有一个任务处于 In Progress（自动压栈）.

        Args:
            all_tasks: 全部任务列表。
            new_active_id: 即将进入 In Progress 的任务 ID。

        Returns:
            被自动暂停的任务列表（可能为空）。
        """
        paused: list[Task] = []
        for task in all_tasks:
            if task.state == TaskState.IN_PROGRESS and task.id != new_active_id:
                await self.transition(task, TaskState.PAUSED)
                paused.append(task)
        return paused
