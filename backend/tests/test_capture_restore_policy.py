from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from flow_engine.app import FlowApp
from flow_engine.client import LocalClient
from flow_engine.config import AppConfig
from flow_engine.context.base_plugin import Snapshot
from flow_engine.context.policy import CaptureRestorePolicy, CaptureTrigger
from flow_engine.state.machine import TaskState
from flow_engine.state.transitions import TransitionVetoedError
from flow_engine.storage.task_model import Task


class FakeContext:
    def __init__(self) -> None:
        self.snapshots: dict[int, Snapshot] = {}
        self.capture_calls: list[tuple[int, str]] = []
        self.restore_calls: list[int] = []

    async def capture_async(self, task_id: int, *, capture_trigger: str = "") -> Snapshot:
        self.capture_calls.append((task_id, capture_trigger))
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
        )
        self.snapshots[task_id] = snapshot
        return snapshot

    def restore_latest(self, task_id: int) -> Snapshot | None:
        self.restore_calls.append(task_id)
        return self.snapshots.get(task_id)


def _build_client(
    tmp_path: Path,
    context: FakeContext,
    *,
    safe_mode: bool = True,
) -> tuple[LocalClient, FlowApp]:
    config = AppConfig()
    config.paths.data_dir = tmp_path / "data"
    config.git.enabled = False
    config.git.auto_commit = False
    config.notifications.enabled = False
    config.plugin_breaker.safe_mode = safe_mode
    config.context.enabled = False
    app = FlowApp(config)
    app.context = context
    return LocalClient(app), app


def test_capture_restore_policy_decision_table() -> None:
    policy = CaptureRestorePolicy()

    assert policy.should_capture(CaptureTrigger.PAUSE) is True
    assert policy.should_capture(CaptureTrigger.AUTO_PAUSE) is True
    assert policy.should_capture(CaptureTrigger.BLOCK, current_state=TaskState.IN_PROGRESS) is True
    assert policy.should_capture(CaptureTrigger.BLOCK, current_state=TaskState.PAUSED) is False
    assert policy.should_capture(CaptureTrigger.BLOCK, current_state=TaskState.READY) is False
    assert policy.should_capture(CaptureTrigger.DONE) is True
    assert policy.should_capture(CaptureTrigger.START) is False
    assert policy.should_capture(CaptureTrigger.RESUME) is False

    assert policy.should_restore(CaptureTrigger.START) is True
    assert policy.should_restore(CaptureTrigger.RESUME) is True
    assert policy.should_restore(CaptureTrigger.PAUSE) is False
    assert policy.should_restore(CaptureTrigger.BLOCK) is False
    assert policy.should_restore(CaptureTrigger.DONE) is False


def test_runtime_stamps_expected_capture_triggers(tmp_path: Path) -> None:
    async def scenario() -> None:
        context = FakeContext()
        client, app = _build_client(tmp_path, context, safe_mode=False)
        try:
            await client.add_task(title="alpha")
            await client.add_task(title="beta")

            await client.start_task(1)
            await client.start_task(2)
            assert context.capture_calls[-1] == (1, "AUTO_PAUSE")

            await client.block_task(2, reason="waiting")
            assert context.capture_calls[-1] == (2, "BLOCK")

            await client.resume_task(2)
            await client.pause_task()
            assert context.capture_calls[-1] == (2, "PAUSE")

            await client.resume_task(2)
            await client.done_task()
            assert context.capture_calls[-1] == (2, "DONE")
        finally:
            await app.shutdown()

    asyncio.run(scenario())


def test_illegal_and_vetoed_transitions_do_not_capture(tmp_path: Path) -> None:
    class VetoPlugin:
        async def before_task_transition(self, payload) -> bool:
            return payload.task.id != 1

    async def scenario() -> None:
        context = FakeContext()
        client, app = _build_client(tmp_path, context, safe_mode=False)
        app.hooks.register(VetoPlugin())
        try:
            await client.add_task(title="alpha")

            with pytest.raises(TransitionVetoedError):
                await client.start_task(1)
            assert context.capture_calls == []

            await app.repo.save_all([
                Task(id=1, title="done", state=TaskState.DONE),
                Task(id=2, title="active", state=TaskState.IN_PROGRESS),
            ])
            with pytest.raises(ValueError):
                await client.start_task(1)
            assert context.capture_calls == []
        finally:
            await app.shutdown()

    asyncio.run(scenario())


def test_block_capture_decision_is_policy_driven(tmp_path: Path) -> None:
    async def scenario() -> None:
        context = FakeContext()
        client, app = _build_client(tmp_path, context)
        try:
            await app.repo.save_all([Task(id=1, title="paused", state=TaskState.PAUSED)])

            with pytest.raises(ValueError):
                await client.block_task(1, reason="waiting")

            assert context.capture_calls == []
            assert client._task_flow._policy.should_capture(  # type: ignore[attr-defined]
                CaptureTrigger.BLOCK,
                current_state=TaskState.PAUSED,
            ) is False
        finally:
            await app.shutdown()

    asyncio.run(scenario())
