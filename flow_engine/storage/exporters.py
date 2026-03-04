"""多格式导出器 — 任务数据导出为 JSON / CSV 等格式.

设计要点：
- Exporter ABC 定义导出合约
- ExporterRegistry 注册表，通过名称查找
- 插件可通过 app.exporters.register(MyExporter()) 注册自定义格式
"""

from __future__ import annotations

import csv
import io
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime
from typing import Any

from flow_engine.storage.task_model import Task

logger = logging.getLogger(__name__)


class Exporter(ABC):
    """导出器合约."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """格式标识名（如 json / csv / ical）."""

    @property
    def description(self) -> str:
        """格式描述."""
        return ""

    @abstractmethod
    def export(self, tasks: list[Task]) -> str:
        """将任务列表导出为字符串."""


class ExporterRegistry:
    """导出器注册表."""

    def __init__(self) -> None:
        self._exporters: dict[str, Exporter] = {}

    def register(self, exporter: Exporter) -> None:
        self._exporters[exporter.format_name] = exporter
        logger.debug("exporter registered: %s", exporter.format_name)

    def get(self, format_name: str) -> Exporter | None:
        return self._exporters.get(format_name)

    def list_formats(self) -> list[str]:
        return list(self._exporters.keys())


# ---------------------------------------------------------------------------
# 内置导出器
# ---------------------------------------------------------------------------

def _serialize_task(task: Task) -> dict[str, Any]:
    """将 Task 转为可序列化的字典."""
    d: dict[str, Any] = {
        "id": task.id,
        "title": task.title,
        "state": task.state.value,
        "priority": task.priority,
        "ddl": task.ddl.isoformat() if task.ddl else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "block_reason": task.block_reason,
        "parent_id": task.parent_id,
        "tags": task.tags,
    }
    return d


class JsonExporter(Exporter):
    """JSON 导出器."""

    @property
    def format_name(self) -> str:
        return "json"

    @property
    def description(self) -> str:
        return "JSON 格式（可机器读取）"

    def export(self, tasks: list[Task]) -> str:
        data = [_serialize_task(t) for t in tasks]
        return json.dumps(data, ensure_ascii=False, indent=2)


class CsvExporter(Exporter):
    """CSV 导出器."""

    @property
    def format_name(self) -> str:
        return "csv"

    @property
    def description(self) -> str:
        return "CSV 格式（可导入 Excel）"

    def export(self, tasks: list[Task]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Title", "State", "Priority", "DDL",
            "Created", "Updated", "BlockReason", "ParentID", "Tags",
        ])
        for t in tasks:
            writer.writerow([
                t.id, t.title, t.state.value, t.priority,
                t.ddl.strftime("%Y-%m-%d") if t.ddl else "",
                t.created_at.strftime("%Y-%m-%d %H:%M"),
                t.updated_at.strftime("%Y-%m-%d %H:%M"),
                t.block_reason, t.parent_id or "",
                ",".join(t.tags),
            ])
        return output.getvalue()
