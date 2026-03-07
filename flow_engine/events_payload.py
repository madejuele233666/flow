"""强类型事件载荷 (Typed Event Payloads).

替代原有的 data: dict[str, Any] 弱类型传参。
每个 EventType 对应一个 frozen dataclass，提供：
- IDE 自动补全
- mypy 静态检查
- 彻底消除 event.data.get("xxx") 拼写错误

用法:
    from flow_engine.events_payload import TaskStateChangedPayload
    await bus.emit(EventType.TASK_STATE_CHANGED,
        TaskStateChangedPayload(task_id=1, old_state=..., new_state=...))

    # 订阅端
    async def on_state_changed(event: Event) -> None:
        p: TaskStateChangedPayload = event.payload
        print(p.task_id, p.new_state)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow_engine.state.machine import TaskState


# ---------------------------------------------------------------------------
# 任务生命周期事件载荷
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskCreatedPayload:
    """任务创建事件载荷."""

    task_id: int


@dataclass(frozen=True)
class TaskStateChangedPayload:
    """状态变更事件载荷."""

    task_id: int
    old_state: TaskState
    new_state: TaskState


@dataclass(frozen=True)
class TaskDeletedPayload:
    """任务删除事件载荷."""

    task_id: int


@dataclass(frozen=True)
class TaskUpdatedPayload:
    """任务更新事件载荷."""

    task_id: int
