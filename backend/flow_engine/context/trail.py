"""Passive context trail primitives."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TrailEvent:
    task_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    event_type: str = ""
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TrailEvent:
        return cls(
            task_id=int(raw["task_id"]),
            timestamp=datetime.fromisoformat(raw["timestamp"]),
            source=str(raw["source"]),
            event_type=str(raw["event_type"]),
            summary=str(raw["summary"]),
            metadata=dict(raw.get("metadata", {})),
        )


class TrailCollector(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Collector identifier."""

    @abstractmethod
    async def collect(self, task_id: int, snapshot) -> list[TrailEvent]:
        """Build task-scoped events from a capture cycle."""


class TrailStore:
    """Append-only JSONL trail store."""

    def __init__(self, trails_dir: Path) -> None:
        self._dir = trails_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def append(self, event: TrailEvent) -> None:
        path = self._dir / f"{event.task_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def query(
        self,
        task_id: int,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[TrailEvent]:
        path = self._dir / f"{task_id}.jsonl"
        if not path.exists():
            return []

        events: list[TrailEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = TrailEvent.from_dict(json.loads(line))
            if since and event.timestamp < since:
                continue
            if until and event.timestamp > until:
                continue
            events.append(event)
        return sorted(events, key=lambda item: item.timestamp)
