"""任务过滤/查询 DSL — 链式 API 精准筛选.

用法（代码层）：
    results = (TaskFilter(tasks)
        .by_state(TaskState.READY, TaskState.PAUSED)
        .by_priority(0, 1)
        .by_tag("论文")
        .by_ddl_before(datetime(2026, 4, 1))
        .exclude_terminal()
        .results())

用法（CLI）：
    flow ls --state ready --p 0-1 --tag "论文" --before "2026-04-01"
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from flow_engine.state.machine import TaskState
from flow_engine.storage.task_model import Task


class TaskFilter:
    """链式任务过滤器（Builder 模式）.

    每个 by_xxx 方法返回 self，支持链式调用。
    内部维护一系列 predicate，最终 results() 时一次性过滤。
    """

    def __init__(self, tasks: list[Task]) -> None:
        self._tasks = tasks
        self._predicates: list[Callable[[Task], bool]] = []

    # ── 链式过滤方法 ──

    def by_state(self, *states: TaskState) -> TaskFilter:
        """按状态筛选（可指定多个）."""
        state_set = set(states)
        self._predicates.append(lambda t: t.state in state_set)
        return self

    def by_priority(self, min_p: int = 0, max_p: int = 3) -> TaskFilter:
        """按优先级范围筛选 [min_p, max_p]."""
        self._predicates.append(lambda t: min_p <= t.priority <= max_p)
        return self

    def by_tag(self, *tags: str) -> TaskFilter:
        """按标签筛选（任一匹配即可）."""
        tag_set = set(tags)
        self._predicates.append(lambda t: bool(tag_set & set(t.tags)))
        return self

    def by_ddl_before(self, deadline: datetime) -> TaskFilter:
        """筛选 DDL 在指定日期之前的任务."""
        self._predicates.append(
            lambda t: t.ddl is not None and t.ddl <= deadline
        )
        return self

    def by_ddl_after(self, deadline: datetime) -> TaskFilter:
        """筛选 DDL 在指定日期之后的任务."""
        self._predicates.append(
            lambda t: t.ddl is not None and t.ddl >= deadline
        )
        return self

    def has_ddl(self) -> TaskFilter:
        """仅保留有 DDL 的任务."""
        self._predicates.append(lambda t: t.ddl is not None)
        return self

    def no_ddl(self) -> TaskFilter:
        """仅保留无 DDL 的任务."""
        self._predicates.append(lambda t: t.ddl is None)
        return self

    def exclude_terminal(self) -> TaskFilter:
        """排除终态（Done / Canceled）."""
        self._predicates.append(lambda t: not t.is_terminal)
        return self

    def by_parent(self, parent_id: int | None) -> TaskFilter:
        """按父任务 ID 筛选."""
        self._predicates.append(lambda t: t.parent_id == parent_id)
        return self

    def by_title_contains(self, keyword: str) -> TaskFilter:
        """标题包含关键词."""
        kw = keyword.lower()
        self._predicates.append(lambda t: kw in t.title.lower())
        return self

    def custom(self, predicate: Callable[[Task], bool]) -> TaskFilter:
        """自定义过滤条件（最高灵活度）."""
        self._predicates.append(predicate)
        return self

    # ── 终结方法 ──

    def results(self) -> list[Task]:
        """执行全部过滤条件，返回匹配的任务列表."""
        result = self._tasks
        for pred in self._predicates:
            result = [t for t in result if pred(t)]
        return result

    def count(self) -> int:
        """返回匹配数量."""
        return len(self.results())

    def first(self) -> Task | None:
        """返回第一个匹配的任务."""
        r = self.results()
        return r[0] if r else None
