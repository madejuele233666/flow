from __future__ import annotations

import asyncio
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from flow_engine.app import FlowApp
from flow_engine.client import LocalClient, RemoteClient, create_client
from flow_engine.config import AppConfig
from flow_engine.context.base_plugin import Snapshot
from flow_engine.context.recovery_execution import (
    RecoveryAction,
    RecoveryActionType,
    RecoveryExecutionService,
    RecoveryExecutorRegistry,
)
from flow_engine.notifications.base import Notification, Notifier, NotifyLevel
from flow_engine.daemon import FlowDaemon
from flow_engine.events import EventType
from flow_engine.state.machine import TaskState
from flow_engine.state.transitions import TransitionVetoedError
from flow_engine.storage.task_model import Task


class FakeContext:
    def __init__(self) -> None:
        self.snapshots: dict[int, Snapshot] = {}
        self.capture_calls: list[tuple[int, str]] = []
        self.restore_calls: list[int] = []
        self.fail_capture_for: set[int] = set()
        self.fail_restore_for: set[int] = set()

    async def capture_async(self, task_id: int, *, capture_trigger: str = "") -> Snapshot:
        self.capture_calls.append((task_id, capture_trigger))
        if task_id in self.fail_capture_for:
            raise RuntimeError(f"capture failed for {task_id}")
        snapshot = Snapshot(
            task_id=task_id,
            active_window=f"window-{task_id}",
            active_file=f"/tmp/file-{task_id}.py",
            active_workspace=f"/tmp/workspace-{task_id}",
            open_windows=[f"window-{task_id}"],
            open_tabs=[f"tab-{task_id}"],
            open_files=[f"/tmp/file-{task_id}.py"],
            source_plugin="fake",
            capture_trigger=capture_trigger,
            session_duration_sec=300,
        )
        self.snapshots[task_id] = snapshot
        return snapshot

    def restore_latest(self, task_id: int) -> Snapshot | None:
        self.restore_calls.append(task_id)
        if task_id in self.fail_restore_for:
            raise RuntimeError(f"restore failed for {task_id}")
        return self.snapshots.get(task_id)


class DaemonAdapter:
    def __init__(self, daemon: FlowDaemon, client: RemoteClient) -> None:
        self._daemon = daemon
        self._client = client

    async def start(self) -> None:
        await self._daemon._ipc.start()
        await self._client.connect()

    async def close(self) -> None:
        await self._client.close()
        await self._daemon._ipc.stop()

    async def add_task(self, **params):
        return await self._client.add_task(**params)

    async def start_task(self, task_id: int):
        return await self._client.start_task(task_id)

    async def done_task(self):
        return await self._client.done_task()

    async def pause_task(self):
        return await self._client.pause_task()

    async def resume_task(self, task_id: int):
        return await self._client.resume_task(task_id)

    async def block_task(self, task_id: int, reason: str = ""):
        return await self._client.block_task(task_id, reason=reason)

    async def get_status(self):
        return await self._client.get_status()


class RecordingNotifier(Notifier):
    def __init__(self) -> None:
        self.records: list[Notification] = []

    @property
    def name(self) -> str:
        return "recording"

    def send(self, notification: Notification) -> bool:
        self.records.append(notification)
        return True


class FailingExecutor:
    async def execute(self, action: RecoveryAction) -> tuple[bool, str]:
        return False, "forced failure"


def _assert_report_v2(report: dict, *, task_id: int, status: str | None = None) -> None:
    assert set(report) == {
        "version",
        "task_id",
        "overall_status",
        "execution_enabled",
        "actions",
        "browser_session",
        "user_message",
    }
    assert report["version"] == 2
    assert report["task_id"] == task_id
    if status is not None:
        assert report["overall_status"] == status


