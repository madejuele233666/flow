"""Executable context recovery planning, execution, and report v2."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from flow_engine.context.recovery import RESTORE_PRIORITY

if TYPE_CHECKING:
    from flow_engine.context.base_plugin import Snapshot

logger = logging.getLogger(__name__)


class RecoveryActionType(str, Enum):
    OPEN_URL = "open_url"
    OPEN_FILE = "open_file"
    OPEN_WORKSPACE = "open_workspace"
    FOCUS_WINDOW = "focus_window"


class RecoveryActionStatus(str, Enum):
    PLANNED = "planned"
    EXECUTED = "executed"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class RecoveryAction:
    id: str
    type: str
    field: str
    role: str
    target: str
    status: str = RecoveryActionStatus.PLANNED.value
    reason: str = ""
    source: str = ""
    priority: str = ""

    def with_result(self, status: RecoveryActionStatus | str, reason: str = "") -> RecoveryAction:
        status_value = status.value if isinstance(status, RecoveryActionStatus) else str(status)
        return replace(self, status=status_value, reason=reason)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class RecoveryReport:
    task_id: int
    version: int = 2
    overall_status: str = "empty"
    execution_enabled: bool = False
    actions: list[RecoveryAction] = field(default_factory=list)
    browser_session: dict[str, object] = field(default_factory=dict)
    user_message: str | None = None

    @classmethod
    def empty(cls, task_id: int, *, execution_enabled: bool = False) -> RecoveryReport:
        return cls(task_id=task_id, execution_enabled=execution_enabled)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "task_id": self.task_id,
            "overall_status": self.overall_status,
            "execution_enabled": self.execution_enabled,
            "actions": [action.to_dict() for action in self.actions],
            "browser_session": dict(self.browser_session),
            "user_message": self.user_message,
        }


class RecoveryExecutor(Protocol):
    async def execute(self, action: RecoveryAction) -> tuple[bool, str]: ...


class RecoveryExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, RecoveryExecutor] = {}

    def register(self, action_type: str | RecoveryActionType, executor: RecoveryExecutor) -> None:
        type_value = action_type.value if isinstance(action_type, RecoveryActionType) else str(action_type)
        self._executors[type_value] = executor

    def get(self, action_type: str) -> RecoveryExecutor | None:
        return self._executors.get(action_type)


class RecoveryPlanner:
    """Build executable recovery actions from a semantic snapshot."""

    def plan(self, snapshot: Snapshot) -> list[RecoveryAction]:
        actions: list[RecoveryAction] = []
        source = str(snapshot.extra.get("browser_session_source") or snapshot.source_plugin or "")

        if snapshot.active_url:
            actions.append(self._action(
                action_type=RecoveryActionType.OPEN_URL,
                field="active_url",
                role="active",
                target=snapshot.active_url,
                source=source,
                index=len(actions),
            ))

        for tab in snapshot.open_tabs:
            if not tab or tab == snapshot.active_url:
                continue
            actions.append(self._action(
                action_type=RecoveryActionType.OPEN_URL,
                field="open_tabs",
                role="secondary",
                target=tab,
                source=source,
                index=len(actions),
            ))

        if snapshot.active_file:
            actions.append(self._action(
                action_type=RecoveryActionType.OPEN_FILE,
                field="active_file",
                role="active",
                target=snapshot.active_file,
                source=snapshot.source_plugin,
                index=len(actions),
            ))

        if snapshot.active_workspace:
            actions.append(self._action(
                action_type=RecoveryActionType.OPEN_WORKSPACE,
                field="active_workspace",
                role="workspace",
                target=snapshot.active_workspace,
                source=snapshot.source_plugin,
                index=len(actions),
            ))

        if snapshot.active_window:
            actions.append(self._action(
                action_type=RecoveryActionType.FOCUS_WINDOW,
                field="active_window",
                role="focus",
                target=snapshot.active_window,
                source=snapshot.source_plugin,
                index=len(actions),
            ))

        return actions

    def browser_session_summary(self, snapshot: Snapshot) -> dict[str, object]:
        summary: dict[str, object] = {}
        if snapshot.active_url:
            summary["active_url"] = snapshot.active_url
        if snapshot.open_tabs:
            summary["open_tabs"] = list(snapshot.open_tabs)
        if snapshot.recent_tabs:
            summary["recent_tabs"] = list(snapshot.recent_tabs)
        for key in (
            "browser_session_source",
            "browser_tab_count",
            "browser_app",
            "browser_title",
            "browser_segment_start",
            "browser_segment_end",
        ):
            if key in snapshot.extra:
                summary[key] = snapshot.extra[key]
        return summary

    def _action(
        self,
        *,
        action_type: RecoveryActionType,
        field: str,
        role: str,
        target: str,
        source: str,
        index: int,
    ) -> RecoveryAction:
        priority = RESTORE_PRIORITY.get(field)
        return RecoveryAction(
            id=f"{field}:{index}",
            type=action_type.value,
            field=field,
            role=role,
            target=target,
            source=source,
            priority=priority.value if priority else "",
        )


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[list[str], float, bool], CommandResult]


class WindowsDefaultOpenExecutor:
    """Open URLs/files/workspaces through Windows default applications from WSL."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        runner: CommandRunner | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._runner = runner or _default_command_runner

    async def execute(self, action: RecoveryAction) -> tuple[bool, str]:
        return await asyncio.to_thread(self._execute_sync, action)

    def _execute_sync(self, action: RecoveryAction) -> tuple[bool, str]:
        target = action.target
        if action.type in {RecoveryActionType.OPEN_FILE.value, RecoveryActionType.OPEN_WORKSPACE.value}:
            resolved, reason = self._resolve_path_target(target)
            if not resolved:
                return False, reason
            target = resolved

        opener = shutil.which("cmd.exe") or "cmd.exe"
        result = self._runner([opener, "/C", "start", "", target], self._timeout, False)
        if result.returncode == 0:
            return True, ""
        return False, result.stderr or f"open command exited with {result.returncode}"

    def _resolve_path_target(self, target: str) -> tuple[str, str]:
        if not target.startswith("/"):
            return target, ""
        wslpath = shutil.which("wslpath") or "wslpath"
        result = self._runner([wslpath, "-w", target], self._timeout, True)
        if result.returncode != 0:
            return "", result.stderr or f"wslpath exited with {result.returncode}"
        converted = result.stdout.strip()
        if not converted:
            return "", "wslpath returned empty path"
        return converted, ""


