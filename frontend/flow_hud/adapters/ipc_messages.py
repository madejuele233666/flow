from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flow_hud.core.events_payload import IpcMessageReceivedPayload


@dataclass(frozen=True)
class TimerTickPayload:
    """来自引擎的定时器心跳."""
    tick: int


@dataclass(frozen=True)
class TaskCreatedIpcPayload:
    """任务创建事件."""
    task_id: int


@dataclass(frozen=True)
class TaskStateChangedIpcPayload:
    """任务状态变更."""
    task_id: int
    old_state: str
    new_state: str


def adapt_ipc_message(method: str, data: dict[str, Any]) -> object:
    """将原始 IPC 消息转换为强类型载荷.
    
    它是唯一允许硬编码 JSON Field string 提取的地方。
    """
    try:
        if method == "timer.tick":
            tick = data.get("tick")
            if tick is None:
                tick = data.get("elapsed", 0)
            return TimerTickPayload(tick=int(tick))
        
        if method == "task.created":
            return TaskCreatedIpcPayload(task_id=data.get("task_id", 0))
            
        if method == "task.state_changed":
            return TaskStateChangedIpcPayload(
                task_id=data.get("task_id", 0),
                old_state=str(data.get("old_state", "")),
                new_state=str(data.get("new_state", ""))
            )
    except (KeyError, TypeError, ValueError):
        pass

    return IpcMessageReceivedPayload(method=method, data=data)
