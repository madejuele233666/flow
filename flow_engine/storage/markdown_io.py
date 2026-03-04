"""Markdown 任务读写器 — TaskRepository 的默认实现.

格式约定（tasks.md 内部结构）:
    每个任务占一行，使用 Markdown 复选框格式：

    - [ ] #1 [P1] 写毕业论文第一章 | Ready | ddl:2026-03-10 | tags:论文,写作
    - [x] #2 [P2] 买咖啡 | Done | ddl: | tags:

设计要点：
- 读写均基于正则解析，不依赖重型 Markdown AST 库。
- 保持 tasks.md 人类可读、可手动编辑。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from flow_engine.state.machine import TaskState
from flow_engine.storage.base import TaskRepository
from flow_engine.storage.task_model import Task

logger = logging.getLogger(__name__)

# 日期格式
_DATE_FMT = "%Y-%m-%d"

# 解析正则：匹配 "- [ ] #1 [P1] Title | State | ddl:... | tags:..."
_TASK_RE = re.compile(
    r"^- \[(?P<check>.)\] "
    r"#(?P<id>\d+) "
    r"\[P(?P<priority>\d)\] "
    r"(?P<title>.+?) "
    r"\| (?P<state>[^|]+) "
    r"\| ddl:(?P<ddl>[^|]*) "
    r"\| tags:(?P<tags>[^|]*)$"
)


class MarkdownTaskRepository(TaskRepository):
    """基于 tasks.md 文件的任务仓库实现."""

    def __init__(self, file_path: Path) -> None:
        self._path = file_path

    def load_all(self) -> list[Task]:
        """从 tasks.md 解析全部任务."""
        if not self._path.exists():
            return []

        tasks: list[Task] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            m = _TASK_RE.match(line)
            if not m:
                continue

            ddl_str = m.group("ddl").strip()
            tags_str = m.group("tags").strip()

            tasks.append(Task(
                id=int(m.group("id")),
                title=m.group("title").strip(),
                state=TaskState(m.group("state").strip()),
                priority=int(m.group("priority")),
                ddl=datetime.strptime(ddl_str, _DATE_FMT) if ddl_str else None,
                tags=[t.strip() for t in tags_str.split(",") if t.strip()],
            ))
        return tasks

    def save_all(self, tasks: list[Task]) -> None:
        """将全部任务序列化写入 tasks.md."""
        lines = ["# Flow Engine Tasks", ""]
        for t in tasks:
            check = "x" if t.state in (TaskState.DONE, TaskState.CANCELED) else " "
            ddl_str = t.ddl.strftime(_DATE_FMT) if t.ddl else ""
            tags_str = ",".join(t.tags)
            lines.append(
                f"- [{check}] #{t.id} [P{t.priority}] {t.title} "
                f"| {t.state.value} | ddl:{ddl_str} | tags:{tags_str}"
            )
        lines.append("")  # 尾换行

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug("saved %d tasks to %s", len(tasks), self._path)

    def next_id(self) -> int:
        """返回当前最大 ID + 1."""
        tasks = self.load_all()
        return max((t.id for t in tasks), default=0) + 1