class RecoveryExecutionService:
    def __init__(
        self,
        *,
        execution_enabled: bool,
        command_timeout_seconds: float = 2.0,
        planner: RecoveryPlanner | None = None,
        registry: RecoveryExecutorRegistry | None = None,
    ) -> None:
        self._execution_enabled = execution_enabled
        self._planner = planner or RecoveryPlanner()
        self._registry = registry or default_executor_registry(command_timeout_seconds)

    async def restore(self, task_id: int, snapshot: Snapshot | None) -> RecoveryReport:
        if snapshot is None:
            return RecoveryReport.empty(task_id, execution_enabled=self._execution_enabled)

        planned = self._planner.plan(snapshot)
        browser_session = self._planner.browser_session_summary(snapshot)
        if not planned:
            return RecoveryReport(
                task_id=task_id,
                overall_status="empty",
                execution_enabled=self._execution_enabled,
                browser_session=browser_session,
            )

        if not self._execution_enabled:
            actions = [
                action.with_result(RecoveryActionStatus.SKIPPED, "execution_disabled")
                for action in planned
            ]
            return self._report(task_id, actions, browser_session, user_message=None)

        executed: list[RecoveryAction] = []
        for action in planned:
            executor = self._registry.get(action.type)
            if executor is None:
                executed.append(action.with_result(RecoveryActionStatus.UNSUPPORTED, "unsupported_action"))
                continue
            try:
                ok, reason = await executor.execute(action)
            except Exception as exc:
                logger.exception("recovery action failed: %s", action)
                executed.append(action.with_result(RecoveryActionStatus.FAILED, str(exc)))
                continue
            executed.append(
                action.with_result(
                    RecoveryActionStatus.EXECUTED if ok else RecoveryActionStatus.FAILED,
                    "" if ok else reason,
                )
            )

        return self._report(task_id, executed, browser_session, user_message=self._message_for(executed))

    def _report(
        self,
        task_id: int,
        actions: list[RecoveryAction],
        browser_session: dict[str, object],
        *,
        user_message: str | None,
    ) -> RecoveryReport:
        return RecoveryReport(
            task_id=task_id,
            overall_status=self._overall_status(actions),
            execution_enabled=self._execution_enabled,
            actions=actions,
            browser_session=browser_session,
            user_message=user_message,
        )

    @staticmethod
    def _overall_status(actions: list[RecoveryAction]) -> str:
        statuses = {action.status for action in actions}
        if not actions:
            return "empty"
        if statuses == {RecoveryActionStatus.SKIPPED.value}:
            return "skipped"
        if statuses == {RecoveryActionStatus.EXECUTED.value}:
            return "executed"
        if statuses == {RecoveryActionStatus.UNSUPPORTED.value}:
            return "unsupported"
        if statuses == {RecoveryActionStatus.FAILED.value}:
            return "failed"
        return "partial"

    @staticmethod
    def _message_for(actions: list[RecoveryAction]) -> str | None:
        failed = [action for action in actions if action.status == RecoveryActionStatus.FAILED.value]
        unsupported = [action for action in actions if action.status == RecoveryActionStatus.UNSUPPORTED.value]
        if failed:
            return "Could not execute restore actions: " + ", ".join(action.field for action in failed)
        if unsupported:
            return "Some restore actions are not supported yet: " + ", ".join(action.field for action in unsupported)
        return None


def default_executor_registry(command_timeout_seconds: float) -> RecoveryExecutorRegistry:
    registry = RecoveryExecutorRegistry()
    opener = WindowsDefaultOpenExecutor(timeout_seconds=command_timeout_seconds)
    registry.register(RecoveryActionType.OPEN_URL, opener)
    registry.register(RecoveryActionType.OPEN_FILE, opener)
    registry.register(RecoveryActionType.OPEN_WORKSPACE, opener)
    return registry


def _default_command_runner(cmd: list[str], timeout: float, capture_output: bool) -> CommandResult:
    completed = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture_output else subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
