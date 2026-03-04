"""Markdown 任务读写器 — TaskRepository 的默认实现.

格式约定（tasks.md 内部结构）:
    每个任务占一行，使用 Markdown 复选框格式：

    - [ ] #1 [P1] 写毕业论文第一章 | Ready | ddl:2026-03-10 | tags:论文,写作
    - [x] #2 [P2] 买咖啡 | Done | ddl: | tags:

设计要点：
- 读写均基于正则解析，不依赖重型 Markdown AST 库。
- 保持 tasks.md 人类可读、可手动编辑。

Phase 4 升级：
- 文件锁保护：防止多终端并发读写导致数据损坏
- 锁超时从 FileLockConfig 注入，零 Magic Numbers
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

# 尝试导入 filelock（可选依赖）
try:
    from filelock import FileLock, Timeout as FileLockTimeout
    _HAS_FILELOCK = True
except ImportError:
    _HAS_FILELOCK = False
    logger.debug("filelock not installed, file locking disabled")


class _NoOpLock:
    """无操作锁 — filelock 不可用时的回退."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> _NoOpLock:
        return self

    def __exit__(self, *args: object) -> None:
        pass


class MarkdownTaskRepository(TaskRepository):
    """基于 tasks.md 文件的任务仓库实现.

    Phase 4: 支持可选的文件锁保护。

    Args:
        file_path: tasks.md 文件路径。
        lock_enabled: 是否启用文件锁（从 FileLockConfig.enabled 注入）。
        lock_timeout: 文件锁超时秒数（从 FileLockConfig.timeout_seconds 注入）。
    """

    def __init__(
        self,
        file_path: Path,
        lock_enabled: bool = True,
        lock_timeout: float = 10.0,
    ) -> None:
        self._path = file_path
        self._lock_enabled = lock_enabled and _HAS_FILELOCK
        self._lock_timeout = lock_timeout

        # 锁文件使用 .lock 后缀，与 tasks.md 同目录
        if self._lock_enabled:
            lock_path = str(file_path) + ".lock"
            self._lock = FileLock(lock_path, timeout=lock_timeout)
        else:
            self._lock = _NoOpLock()

        if lock_enabled and not _HAS_FILELOCK:
            logger.warning(
                "file locking requested but 'filelock' package not installed. "
                "Install with: pip install filelock"
            )

    async def load_all(self) -> list[Task]:
        """从 tasks.md 解析全部任务（带文件锁保护）."""
        def _sync_load() -> list[Task]:
            with self._lock:
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
        
        import asyncio
        return await asyncio.to_thread(_sync_load)

    async def save_all(self, tasks: list[Task]) -> None:
        """将全部任务序列化写入 tasks.md（带文件锁保护）."""
        def _sync_save() -> None:
            with self._lock:
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

        import asyncio
        await asyncio.to_thread(_sync_save)

    async def next_id(self) -> int:
        """返回当前最大 ID + 1."""
        tasks = await self.load_all()
        return max((t.id for t in tasks), default=0) + 1