def _build_app(tmp_path: Path, context: FakeContext | None = None, *, safe_mode: bool = True) -> FlowApp:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    config = AppConfig()
    config.paths.data_dir = data_dir
    config.git.enabled = False
    config.git.auto_commit = False
    config.notifications.enabled = False
    config.plugin_breaker.safe_mode = safe_mode
    config.context.enabled = False
    config.context.capture_on_switch = True

    app = FlowApp(config)
    if context is not None:
        app.context = context
    return app


async def _build_mode(
    mode: str,
    tmp_path: Path,
    context: FakeContext | None = None,
    *,
    safe_mode: bool = True,
):
    app = _build_app(tmp_path, context=context, safe_mode=safe_mode)
    if mode == "local":
        return LocalClient(app), app
    if mode == "daemon":
        daemon = FlowDaemon(app)
        socket_path = app.config.paths.data_dir / app.config.daemon.socket_name
        adapter = DaemonAdapter(daemon, RemoteClient(socket_path=socket_path))
        await adapter.start()
        return adapter, app
    raise AssertionError(f"unknown mode: {mode}")


def test_local_and_daemon_lifecycle_payloads_stay_in_parity(tmp_path: Path) -> None:
    async def scenario() -> None:
        local_context = FakeContext()
        daemon_context = FakeContext()
        local, local_app = await _build_mode("local", tmp_path / "local", local_context)
        daemon, daemon_app = await _build_mode("daemon", tmp_path / "daemon", daemon_context)
        try:
            local_add = await local.add_task(title="alpha", priority=1)
            daemon_add = await daemon.add_task(title="alpha", priority=1)
            assert set(local_add) == {"id", "title", "priority", "state"}
            assert local_add == daemon_add

            await local.add_task(title="beta", priority=2)
            await daemon.add_task(title="beta", priority=2)

            local_start = await local.start_task(1)
            daemon_start = await daemon.start_task(1)
            assert set(local_start) == {"id", "title", "state", "paused", "restore_report"}
            assert local_start == daemon_start
            _assert_report_v2(local_start["restore_report"], task_id=1)

            local_status = await local.get_status()
            daemon_status = await daemon.get_status()
            assert set(local_status) == {"active", "break_suggested"}
            assert set(local_status["active"]) == {"id", "title", "priority", "state", "duration_min"}
            assert local_status == daemon_status

            local_pause = await local.pause_task()
            daemon_pause = await daemon.pause_task()
            assert set(local_pause) == {"id", "title", "state"}
            assert local_pause == daemon_pause

            local_resume = await local.resume_task(1)
            daemon_resume = await daemon.resume_task(1)
            assert set(local_resume) == {"id", "title", "state", "restore_report"}
            assert local_resume == daemon_resume
            _assert_report_v2(local_resume["restore_report"], task_id=1)

            local_block = await local.block_task(1, reason="waiting")
            daemon_block = await daemon.block_task(1, reason="waiting")
            assert set(local_block) == {"id", "title", "state", "reason"}
            assert local_block == daemon_block

            local_resume_blocked = await local.resume_task(1)
            daemon_resume_blocked = await daemon.resume_task(1)
            assert set(local_resume_blocked) == {"id", "title", "state", "restore_report"}
            assert local_resume_blocked == daemon_resume_blocked
            assert local_resume_blocked["state"] == TaskState.IN_PROGRESS.value

            local_done = await local.done_task()
            daemon_done = await daemon.done_task()
            assert set(local_done) == {"id", "title", "state"}
            assert local_done == daemon_done

            assert await local.get_status() == {"active": None, "break_suggested": False}
            assert await daemon.get_status() == {"active": None, "break_suggested": False}
        finally:
            await daemon.close()
            await local_app.shutdown()
            await daemon_app.shutdown()

    asyncio.run(scenario())


