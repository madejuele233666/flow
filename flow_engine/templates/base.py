"""任务模板系统 — 预定义工作流快速创建.

设计要点：
- TaskTemplate ABC 定义模板合约
- TemplateRegistry 管理全部模板（内置 + 用户自定义 TOML）
- 支持从 ~/.flow_engine/templates/ 目录加载 TOML 自定义模板

用法：
    flow add --template weekly_review   # 按模板创建任务
    flow templates ls                   # 查看可用模板
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flow_engine.state.machine import TaskState
from flow_engine.storage.task_model import Task

logger = logging.getLogger(__name__)

# toml 读取
try:
    import tomllib
except ModuleNotFoundError:
    import toml as tomllib  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# 模板抽象
# ---------------------------------------------------------------------------

@dataclass
class TemplateOutput:
    """模板产出 — 可以是一个任务或一组任务."""
    tasks: list[Task]


class TaskTemplate(ABC):
    """任务模板合约."""

    @property
    @abstractmethod
    def name(self) -> str:
        """模板标识名（用于 CLI --template xxx）。"""

    @property
    @abstractmethod
    def description(self) -> str:
        """模板描述。"""

    @abstractmethod
    def create(self, base_id: int, **overrides: Any) -> TemplateOutput:
        """根据模板创建任务.

        Args:
            base_id: 起始 ID（由调用方提供）。
            **overrides: 用户覆盖的参数（如 ddl、priority 等）。

        Returns:
            TemplateOutput 包含一或多个 Task。
        """


# ---------------------------------------------------------------------------
# TOML 文件模板 — 用户自定义
# ---------------------------------------------------------------------------

class TomlTemplate(TaskTemplate):
    """从 TOML 文件加载的用户自定义模板.

    TOML 格式示例（~/.flow_engine/templates/weekly_review.toml）:
        name = "weekly_review"
        description = "每周复盘"

        [[tasks]]
        title = "回顾本周完成的任务"
        priority = 1

        [[tasks]]
        title = "整理下周计划"
        priority = 2
        ddl_offset_days = 7
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return self._data.get("name", "unnamed")

    @property
    def description(self) -> str:
        return self._data.get("description", "")

    def create(self, base_id: int, **overrides: Any) -> TemplateOutput:
        task_defs = self._data.get("tasks", [])
        tasks: list[Task] = []
        for i, td in enumerate(task_defs):
            ddl = None
            if offset := td.get("ddl_offset_days"):
                ddl = datetime.now() + timedelta(days=offset)

            tasks.append(Task(
                id=base_id + i,
                title=overrides.get("title_prefix", "") + td.get("title", f"步骤 {i+1}"),
                priority=td.get("priority", overrides.get("priority", 2)),
                ddl=overrides.get("ddl") or ddl,
                tags=td.get("tags", []),
                parent_id=base_id if i > 0 else None,
            ))
        return TemplateOutput(tasks=tasks)

    @classmethod
    def from_file(cls, path: Path) -> TomlTemplate:
        """从 TOML 文件加载模板."""
        with open(path, "rb") as f:
            data = tomllib.load(f)  # type: ignore[arg-type]
        return cls(data)


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

class TemplateRegistry:
    """模板注册表 — 管理全部可用模板."""

    def __init__(self) -> None:
        self._templates: dict[str, TaskTemplate] = {}

    def register(self, template: TaskTemplate) -> None:
        """注册一个模板."""
        self._templates[template.name] = template
        logger.debug("template registered: %s", template.name)

    def register_builtins(self) -> None:
        """注册内置模板（延迟导入避免循环）."""
        from flow_engine.templates.builtin import get_builtin_templates
        for t in get_builtin_templates():
            self.register(t)

    def load_user_templates(self, templates_dir: Path) -> int:
        """从目录加载全部 TOML 模板.

        Returns:
            成功加载的模板数。
        """
        if not templates_dir.exists():
            return 0
        count = 0
        for path in sorted(templates_dir.glob("*.toml")):
            try:
                template = TomlTemplate.from_file(path)
                self.register(template)
                count += 1
            except Exception:
                logger.exception("failed to load template: %s", path)
        return count

    def get(self, name: str) -> TaskTemplate | None:
        """按名称获取模板."""
        return self._templates.get(name)

    def list_all(self) -> list[tuple[str, str]]:
        """返回 (name, description) 列表."""
        return [(t.name, t.description) for t in self._templates.values()]
