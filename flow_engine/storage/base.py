"""存储层抽象接口 — 定义 CRUD 合约.

设计要点：
- 抽象基类定义合约，具体实现（Markdown / SQLite / JSON）可自由替换。
- CLI 和调度层只依赖此接口，不关心底层存储格式。
- 未来切换存储引擎只需提供新的 TaskRepository 实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from flow_engine.state.machine import TaskState
from flow_engine.storage.task_model import Task


class TaskRepository(ABC):
    """任务仓库抽象接口 — 所有存储实现的合约."""

    @abstractmethod
    def load_all(self) -> list[Task]:
        """加载全部任务."""

    @abstractmethod
    def save_all(self, tasks: list[Task]) -> None:
        """保存全部任务（原子覆盖写入）."""

    @abstractmethod
    def next_id(self) -> int:
        """返回下一个可用的任务 ID."""

    # ── 便捷查询（默认实现，子类可优化） ──

    def get_by_id(self, task_id: int) -> Task | None:
        """按 ID 查找任务."""
        return next((t for t in self.load_all() if t.id == task_id), None)

    def get_by_state(self, state: TaskState) -> list[Task]:
        """按状态筛选任务."""
        return [t for t in self.load_all() if t.state == state]

    def get_active(self) -> Task | None:
        """获取当前唯一处于 In Progress 的任务."""
        active = self.get_by_state(TaskState.IN_PROGRESS)
        return active[0] if active else None


class VersionControl(ABC):
    """版本控制抽象接口 — Git 或其他 VCS 的合约."""

    @abstractmethod
    def commit(self, message: str) -> None:
        """提交当前变更."""

    @abstractmethod
    def log(self, count: int = 10) -> list[str]:
        """返回最近 N 条提交信息."""
