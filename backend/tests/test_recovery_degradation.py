from __future__ import annotations

import asyncio
from pathlib import Path

from flow_engine.app import FlowApp
from flow_engine.client import LocalClient
from flow_engine.config import AppConfig
from flow_engine.context.base_plugin import Snapshot
from flow_engine.notifications.base import Notification, Notifier, NotifyLevel


class FakeContext:
    def __init__(self) -> None:
        self.snapshots: dict[int, Snapshot] = {}
        self.fail_restore_for: set[int] = set()

    async def capture_async(self, task_id: int, *, capture_trigger: str = "") -> Snapshot:
        snapshot = Snapshot(
            task_id=task_id,
            active_window=f"window-{task_id}",
            active_file=f"/tmp/file-{task_id}.py",
            active_workspace=f"/tmp/workspace-{task_id}",
            open_windows=[f"window-{task_id}"],
            open_tabs=[f"tab-{task_id}"],
            open_files=[f"/tmp/file-{task_id}.py"],
            active_url=f"https://example.com/{task_id}",
            source_plugin="fake",
            capture_trigger=capture_trigger,
            session_duration_sec=60,
        )
        self.snapshots[task_id] = snapshot
        return snapshot

    def restore_latest(self, task_id: int) -> Snapshot | None:
        if task_id in self.fail_restore_for:
            raise RuntimeError(f"restore failed for {task_id}")
        return self.snapshots.get(task_id)


class RecordingNotifier(Notifier):
    def __init__(self) -> None:
        self.records: list[Notification] = []

    @property
    def name(self) -> str:
        return "recording"

    def send(self, notification: Notification) -> bool:
        self.records.append(notification)
        return True


def _build_client(tmp_path: Path, context: FakeContext) -> tuple[LocalClient, FlowApp, RecordingNotifier]:
    config = AppConfig()
    config.paths.data_dir = tmp_path / "data"
    config.git.enabled = False
    config.git.auto_commit = False
    config.notifications.enabled = False
    config.plugin_breaker.safe_mode = True
    config.context.enabled = False

    app = FlowApp(config)
    app.context = context
    notifier = RecordingNotifier()
    app.notifications.register(notifier)
    return LocalClient(app), app, notifier


def test_recovery_degradation_levels_and_failure_isolation(tmp_path: Path) -> None:
    async def scenario() -> None:
        context = FakeContext()
        client, app, notifier = _build_client(tmp_path, context)
        try:
            await client.add_task(title="full")
            context.snapshots[1] = Snapshot(
                task_id=1,
                active_window="window-1",
                active_file="/tmp/file-1.py",
                active_workspace="/tmp/workspace-1",
                open_windows=["window-1"],
                open_tabs=["tab-1"],
                open_files=["/tmp/file-1.py"],
                active_url="https://example.com/1",
                source_plugin="fake",
                capture_trigger="PAUSE",
                session_duration_sec=30,
            )
            full = await client.start_task(1)
            assert full["restore_report"]["failed"] == []
            assert full["restore_report"]["degraded"] == []
            assert full["restore_report"]["user_message"] is None
            await client.done_task()

            await client.add_task(title="activitywatch-default")
            context.snapshots[2] = Snapshot(
                task_id=2,
                active_window="window-2",
                active_url="https://example.com/2",
                source_plugin="activitywatch",
                capture_trigger="PAUSE",
                session_duration_sec=30,
            )
            aw_default = await client.start_task(2)
            assert aw_default["restore_report"]["failed"] == []
            assert aw_default["restore_report"]["degraded"] == []
            assert aw_default["restore_report"]["user_message"] is None
            assert not notifier.records
            await client.done_task()

            await client.add_task(title="partial")
            context.snapshots[3] = Snapshot(
                task_id=3,
                active_window="window-3",
                active_file="/tmp/file-3.py",
                active_workspace="/tmp/workspace-3",
                open_windows=["window-3"],
                open_tabs=["tab-3"],
                open_files=["/tmp/file-3.py"],
                active_url="https://example.com/3",
                source_plugin="fake",
                capture_trigger="PAUSE",
                session_duration_sec=30,
                extra={"restore_degraded_fields": ["open_windows", "open_tabs", "active_url"]},
            )
            partial = await client.start_task(3)
            assert partial["restore_report"]["failed"] == []
            assert set(partial["restore_report"]["degraded"]) == {"open_windows", "open_tabs", "active_url"}
            assert partial["restore_report"]["user_message"] is None
            await client.done_task()

            await client.add_task(title="display-only")
            context.snapshots[4] = Snapshot(
                task_id=4,
                source_plugin="fake",
                capture_trigger="PAUSE",
                session_duration_sec=30,
            )
            display_only = await client.start_task(4)
            assert display_only["restore_report"]["failed"] == []
            assert display_only["restore_report"]["degraded"] == []
            assert display_only["restore_report"]["user_message"] is not None
            assert notifier.records[-1].level == NotifyLevel.INFO
            await client.done_task()

            await client.add_task(title="empty")
            empty = await client.start_task(5)
            assert empty["restore_report"] == {
                "task_id": 5,
                "restored": {},
                "degraded": [],
                "failed": [],
                "user_message": None,
            }
            await client.done_task()

            await client.add_task(title="restore-error")
            context.fail_restore_for.add(6)
            restore_error = await client.start_task(6)
            assert restore_error["state"] == "In Progress"
            assert restore_error["restore_report"] == {
                "task_id": 6,
                "restored": {},
                "degraded": [],
                "failed": [],
                "user_message": None,
            }
        finally:
            await app.shutdown()

    asyncio.run(scenario())
