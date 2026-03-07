"""强类型钩子载荷 (Typed Hook Payloads).

替代原有的 **kwargs 弱类型传参。
每个 hook 对应一个 dataclass:
- Waterfall 钩子 → 可变 dataclass（插件原地修改属性）
- Parallel / Bail / Collect 钩子 → frozen dataclass（只读通知）
- Bail Veto 钩子 → frozen dataclass（返回 bool 投票）

设计要点:
- HookManager 本身保持泛型 (payload: Any)，不绑定业务类型。
- 类型安全由调用方 (TransitionEngine) 和插件开发者共同约守。

用法 (插件侧):
    class MyPlugin(FlowPlugin):
        def on_before_transition(self, payload: BeforeTransitionPayload) -> None:
            # Waterfall: 原地修改目标状态
            if payload.task.priority < 3:
                payload.target_state = TaskState.BLOCKED

        def on_after_transition(self, payload: AfterTransitionPayload) -> None:
            # Parallel: 只读通知
            print(f"{payload.task.title}: {payload.old_state} → {payload.new_state}")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow_engine.state.machine import TaskState
    from flow_engine.storage.task_model import Task


# ---------------------------------------------------------------------------
# Waterfall 载荷 — 可变，插件可原地修改属性
# ---------------------------------------------------------------------------

@dataclass
class BeforeTransitionPayload:
    """on_before_transition (waterfall) — 插件可修改 target_state."""

    task: Task
    target_state: TaskState


@dataclass
class BeforeSavePayload:
    """on_before_save (waterfall) — 插件可修改任务数据."""

    task: Task


# ---------------------------------------------------------------------------
# Bail Veto 载荷 — 不可变，插件返回 bool 投票
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VetoCheckPayload:
    """before_task_transition (bail_veto) — 返回 False 可一票否决."""

    task: Task
    old_state: TaskState
    target_state: TaskState


# ---------------------------------------------------------------------------
# Parallel 载荷 — 不可变，仅通知
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AfterTransitionPayload:
    """on_after_transition (parallel) — 只读通知."""

    task: Task
    old_state: TaskState
    new_state: TaskState


@dataclass(frozen=True)
class TransitionErrorPayload:
    """on_transition_error (parallel) — 错误通知."""

    task: Task
    target_state: TaskState
    error: Exception


@dataclass(frozen=True)
class TaskLifecyclePayload:
    """on_task_created / on_task_deleted (parallel) — 任务生命周期通知."""

    task: Task


@dataclass(frozen=True)
class AfterSavePayload:
    """on_after_save (parallel) — 保存后通知."""

    task: Task


@dataclass(frozen=True)
class FocusBreakPayload:
    """on_focus_break (parallel) — 休息提醒通知."""

    task_id: int
    elapsed_minutes: int


@dataclass(frozen=True)
class SuggestNextPayload:
    """on_suggest_next (bail) — 推荐下一个任务."""

    candidates: list


@dataclass(frozen=True)
class RankFactorPayload:
    """on_rank_factor (collect) — 排序因子打分."""

    task: Task


@dataclass(frozen=True)
class ContextPayload:
    """on_context_captured / on_context_restored (parallel) — 上下文快照."""

    task_id: int
