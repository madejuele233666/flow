from __future__ import annotations

import asyncio

from flow_engine.context.base_plugin import Snapshot
from flow_engine.context.recovery_execution import (
    CommandResult,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryExecutionService,
    RecoveryExecutorRegistry,
    RecoveryPlanner,
    WindowsDefaultOpenExecutor,
)


class RecordingExecutor:
    def __init__(self, *, ok: bool = True, reason: str = "") -> None:
        self.ok = ok
        self.reason = reason
        self.calls: list[RecoveryAction] = []

    async def execute(self, action: RecoveryAction) -> tuple[bool, str]:
        self.calls.append(action)
        return self.ok, self.reason


def test_planner_builds_browser_file_workspace_and_unsupported_focus_actions() -> None:
    snapshot = Snapshot(
        task_id=1,
        active_window="Editor",
        active_url="https://active.example",
        open_tabs=["https://docs.example", "https://active.example"],
        recent_tabs=["https://docs.example", "https://search.example"],
        active_file="/tmp/file.py",
        active_workspace="/tmp/workspace",
        source_plugin="fake",
        extra={"browser_session_source": "derived_aw_last_browser_segment", "browser_tab_count": 3},
    )

    planner = RecoveryPlanner()
    actions = planner.plan(snapshot)

    assert [(action.type, action.field, action.role, action.target) for action in actions] == [
        ("open_url", "active_url", "active", "https://active.example"),
        ("open_url", "open_tabs", "secondary", "https://docs.example"),
        ("open_file", "active_file", "active", "/tmp/file.py"),
        ("open_workspace", "active_workspace", "workspace", "/tmp/workspace"),
        ("focus_window", "active_window", "focus", "Editor"),
    ]
    assert actions[0].source == "derived_aw_last_browser_segment"
    assert planner.browser_session_summary(snapshot)["browser_tab_count"] == 3


def test_execution_disabled_skips_actions_without_calling_executor() -> None:
    async def scenario() -> None:
        executor = RecordingExecutor()
        registry = RecoveryExecutorRegistry()
        registry.register(RecoveryActionType.OPEN_URL, executor)
        service = RecoveryExecutionService(execution_enabled=False, registry=registry)
        report = await service.restore(
            1,
            Snapshot(task_id=1, active_url="https://example.com"),
        )

        assert report.overall_status == "skipped"
        assert report.execution_enabled is False
        assert report.actions[0].status == RecoveryActionStatus.SKIPPED.value
        assert report.actions[0].reason == "execution_disabled"
        assert executor.calls == []

    asyncio.run(scenario())


def test_execution_reports_unsupported_and_failed_actions_without_raising() -> None:
    async def scenario() -> None:
        failing = RecordingExecutor(ok=False, reason="boom")
        registry = RecoveryExecutorRegistry()
        registry.register(RecoveryActionType.OPEN_URL, failing)
        service = RecoveryExecutionService(execution_enabled=True, registry=registry)
        report = await service.restore(
            1,
            Snapshot(task_id=1, active_url="https://example.com", active_window="Editor"),
        )

        assert report.overall_status == "partial"
        assert [action.status for action in report.actions] == ["failed", "unsupported"]
        assert report.user_message is not None

    asyncio.run(scenario())


def test_windows_wsl_opener_converts_linux_path_before_default_open() -> None:
    calls: list[tuple[list[str], bool]] = []

    def runner(cmd: list[str], timeout: float, capture_output: bool) -> CommandResult:
        calls.append((cmd, capture_output))
        if cmd[0].endswith("wslpath"):
            return CommandResult(returncode=0, stdout="C:\\Users\\madejuele\\file.py\n")
        return CommandResult(returncode=0)

    executor = WindowsDefaultOpenExecutor(timeout_seconds=2.0, runner=runner)
    ok, reason = asyncio.run(executor.execute(RecoveryAction(
        id="active_file:0",
        type="open_file",
        field="active_file",
        role="active",
        target="/home/madejuele/file.py",
    )))

    assert ok is True
    assert reason == ""
    assert calls[0][0][-2:] == ["-w", "/home/madejuele/file.py"]
    assert calls[0][1] is True
    assert calls[1][0][-1] == "C:\\Users\\madejuele\\file.py"
    assert calls[1][1] is False


def test_windows_wsl_opener_opens_url_without_path_conversion() -> None:
    calls: list[list[str]] = []

    def runner(cmd: list[str], timeout: float, capture_output: bool) -> CommandResult:
        calls.append(cmd)
        return CommandResult(returncode=0)

    executor = WindowsDefaultOpenExecutor(timeout_seconds=2.0, runner=runner)
    ok, _ = asyncio.run(executor.execute(RecoveryAction(
        id="active_url:0",
        type="open_url",
        field="active_url",
        role="active",
        target="https://example.com",
    )))

    assert ok is True
    assert len(calls) == 1
    assert calls[0][-1] == "https://example.com"
