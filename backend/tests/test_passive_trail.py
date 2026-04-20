from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from flow_engine.context.aw_plugin import ActivityWatchTrailCollector
from flow_engine.context.base_plugin import ContextPlugin, ContextService, Snapshot, SnapshotManager
from flow_engine.context.trail import TrailCollector, TrailEvent, TrailStore


class FixedPlugin(ContextPlugin):
    def __init__(self, name: str = "fake") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def available(self) -> bool:
        return True

    async def capture(self) -> dict[str, object]:
        return {
            "active_window": "Editor",
            "active_url": "https://example.com",
            "active_file": "/tmp/main.py",
        }


class FixedCollector(TrailCollector):
    @property
    def source_name(self) -> str:
        return "fixed"

    async def collect(self, task_id: int, snapshot: Snapshot) -> list[TrailEvent]:
        return [TrailEvent(
            task_id=task_id,
            timestamp=snapshot.timestamp,
            source=self.source_name,
            event_type="window_focus",
            summary=snapshot.active_window or "unknown",
            metadata={"capture_trigger": snapshot.capture_trigger},
        )]


class FailingTrailStore(TrailStore):
    def append(self, event: TrailEvent) -> None:
        raise RuntimeError("trail append failed")


class FailingSnapshotManager(SnapshotManager):
    def save(self, snapshot: Snapshot) -> Path:
        raise RuntimeError("snapshot save failed")


def test_trail_store_append_query_and_jsonl_format(tmp_path: Path) -> None:
    store = TrailStore(tmp_path / "trails")
    base = datetime(2026, 4, 20, 10, 0, 0)

    store.append(TrailEvent(task_id=4, timestamp=base, source="fixed", event_type="window_focus", summary="A"))
    store.append(TrailEvent(task_id=4, timestamp=base + timedelta(minutes=30), source="fixed", event_type="url_visit", summary="B"))
    store.append(TrailEvent(task_id=4, timestamp=base + timedelta(hours=1), source="fixed", event_type="window_focus", summary="C"))

    assert [event.summary for event in store.query(4)] == ["A", "B", "C"]
    assert [event.summary for event in store.query(4, since=base + timedelta(minutes=20))] == ["B", "C"]

    lines = (tmp_path / "trails" / "4.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert all(isinstance(json.loads(line), dict) for line in lines)


def test_trail_write_failure_does_not_break_snapshot_save(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager = SnapshotManager(tmp_path / "snapshots")
        service = ContextService(manager, trail_store=FailingTrailStore(tmp_path / "trails"))
        service.register(FixedPlugin())
        service.register_collector(FixedCollector())

        snapshot = await service.capture_async(1, capture_trigger="PAUSE")

        assert snapshot.capture_trigger == "PAUSE"
        assert manager.load_latest(1) is not None

    asyncio.run(scenario())


def test_snapshot_save_failure_does_not_erase_trail_write(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = TrailStore(tmp_path / "trails")
        service = ContextService(FailingSnapshotManager(tmp_path / "snapshots"), trail_store=store)
        service.register(FixedPlugin())
        service.register_collector(FixedCollector())

        with pytest.raises(RuntimeError, match="snapshot save failed"):
            await service.capture_async(2, capture_trigger="PAUSE")

        events = store.query(2)
        assert len(events) == 1
        assert events[0].metadata["capture_trigger"] == "PAUSE"

    asyncio.run(scenario())


def test_activitywatch_collector_produces_trail_events(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = TrailStore(tmp_path / "trails")
        service = ContextService(SnapshotManager(tmp_path / "snapshots"), trail_store=store)
        service.register(FixedPlugin(name="activitywatch"))
        service.register_collector(ActivityWatchTrailCollector())

        await service.capture_async(3, capture_trigger="START")

        events = store.query(3)
        assert [event.event_type for event in events] == ["window_focus", "url_visit"]
        assert all(event.source == "activitywatch" for event in events)

    asyncio.run(scenario())