def test_business_error_parity_and_transport_specific_failures(tmp_path: Path) -> None:
    async def scenario() -> None:
        local, local_app = await _build_mode("local", tmp_path / "local")
        daemon, daemon_app = await _build_mode("daemon", tmp_path / "daemon")
        try:
            await local.add_task(title="alpha")
            await daemon.add_task(title="alpha")

            missing_local = pytest.raises(ValueError)
            missing_daemon = pytest.raises(ValueError)
            with missing_local as local_exc:
                await local.start_task(99)
            with missing_daemon as daemon_exc:
                await daemon.start_task(99)
            assert str(local_exc.value) == str(daemon_exc.value) == "未找到任务 #99"

            illegal_local = pytest.raises(ValueError)
            illegal_daemon = pytest.raises(ValueError)
            with illegal_local as local_exc:
                await local.resume_task(1)
            with illegal_daemon as daemon_exc:
                await daemon.resume_task(1)
            assert str(local_exc.value) == str(daemon_exc.value)
            assert "无法恢复" in str(local_exc.value)

            await local.start_task(1)
            await daemon.start_task(1)
            await local.done_task()
            await daemon.done_task()

            with pytest.raises(ValueError) as local_exc:
                await local.start_task(1)
            with pytest.raises(ValueError) as daemon_exc:
                await daemon.start_task(1)
            assert str(local_exc.value) == str(daemon_exc.value)
            assert "Done" in str(local_exc.value)

            duplicated = [
                Task(id=1, title="alpha", state=TaskState.IN_PROGRESS),
                Task(id=2, title="beta", state=TaskState.IN_PROGRESS),
            ]
            await local_app.repo.save_all([replace(task) for task in duplicated])
            await daemon_app.repo.save_all([replace(task) for task in duplicated])

            for op_name in ("get_status", "pause_task", "done_task"):
                with pytest.raises(ValueError) as local_exc:
                    await getattr(local, op_name)()
                with pytest.raises(ValueError) as daemon_exc:
                    await getattr(daemon, op_name)()
                assert str(local_exc.value) == str(daemon_exc.value)
                assert "多个进行中的任务" in str(local_exc.value)

            offline = RemoteClient(socket_path=tmp_path / "missing.sock")
            with pytest.raises(ConnectionError):
                await offline.connect()
        finally:
            await daemon.close()
            await local_app.shutdown()
            await daemon_app.shutdown()

    asyncio.run(scenario())


def test_illegal_start_does_not_emit_auto_pause_side_effects(tmp_path: Path) -> None:
    async def scenario() -> None:
        local, local_app = await _build_mode("local", tmp_path / "local")
        daemon, daemon_app = await _build_mode("daemon", tmp_path / "daemon")
        local_events: list[tuple[int, TaskState, TaskState]] = []
        daemon_events: list[tuple[int, TaskState, TaskState]] = []

        def record_local(event) -> None:
            payload = event.payload
            local_events.append((payload.task_id, payload.old_state, payload.new_state))

        def record_daemon(event) -> None:
            payload = event.payload
            daemon_events.append((payload.task_id, payload.old_state, payload.new_state))

        local_app.bus.subscribe(EventType.TASK_STATE_CHANGED, record_local)
        daemon_app.bus.subscribe(EventType.TASK_STATE_CHANGED, record_daemon)

        fixture = [
            Task(id=1, title="done", state=TaskState.DONE),
            Task(id=2, title="active", state=TaskState.IN_PROGRESS),
        ]
        await local_app.repo.save_all([replace(task) for task in fixture])
        await daemon_app.repo.save_all([replace(task) for task in fixture])

        try:
            with pytest.raises(ValueError) as local_exc:
                await local.start_task(1)
            with pytest.raises(ValueError) as daemon_exc:
                await daemon.start_task(1)

            assert str(local_exc.value) == str(daemon_exc.value)
            assert local_events == []
            assert daemon_events == []

            local_states = {task.id: task.state for task in await local_app.repo.load_all()}
            daemon_states = {task.id: task.state for task in await daemon_app.repo.load_all()}
            expected = {
                1: TaskState.DONE,
                2: TaskState.IN_PROGRESS,
            }
            assert local_states == expected
            assert daemon_states == expected
        finally:
            await daemon.close()
            await local_app.shutdown()
            await daemon_app.shutdown()

    asyncio.run(scenario())


