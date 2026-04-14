"""八维状态机 — 状态枚举与转移合法性定义.

这是整个系统最核心的约束层。
所有状态变化必须经过此模块校验，禁止任何模块绕过状态机直接修改状态。

设计要点：
- TRANSITIONS 字典是"白名单"模式 — 只有显式声明的转移才合法。
- 自动压栈等复合行为不在此层处理，由上层 TransitionEngine 组合完成。
"""

from __future__ import annotations

from enum import Enum


class TaskState(str, Enum):
    """八维任务状态."""

    DRAFT = "Draft"
    READY = "Ready"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    PAUSED = "Paused"
    BLOCKED = "Blocked"
    DONE = "Done"
    CANCELED = "Canceled"


# ---------------------------------------------------------------------------
# 状态转移白名单
#
# key   = 当前状态
# value = 该状态允许转移到的目标状态集合
# ---------------------------------------------------------------------------

TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.DRAFT: frozenset({
        TaskState.READY,
        TaskState.CANCELED,
    }),
    TaskState.READY: frozenset({
        TaskState.SCHEDULED,
        TaskState.IN_PROGRESS,
        TaskState.CANCELED,
    }),
    TaskState.SCHEDULED: frozenset({
        TaskState.IN_PROGRESS,
        TaskState.READY,
        TaskState.CANCELED,
    }),
    TaskState.IN_PROGRESS: frozenset({
        TaskState.PAUSED,
        TaskState.BLOCKED,
        TaskState.DONE,
    }),
    TaskState.PAUSED: frozenset({
        TaskState.IN_PROGRESS,
        TaskState.CANCELED,
    }),
    TaskState.BLOCKED: frozenset({
        TaskState.READY,
        TaskState.CANCELED,
    }),
    TaskState.DONE: frozenset(),      # 终态，不可转移
    TaskState.CANCELED: frozenset(),  # 终态，不可转移
}


def can_transition(current: TaskState, target: TaskState) -> bool:
    """判断从 current 到 target 的转移是否合法."""
    return target in TRANSITIONS.get(current, frozenset())


class IllegalTransitionError(ValueError):
    """非法状态转移异常."""

    def __init__(self, current: TaskState, target: TaskState) -> None:
        self.current = current
        self.target = target
        allowed = ", ".join(s.value for s in TRANSITIONS.get(current, frozenset()))
        super().__init__(
            f"非法转移: {current.value} → {target.value}。"
            f"当前状态 [{current.value}] 允许转移到: [{allowed or '无 (终态)'}]"
        )
