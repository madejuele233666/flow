"""状态转移引擎 — 执行状态变化的复合逻辑.

此模块是状态机的"执行层"，负责：
1. 调用 before_task_transition 拦截钩子（bail_veto，插件可一票否决）
2. 调用 on_before_transition 中间件（waterfall，可修改目标状态）
3. 校验转移合法性（委托 machine.py）
4. 执行 In Progress 的唯一排他（自动压栈）
5. 通过事件总线广播状态变更
6. 调用 on_after_transition 通知

设计要点：
- 不直接依赖存储层 — 通过注入的回调/事件总线与其他模块通信。
- HookManager 可选注入 — 不注入时退化为原版无钩子行为。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
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


class TransitionVetoedError(ValueError):
    """插件通过 before_task_transition 钩子否决了状态转移.

    与 IllegalTransitionError 不同：
    - IllegalTransitionError 是状态机规则层面不允许的转移。
    - TransitionVetoedError 是规则允许，但插件基于业务逻辑否决的转移。
    """

    def __init__(self, task_id: int, old_state: TaskState, target: TaskState) -> None:
        self.task_id = task_id
        self.old_state = old_state
        self.target = target
        super().__init__(
            f"Task #{task_id}: {old_state.value} → {target.value} vetoed by plugin"
        )


class TransitionEngine:
    """状态转移引擎 — 所有状态变更的唯一入口.

    并发安全：通过实例级 asyncio.Lock 保证同一时刻只有一个
    协程能执行状态变更，消除自动压栈过程中的竞态条件。
    未来切换为多进程 Daemon 时，只需替换为跨进程文件锁即可。

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
        self._lock = asyncio.Lock()

    # ── 公共 API（带锁保护） ──

    async def transition(self, task: Task, target: TaskState) -> Task:
        """将 task 的状态转移到 target（线程安全）.

        外部调用方使用此方法，自动获取互斥锁。

        Raises:
            IllegalTransitionError: 如果转移不合法。
        """
        async with self._lock:
            resolved_target = await self._prepare_transition_unlocked(task, target)
            return await self._commit_transition_unlocked(task, resolved_target)

    async def prepare_transition(self, task: Task, target: TaskState) -> TaskState:
        """预检状态转移，返回已解析的目标状态且不产生副作用."""
        async with self._lock:
            shadow = replace(task)
            return await self._prepare_transition_unlocked(shadow, target)

    async def commit_transition(self, task: Task, target: TaskState) -> Task:
        """提交已预检的状态转移，只执行状态写入、事件广播和 after hook."""
        async with self._lock:
            return await self._commit_transition_unlocked(task, target)

    async def ensure_single_active(
        self,
        all_tasks: list[Task],
        new_active_id: int,
    ) -> list[Task]:
        """确保同一时刻只有一个任务处于 In Progress（原子操作）.

        在同一把锁内完成"暂停旧任务 + 启动新任务"，消除竞态窗口。

        Args:
            all_tasks: 全部任务列表。
            new_active_id: 即将进入 In Progress 的任务 ID。

        Returns:
            被自动暂停的任务列表（可能为空）。
        """
        async with self._lock:
            paused: list[Task] = []
            for task in all_tasks:
                if task.state == TaskState.IN_PROGRESS and task.id != new_active_id:
                    await self._transition_unlocked(task, TaskState.PAUSED)
                    paused.append(task)
            return paused

    # ── 内部实现（无锁，仅供已持锁的上层方法调用） ──

    async def _transition_unlocked(self, task: Task, target: TaskState) -> Task:
        resolved_target = await self._prepare_transition_unlocked(task, target)
        return await self._commit_transition_unlocked(task, resolved_target)

    async def _prepare_transition_unlocked(self, task: Task, target: TaskState) -> TaskState:
        """状态转移的核心逻辑（不含锁，由调用方负责并发控制）.

        执行流程：
        1. before_task_transition 拦截钩子（bail_veto，可一票否决）
        2. on_before_transition 中间件（waterfall，可修改目标状态）
        3. 合法性校验
        """
        from flow_engine.hooks_payload import (
            BeforeTransitionPayload,
            TransitionErrorPayload,
            VetoCheckPayload,
        )

        if self._hooks:
            veto_payload = VetoCheckPayload(
                task=task, old_state=task.state, target_state=target,
            )
            approved = await self._hooks.call("before_task_transition", veto_payload)
            if approved is False:
                raise TransitionVetoedError(task.id, task.state, target)

        if self._hooks:
            wf_payload = BeforeTransitionPayload(task=task, target_state=target)
            await self._hooks.call("on_before_transition", wf_payload)
            target = wf_payload.target_state

        if not can_transition(task.state, target):
            error = IllegalTransitionError(task.state, target)
            if self._hooks:
                err_payload = TransitionErrorPayload(
                    task=task, target_state=target, error=error,
                )
                await self._hooks.call("on_transition_error", err_payload)
            raise error

        return target

    async def _commit_transition_unlocked(self, task: Task, target: TaskState) -> Task:
        """提交已解析的状态转移（不再次运行 before hook / waterfall hook）.

        4. 状态变更
        5. 事件广播（强类型载荷）
        6. on_after_transition 通知
        """
        from flow_engine.events_payload import TaskStateChangedPayload
        from flow_engine.hooks_payload import AfterTransitionPayload

        # ── 3. 状态变更 ──
        old_state = task.state
        task.state = target
        task.touch()

        logger.info("Task #%s: %s → %s", task.id, old_state.value, target.value)

        # ── 4. 事件广播（强类型载荷） ──
        await self._bus.emit(
            EventType.TASK_STATE_CHANGED,
            TaskStateChangedPayload(
                task_id=task.id, old_state=old_state, new_state=target,
            ),
        )

        # ── 5. after 钩子 (parallel: 全部通知) ──
        if self._hooks:
            after_payload = AfterTransitionPayload(
                task=task, old_state=old_state, new_state=target,
            )
            await self._hooks.call("on_after_transition", after_payload)

        return task
