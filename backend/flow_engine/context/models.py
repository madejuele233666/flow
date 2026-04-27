"""Context semantic model helpers."""

from __future__ import annotations

from enum import Enum


class ContextKind(str, Enum):
    """Semantic layer for snapshot fields."""

    ACTIVE = "active"
    RESTORABLE = "restorable"
    RECORD_ONLY = "record_only"


FIELD_CLASSIFICATION: dict[str, ContextKind] = {
    "active_window": ContextKind.ACTIVE,
    "active_url": ContextKind.ACTIVE,
    "active_file": ContextKind.ACTIVE,
    "active_workspace": ContextKind.ACTIVE,
    "open_windows": ContextKind.RESTORABLE,
    "open_tabs": ContextKind.RESTORABLE,
    "recent_tabs": ContextKind.RECORD_ONLY,
    "open_files": ContextKind.RESTORABLE,
    "source_plugin": ContextKind.RECORD_ONLY,
    "capture_trigger": ContextKind.RECORD_ONLY,
    "session_duration_sec": ContextKind.RECORD_ONLY,
}