def test_transition_veto_failure_stays_in_local_daemon_parity(tmp_path: Path) -> None:
    class VetoPlugin:
        async def before_task_transition(self, payload) -> bool:
            return payload.task.id != 1

    async def scenario() -> None:
        local, local_app = await _build_mode("local", tmp_path / "local", safe_mode=False)
        daemon, daemon_app = await _build_mode("daemon", tmp_path / "daemon", safe_mode=False)
        local_app.hooks.register(VetoPlugin())
        daemon_app.hooks.register(VetoPlugin())

        try:
            await local.add_task(title="alpha")
            await daemon.add_task(title="alpha")

            with pytest.raises(TransitionVetoedError) as local_exc:
                await local.start_task(1)
            with pytest.raises(TransitionVetoedError) as daemon_exc:
                await daemon.start_task(1)

            assert str(local_exc.value) == str(daemon_exc.value)
        finally:
            await daemon.close()
            await local_app.shutdown()
            await daemon_app.shutdown()

    asyncio.run(scenario())


def test_vetoed_start_and_resume_do_not_emit_auto_pause_side_effects(tmp_path: Path) -> None:
    class VetoTaskOnePlugin:
        async def before_task_transition(self, payload) -> bool:
            return payload.task.id != 1

    async def assert_no_side_effects(
        operation_name: str,
        fixture: list[Task],
    ) -> None:
        local, local_app = await _build_mode("local", tmp_path / f"{operation_name}-local", safe_mode=False)
        daemon, daemon_app = await _build_mode("daemon", tmp_path / f"{operation_name}-daemon", safe_mode=False)
        local_events: list[tuple[int, TaskState, TaskState]] = []
        daemon_events: list[tuple[int, TaskState, TaskState]] = []

        def record_local(event) -> None:
            payload = event.payload
            local_events.append((payload.task_id, payload.old_state, payload.new_state))

        def record_daemon(event) -> None:
            payload = event.payload
            daemon_events.append((payload.task_id, payload.old_state, payload.new_state))

        local_app.hooks.register(VetoTaskOnePlugin())
        daemon_app.hooks.register(VetoTaskOnePlugin())
        local_app.bus.subscribe(EventType.TASK_STATE_CHANGED, record_local)
        daemon_app.bus.subscribe(EventType.TASK_STATE_CHANGED, record_daemon)
        await local_app.repo.save_all([replace(task) for task in fixture])
        await daemon_app.repo.save_all([replace(task) for task in fixture])

        try:
            local_op = getattr(local, operation_name)
            daemon_op = getattr(daemon, operation_name)

            with pytest.raises(TransitionVetoedError) as local_exc:
                await local_op(1)
            with pytest.raises(TransitionVetoedError) as daemon_exc:
                await daemon_op(1)

            assert str(local_exc.value) == str(daemon_exc.value)
            assert local_events == []
            assert daemon_events == []

            expected = {task.id: task.state for task in fixture}
            local_states = {task.id: task.state for task in await local_app.repo.load_all()}
            daemon_states = {task.id: task.state for task in await daemon_app.repo.load_all()}
            assert local_states == expected
            assert daemon_states == expected
        finally:
            await daemon.close()
            await local_app.shutdown()
            await daemon_app.shutdown()

    async def scenario() -> None:
        await assert_no_side_effects(
            "start_task",
            [
                Task(id=1, title="ready", state=TaskState.READY),
                Task(id=2, title="active", state=TaskState.IN_PROGRESS),
            ],
        )
        await assert_no_side_effects(
            "resume_task",
            [
                Task(id=1, title="paused", state=TaskState.PAUSED),
                Task(id=2, title="active", state=TaskState.IN_PROGRESS),
            ],
        )

    asyncio.run(scenario())


