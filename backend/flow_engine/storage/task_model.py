"""任务数据模型 — 纯数据结构，零业务逻辑.

设计要点：
- dataclass 保持简单、可序列化。
- 不依赖任何外部模块，可被所有层引用。
- touch() 是唯一的行为方法，仅更新时间戳。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from flow_engine.state.machine import TaskState


@dataclass
class Task:
    """单个任务的全部元数据."""

    id: int
    title: str
    state: TaskState = TaskState.READY
    priority: int = 2                           # P0(紧急) ~ P3(低优)
    ddl: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None          # 最近一次进入 In Progress 的时间
    block_reason: str = ""
    parent_id: int | None = None                # 子任务指向父任务
    tags: list[str] = field(default_factory=list)

    def touch(self) -> None:
        """更新 updated_at 时间戳."""
        self.updated_at = datetime.now()

    @property
    def is_terminal(self) -> bool:
        """是否处于终态（Done / Canceled）."""
        return self.state in (TaskState.DONE, TaskState.CANCELED)

    @property
    def is_active(self) -> bool:
        """是否处于 In Progress."""
        return self.state == TaskState.IN_PROGRESS
