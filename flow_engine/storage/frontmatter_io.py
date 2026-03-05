"""YAML Frontmatter Markdown I/O - Obsidian-compatible task storage.

Design (Phase 4 - Resilient Storage):
- Tasks stored as standard Markdown with YAML frontmatter headers.
- Compatible with Obsidian, Logseq, and other Markdown-based tools.
- Each task file: YAML header (metadata) + Markdown body (notes/LLM logs).
- Uses PyYAML for robust parsing, replacing fragile regex.
- Falls back gracefully to the legacy single-line format for reading.

File format (single consolidated tasks.md):

    ---
    flow_version: 1
    tasks:
      - id: 1
        title: "Write thesis chapter 1"
        state: in_progress
        priority: 1
        ddl: "2026-03-10"
        tags: ["thesis", "writing"]
        created_at: "2026-03-01T10:00:00"
        updated_at: "2026-03-04T15:30:00"
        block_reason: ""
      - id: 2
        title: "Buy coffee"
        state: done
        priority: 3
        tags: []
    ---

    # Flow Engine Tasks

    Additional notes, LLM conversation logs, and free-form content below.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from flow_engine.state.machine import TaskState
from flow_engine.storage.base import TaskRepository
from flow_engine.storage.task_model import Task

logger = logging.getLogger(__name__)

_DATE_FMT = "%Y-%m-%d"
_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"
_FRONTMATTER_DELIM = "---"


# ---------------------------------------------------------------------------
# Serialization helpers (Task <-> dict)
# ---------------------------------------------------------------------------

def _task_to_dict(task: Task) -> dict[str, Any]:
    """Serialize a Task to a YAML-safe dictionary."""
    d: dict[str, Any] = {
        "id": task.id,
        "title": task.title,
        "state": task.state.value,
        "priority": task.priority,
        "tags": task.tags,
        "created_at": task.created_at.strftime(_DATETIME_FMT),
        "updated_at": task.updated_at.strftime(_DATETIME_FMT),
    }
    if task.ddl is not None:
        d["ddl"] = task.ddl.strftime(_DATE_FMT)
    if task.started_at is not None:
        d["started_at"] = task.started_at.strftime(_DATETIME_FMT)
    if task.block_reason:
        d["block_reason"] = task.block_reason
    if task.parent_id is not None:
        d["parent_id"] = task.parent_id
    return d


def _dict_to_task(d: dict[str, Any]) -> Task:
    """Deserialize a dictionary to a Task."""
    ddl_raw = d.get("ddl")
    started_raw = d.get("started_at")
    created_raw = d.get("created_at")
    updated_raw = d.get("updated_at")

    return Task(
        id=int(d["id"]),
        title=str(d["title"]),
        state=TaskState(d.get("state", "ready")),
        priority=int(d.get("priority", 2)),
        ddl=_parse_datetime(ddl_raw, _DATE_FMT) if ddl_raw else None,
        created_at=_parse_datetime(created_raw, _DATETIME_FMT) if created_raw else datetime.now(),
        updated_at=_parse_datetime(updated_raw, _DATETIME_FMT) if updated_raw else datetime.now(),
        started_at=_parse_datetime(started_raw, _DATETIME_FMT) if started_raw else None,
        block_reason=str(d.get("block_reason", "")),
        parent_id=d.get("parent_id"),
        tags=list(d.get("tags", [])),
    )


def _parse_datetime(raw: Any, fmt: str) -> datetime:
    """Parse a datetime from string or datetime object."""
    if isinstance(raw, datetime):
        return raw
    return datetime.strptime(str(raw), fmt)


# ---------------------------------------------------------------------------
# Frontmatter read/write
# ---------------------------------------------------------------------------

def _read_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from Markdown body.

    Returns:
        (frontmatter_dict, body_text)
    """
    if not text.startswith(_FRONTMATTER_DELIM):
        return {}, text

    lines = text.split("\n")
    end_idx = -1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_DELIM:
            end_idx = i
            break

    if end_idx < 0:
        return {}, text

    yaml_block = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).strip()

    try:
        fm = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        logger.warning("failed to parse YAML frontmatter: %s", exc)
        return {}, text

    return fm, body


def _write_frontmatter(fm: dict[str, Any], body: str = "") -> str:
    """Compose YAML frontmatter + Markdown body into a single string."""
    yaml_str = yaml.dump(
        fm,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip()

    parts = [_FRONTMATTER_DELIM, yaml_str, _FRONTMATTER_DELIM]
    if body:
        parts.append("")
        parts.append(body)
    parts.append("")  # trailing newline
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Repository implementation
# ---------------------------------------------------------------------------

class FrontmatterTaskRepository(TaskRepository):
    """Obsidian-compatible YAML Frontmatter task repository.

    Stores all tasks in a single Markdown file with YAML frontmatter.
    The body section is preserved for free-form notes and LLM logs.

    Args:
        file_path: Path to the tasks.md file.
    """

    def __init__(self, file_path: Path) -> None:
        self._path = file_path

    async def load_all(self) -> list[Task]:
        """Load tasks from YAML frontmatter."""
        import asyncio

        def _sync_load() -> list[Task]:
            if not self._path.exists():
                return []

            text = self._path.read_text(encoding="utf-8")
            fm, _ = _read_frontmatter(text)

            raw_tasks = fm.get("tasks", [])
            if not isinstance(raw_tasks, list):
                return []

            tasks: list[Task] = []
            for entry in raw_tasks:
                try:
                    tasks.append(_dict_to_task(entry))
                except Exception as exc:
                    logger.warning("skipping malformed task entry: %s", exc)
            return tasks

        return await asyncio.to_thread(_sync_load)

    async def save_all(self, tasks: list[Task]) -> None:
        """Save tasks to YAML frontmatter, preserving body notes."""
        import asyncio

        def _sync_save() -> None:
            # Preserve existing body if file exists
            body = ""
            if self._path.exists():
                text = self._path.read_text(encoding="utf-8")
                _, body = _read_frontmatter(text)

            fm: dict[str, Any] = {
                "flow_version": 1,
                "tasks": [_task_to_dict(t) for t in tasks],
            }

            self._path.parent.mkdir(parents=True, exist_ok=True)
            content = _write_frontmatter(fm, body or "# Flow Engine Tasks")
            self._path.write_text(content, encoding="utf-8")
            logger.debug("saved %d tasks to %s (frontmatter)", len(tasks), self._path)

        await asyncio.to_thread(_sync_save)

    async def next_id(self) -> int:
        """Return next available task ID."""
        tasks = await self.load_all()
        return max((t.id for t in tasks), default=0) + 1