def test_start_snapshot_paths_degrade_without_breaking_task_flow(tmp_path: Path) -> None:
    async def run_mode(mode: str, context: FakeContext, root: Path) -> None:
        adapter, app = await _build_mode(mode, root, context)
        try:
            await adapter.add_task(title="alpha")

            first_start = await adapter.start_task(1)
            _assert_report_v2(first_start["restore_report"], task_id=1, status="empty")

            await adapter.pause_task()
            second_start = await adapter.start_task(1)
            _assert_report_v2(second_start["restore_report"], task_id=1, status="skipped")
            assert {action["field"] for action in second_start["restore_report"]["actions"]} >= {
                "active_window",
                "active_file",
                "active_workspace",
            }

            await adapter.pause_task()
            context.fail_capture_for.add(1)
            await adapter.start_task(1)
            await adapter.pause_task()
            context.fail_capture_for.clear()
            context.fail_restore_for.add(1)

            restore_failure = await adapter.start_task(1)
            _assert_report_v2(restore_failure["restore_report"], task_id=1, status="empty")
            assert (await adapter.get_status())["active"]["id"] == 1
        finally:
            if isinstance(adapter, DaemonAdapter):
                await adapter.close()
            await app.shutdown()

    async def scenario() -> None:
        await run_mode("local", FakeContext(), tmp_path / "local")
        await run_mode("daemon", FakeContext(), tmp_path / "daemon")

    asyncio.run(scenario())


def test_concurrent_starts_preserve_single_active_contract(tmp_path: Path) -> None:
    async def scenario() -> None:
        client, app = await _build_mode("local", tmp_path / "local", FakeContext())
        try:
            await client.add_task(title="alpha")
            await client.add_task(title="beta")

            first, second = await asyncio.gather(
                client.start_task(1),
                client.start_task(2),
            )

            paused_lengths = sorted([len(first["paused"]), len(second["paused"])])
            assert paused_lengths == [0, 1]

            tasks = await app.repo.load_all()
            in_progress = [task.id for task in tasks if task.state == TaskState.IN_PROGRESS]
            paused = sorted(task.id for task in tasks if task.state == TaskState.PAUSED)
            assert len(in_progress) == 1
            assert paused == [1] or paused == [2]
        finally:
            await app.shutdown()

    asyncio.run(scenario())


def test_create_client_uses_configured_daemon_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        data_dir = tmp_path / "configured-data"
        monkeypatch.setenv("FLOW_DATA_DIR", str(data_dir))

        config = AppConfig()
        config.paths.data_dir = data_dir
        config.git.enabled = False
        config.git.auto_commit = False
        config.notifications.enabled = False
        config.plugin_breaker.safe_mode = True
        config.context.enabled = False
        config.context.capture_on_switch = True

        app = FlowApp(config)
        daemon = FlowDaemon(app)
        await daemon._ipc.start()
        daemon._write_pid()

        client = None
        try:
            client = await create_client()
            assert isinstance(client, RemoteClient)
        finally:
            if client is not None and isinstance(client, RemoteClient):
                await client.close()
            await daemon._ipc.stop()
            daemon._remove_pid()
            await app.shutdown()
            monkeypatch.delenv("FLOW_DATA_DIR", raising=False)

    asyncio.run(scenario())


def test_default_git_auto_commit_persists_transition_state(tmp_path: Path) -> None:
    async def scenario() -> None:
        config = AppConfig()
        config.paths.data_dir = tmp_path / "git-data"
        config.notifications.enabled = False
        config.plugin_breaker.safe_mode = True
        config.context.enabled = False
        config.context.capture_on_switch = False

        app = FlowApp(config)
        subprocess.run(
            ["git", "config", "user.name", "Flow Test"],
            cwd=config.paths.data_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "flow-test@example.com"],
            cwd=config.paths.data_dir,
            check=True,
            capture_output=True,
            text=True,
        )

        client = LocalClient(app)
        try:
            await client.add_task(title="alpha")
            await client.start_task(1)

            log = app.vcs.log(5)
            assert any("task #1 → In Progress" in entry for entry in log)

            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=config.paths.data_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            assert status.stdout.strip() == ""
        finally:
            await app.shutdown()

    asyncio.run(scenario())


