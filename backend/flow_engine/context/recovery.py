"""Recovery priority and reporting primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RecoveryPriority(str, Enum):
    MUST_RESTORE = "must_restore"
    BEST_EFFORT = "best_effort"
    DISPLAY_ONLY = "display_only"


RESTORE_PRIORITY: dict[str, RecoveryPriority] = {
    "active_window": RecoveryPriority.MUST_RESTORE,
    "active_file": RecoveryPriority.MUST_RESTORE,
    "active_workspace": RecoveryPriority.BEST_EFFORT,
    "open_windows": RecoveryPriority.BEST_EFFORT,
    "open_tabs": RecoveryPriority.BEST_EFFORT,
    "open_files": RecoveryPriority.BEST_EFFORT,
    "active_url": RecoveryPriority.BEST_EFFORT,
    "recent_tabs": RecoveryPriority.DISPLAY_ONLY,
    "session_duration_sec": RecoveryPriority.DISPLAY_ONLY,
    "capture_trigger": RecoveryPriority.DISPLAY_ONLY,
    "source_plugin": RecoveryPriority.DISPLAY_ONLY,
}


@dataclass
class RestoreResult:
    task_id: int
    restored: dict[str, Any] = field(default_factory=dict)
    degraded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    user_message: str | None = None

    @classmethod
    def empty(cls, task_id: int) -> RestoreResult:
        return cls(task_id=task_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
