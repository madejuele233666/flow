from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from flow_engine.context.base_plugin import Snapshot, SnapshotManager
from flow_engine.context.models import ContextKind, FIELD_CLASSIFICATION


def test_snapshot_build_extracts_known_fields_and_preserves_unknowns() -> None:
    snapshot = Snapshot.build(7, {
        "schema_version": 1,
        "active_window": "Editor",
        "active_url": "https://example.com",
        "active_file": "/tmp/main.py",
        "active_workspace": "/tmp",
        "open_windows": ["Editor", "Browser"],
        "open_tabs": ["main.py"],
        "recent_tabs": ["docs.py"],
        "open_files": ["/tmp/main.py"],
        "source_plugin": "fake",
        "capture_trigger": "PAUSE",
        "session_duration_sec": 42,
        "custom_plugin_data": {"foo": "bar"},
    })

    assert snapshot.task_id == 7
    assert snapshot.schema_version == 3
    assert snapshot.active_window == "Editor"
    assert snapshot.active_file == "/tmp/main.py"
    assert snapshot.open_tabs == ["main.py"]
    assert snapshot.recent_tabs == ["docs.py"]
    assert snapshot.source_plugin == "fake"
    assert snapshot.capture_trigger == "PAUSE"
    assert snapshot.session_duration_sec == 42
    assert snapshot.extra == {"custom_plugin_data": {"foo": "bar"}}
    assert FIELD_CLASSIFICATION["active_window"] == ContextKind.ACTIVE
    assert FIELD_CLASSIFICATION["open_files"] == ContextKind.RESTORABLE
    assert FIELD_CLASSIFICATION["recent_tabs"] == ContextKind.RECORD_ONLY
    assert FIELD_CLASSIFICATION["capture_trigger"] == ContextKind.RECORD_ONLY


def test_snapshot_manager_round_trip_preserves_all_fields(tmp_path: Path) -> None:
    manager = SnapshotManager(tmp_path / "snapshots")
    original = Snapshot(
        task_id=3,
        timestamp=datetime(2026, 4, 20, 10, 30, 0),
        schema_version=3,
        active_window="Editor",
        active_url="https://example.com",
        active_file="/tmp/main.py",
        active_workspace="/tmp",
        open_windows=["Editor"],
        open_tabs=["main.py"],
        recent_tabs=["docs.py"],
        open_files=["/tmp/main.py"],
        source_plugin="fake",
        capture_trigger="START",
        session_duration_sec=99,
        extra={"custom": True},
    )

    manager.save(original)
    restored = manager.load_latest(3)

    assert restored == original


def test_snapshot_manager_loads_legacy_v1_json_with_defaults(tmp_path: Path) -> None:
    snapshots_dir = tmp_path / "snapshots" / "9"
    snapshots_dir.mkdir(parents=True)
    legacy_path = snapshots_dir / "20260420_103000.json"
    legacy_path.write_text(json.dumps({
        "task_id": 9,
        "timestamp": "2026-04-20T10:30:00",
        "active_window": "Legacy Editor",
        "active_url": "https://legacy.example.com",
        "extra": {"legacy": True},
    }), encoding="utf-8")

    manager = SnapshotManager(tmp_path / "snapshots")
    restored = manager.load_latest(9)

    assert restored is not None
    assert restored.schema_version == 1
    assert restored.active_window == "Legacy Editor"
    assert restored.active_file == ""
    assert restored.active_workspace == ""
    assert restored.open_windows == []
    assert restored.open_tabs == []
    assert restored.recent_tabs == []
    assert restored.open_files == []
    assert restored.source_plugin == ""
    assert restored.capture_trigger == ""
    assert restored.session_duration_sec == 0
    assert restored.extra == {"legacy": True}