def test_capture_on_switch_false_disables_restore_for_start_and_resume(tmp_path: Path) -> None:
    async def scenario() -> None:
        context = FakeContext()
        config = AppConfig()
        config.paths.data_dir = tmp_path / "gate-data"
        config.git.enabled = False
        config.git.auto_commit = False
        config.notifications.enabled = False
        config.plugin_breaker.safe_mode = True
        config.context.enabled = False
        config.context.capture_on_switch = False

        app = FlowApp(config)
        app.context = context
        client = LocalClient(app)
        try:
            await client.add_task(title="alpha")
            context.snapshots[1] = Snapshot(
                task_id=1,
                active_window="window-1",
                active_file="/tmp/file-1.py",
                source_plugin="fake",
                capture_trigger="PAUSE",
            )

            started = await client.start_task(1)
            _assert_report_v2(started["restore_report"], task_id=1, status="empty")
            assert context.restore_calls == []

            await app.repo.save_all([Task(id=1, title="alpha", state=TaskState.PAUSED)])
            resumed = await client.resume_task(1)
            assert resumed["state"] == TaskState.IN_PROGRESS.value
            _assert_report_v2(resumed["restore_report"], task_id=1, status="empty")
            assert context.restore_calls == []
        finally:
            await app.shutdown()

    asyncio.run(scenario())


def test_done_task_captures_with_done_trigger(tmp_path: Path) -> None:
    async def scenario() -> None:
        context = FakeContext()
        client, app = await _build_mode("local", tmp_path / "local", context)
        try:
            await client.add_task(title="alpha")
            await client.start_task(1)
            await client.done_task()

            assert context.capture_calls[-1] == (1, "DONE")
            assert context.snapshots[1].capture_trigger == "DONE"
        finally:
            await app.shutdown()

    asyncio.run(scenario())


def test_resume_task_payload_stays_state_focused_after_restore(tmp_path: Path) -> None:
    async def scenario() -> None:
        context = FakeContext()
        client, app = await _build_mode("local", tmp_path / "local", context)
        try:
            await client.add_task(title="alpha")
            await client.start_task(1)
            await client.pause_task()

            result = await client.resume_task(1)
            assert set(result) == {"id", "title", "state", "restore_report"}
            assert result["state"] == TaskState.IN_PROGRESS.value
            _assert_report_v2(result["restore_report"], task_id=1)
            assert context.restore_calls[-1] == 1
        finally:
            await app.shutdown()

    asyncio.run(scenario())


def test_start_task_reports_restore_degradation_and_notifies(tmp_path: Path) -> None:
    async def scenario() -> None:
        context = FakeContext()
        client, app = await _build_mode("local", tmp_path / "local", context)
        notifier = RecordingNotifier()
        app.notifications.register(notifier)
        registry = RecoveryExecutorRegistry()
        registry.register(RecoveryActionType.OPEN_URL, FailingExecutor())
        app.recovery = RecoveryExecutionService(execution_enabled=True, registry=registry)

        try:
            await client.add_task(title="alpha")
            context.snapshots[1] = Snapshot(
                task_id=1,
                active_url="https://example.com/fail",
                source_plugin="fake",
                capture_trigger="PAUSE",
                session_duration_sec=120,
            )

            result = await client.start_task(1)

            _assert_report_v2(result["restore_report"], task_id=1, status="failed")
            assert result["restore_report"]["user_message"] is not None
            assert notifier.records
            assert notifier.records[-1].level == NotifyLevel.WARNING
        finally:
            await app.shutdown()

    asyncio.run(scenario())
