"""Shared task-flow runtime for local and daemon adapters."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from flow_engine.context.policy import CaptureRestorePolicy, CaptureTrigger
from flow_engine.context.recovery import RESTORE_PRIORITY, RecoveryPriority, RestoreResult
from flow_engine.notifications.base import NotifyLevel
from flow_engine.state.machine import TaskState

if TYPE_CHECKING:
    from flow_engine.app import FlowApp
    from flow_engine.context.base_plugin import Snapshot
    from flow_engine.storage.task_model import Task

logger = logging.getLogger(__name__)

_StartCallback = Callable[[int], Awaitable[None] | None]
_StopCallback = Callable[[], Awaitable[None] | None]


class TaskFlowRuntime:
    """Canonical task-flow orchestration shared by local and daemon adapters."""

    def __init__(
        self,
        app: FlowApp,
        *,
        on_task_started: _StartCallback | None = None,
        on_task_stopped: _StopCallback | None = None,
        policy: CaptureRestorePolicy | None = None,
    ) -> None:
        self._app = app
        self._on_task_started = on_task_started
        self._on_task_stopped = on_task_stopped
        self._policy = policy or CaptureRestorePolicy()
        self._lock = asyncio.Lock()

    async def add_task(
        self,
        title: str,
        priority: int = 2,
        ddl: str | None = None,
        tags: list[str] | None = None,
        template_name: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            app = self._app
            parsed_ddl = datetime.strptime(ddl, "%Y-%m-%d") if ddl else None

            if template_name:
                tmpl = app.templates.get(template_name)
                if tmpl is None:
                    raise ValueError(f"未找到模板: {template_name}")

                base_id = await app.repo.next_id()
                output = tmpl.create(
                    base_id=base_id,
                    title=title,
                    priority=priority,
                    ddl=parsed_ddl,
                )
                tasks = await app.repo.load_all()
                tasks.extend(output.tasks)
                await app.repo.save_all(tasks)
                await self._emit_task_created(*(task.id for task in output.tasks))
                await self._auto_commit(f"{app.config.git.commit_prefix} add template:{template_name}")
                return {
                    "template": template_name,
                    "tasks": [self._task_created_payload(task) for task in output.tasks],
                }

            from flow_engine.storage.task_model import Task

            task = Task(
                id=await app.repo.next_id(),
                title=title,
                priority=priority,
                ddl=parsed_ddl,
                tags=list(tags or []),
            )
            tasks = await app.repo.load_all()
            tasks.append(task)
            await app.repo.save_all(tasks)
            await self._emit_task_created(task.id)
            await self._auto_commit(f"{app.config.git.commit_prefix} add #{task.id} {task.title}")
            return self._task_created_payload(task)

    async def start_task(self, task_id: int) -> dict[str, Any]:
        async with self._lock:
            tasks = await self._app.repo.load_all()
            task = self._find(tasks, task_id)
            start_target = await self._app.engine.prepare_transition(task, TaskState.IN_PROGRESS)

            auto_paused = await self._app.engine.ensure_single_active(tasks, task_id)
            await self._capture_many(auto_paused, CaptureTrigger.AUTO_PAUSE)
            await self._app.engine.commit_transition(task, start_target)
            task.started_at = datetime.now()
            await self._app.repo.save_all(tasks)
            await self._auto_commit_state(task)

            restore_result = await self._restore_context(task.id, CaptureTrigger.START)
        await self._invoke_started(task.id)
        return {
            **self._task_state_payload(task),
            "paused": [paused.id for paused in auto_paused],
            "restored_window": restore_result.restored.get("active_window"),
            "restore_report": restore_result.to_dict(),
        }

    async def done_task(self) -> dict[str, Any]:
        async with self._lock:
            tasks = await self._app.repo.load_all()
            active = self._require_single_active(tasks)
            done_target = await self._app.engine.prepare_transition(active, TaskState.DONE)

            await self._capture_one(active, CaptureTrigger.DONE)
            await self._app.engine.commit_transition(active, done_target)
            await self._app.repo.save_all(tasks)
            await self._auto_commit_state(active)
        await self._invoke_stopped()
        return self._task_state_payload(active)

    async def pause_task(self) -> dict[str, Any]:
        async with self._lock:
            tasks = await self._app.repo.load_all()
            active = self._require_single_active(tasks)
            pause_target = await self._app.engine.prepare_transition(active, TaskState.PAUSED)

            await self._capture_one(active, CaptureTrigger.PAUSE)
            await self._app.engine.commit_transition(active, pause_target)
            await self._app.repo.save_all(tasks)
            await self._auto_commit_state(active)
        await self._invoke_stopped()
        return self._task_state_payload(active)

    async def resume_task(self, task_id: int) -> dict[str, Any]:
        async with self._lock:
            tasks = await self._app.repo.load_all()
            task = self._find(tasks, task_id)

            if task.state not in (TaskState.PAUSED, TaskState.BLOCKED):
                raise ValueError(f"任务 #{task_id} 当前状态为 {task.state.value}，无法恢复")

            resume_target = TaskState.IN_PROGRESS
            unblock_target: TaskState | None = None
            if task.state == TaskState.BLOCKED:
                shadow = self._clone_task(task)
                unblock_target = await self._app.engine.prepare_transition(shadow, TaskState.READY)
                shadow.state = unblock_target
                shadow.block_reason = ""
                resume_target = await self._app.engine.prepare_transition(shadow, TaskState.IN_PROGRESS)
            else:
                resume_target = await self._app.engine.prepare_transition(task, TaskState.IN_PROGRESS)

            auto_paused = await self._app.engine.ensure_single_active(tasks, task_id)
            await self._capture_many(auto_paused, CaptureTrigger.AUTO_PAUSE)

            if unblock_target is not None:
                await self._app.engine.commit_transition(task, unblock_target)
                task.block_reason = ""

            await self._app.engine.commit_transition(task, resume_target)
            task.started_at = datetime.now()
            await self._app.repo.save_all(tasks)
            await self._auto_commit_state(task)

            await self._restore_context(task.id, CaptureTrigger.RESUME)
        await self._invoke_started(task.id)
        return self._task_state_payload(task)

    async def block_task(self, task_id: int, reason: str = "") -> dict[str, Any]:
        async with self._lock:
            tasks = await self._app.repo.load_all()
            task = self._find(tasks, task_id)
            block_target = await self._app.engine.prepare_transition(task, TaskState.BLOCKED)

            await self._capture_one(task, CaptureTrigger.BLOCK)
            await self._app.engine.commit_transition(task, block_target)
            task.block_reason = reason
            await self._app.repo.save_all(tasks)
            await self._auto_commit_state(task)
        await self._invoke_stopped()
        return {
            **self._task_state_payload(task),
            "reason": reason,
        }

    async def get_status(self) -> dict[str, Any]:
        async with self._lock:
            tasks = await self._app.repo.load_all()
            active_tasks = [task for task in tasks if task.state == TaskState.IN_PROGRESS]
            if not active_tasks:
                return {"active": None, "break_suggested": False}
            if len(active_tasks) > 1:
                raise ValueError("存在多个进行中的任务，无法确定当前活跃任务")

            active = active_tasks[0]
            duration_min = self._duration_minutes(active)
            return {
                "active": {
                    "id": active.id,
                    "title": active.title,
                    "priority": active.priority,
                    "state": active.state.value,
                    "duration_min": duration_min,
                },
                "break_suggested": self._is_break_suggested(active),
            }

    def _find(self, tasks: list[Task], task_id: int) -> Task:
        task = next((item for item in tasks if item.id == task_id), None)
        if task is None:
            raise ValueError(f"未找到任务 #{task_id}")
        return task

    def _require_single_active(self, tasks: list[Task]) -> Task:
        active_tasks = [task for task in tasks if task.state == TaskState.IN_PROGRESS]
        if not active_tasks:
            raise ValueError("当前没有进行中的任务")
        if len(active_tasks) > 1:
            raise ValueError("存在多个进行中的任务，无法确定当前活跃任务")
        return active_tasks[0]

    def _clone_task(self, task: Task) -> Task:
        from dataclasses import replace

        return replace(task)

    def _task_created_payload(self, task: Task) -> dict[str, Any]:
        return {
            "id": task.id,
            "title": task.title,
            "priority": task.priority,
            "state": task.state.value,
        }

    def _task_state_payload(self, task: Task) -> dict[str, Any]:
        return {
            "id": task.id,
            "title": task.title,
            "state": task.state.value,
        }

    def _duration_minutes(self, task: Task) -> int | None:
        if task.started_at is None:
            return None
        delta = datetime.now() - task.started_at
        return int(delta.total_seconds() // 60)

    def _is_break_suggested(self, task: Task) -> bool:
        if task.started_at is None:
            return False
        elapsed = (datetime.now() - task.started_at).total_seconds() / 60
        return elapsed >= self._app.config.focus.break_interval_minutes

    async def _capture_many(self, tasks: list[Task], trigger: CaptureTrigger) -> None:
        if not tasks:
            return
        for task in tasks:
            await self._capture_one(task, trigger)

    async def _capture_one(self, task: Task, trigger: CaptureTrigger) -> Snapshot | None:
        context = getattr(self._app, "context", None)
        if (
            context is None
            or not self._app.config.context.capture_on_switch
            or not self._policy.should_capture(trigger, current_state=task.state)
        ):
            return None
        try:
            return await context.capture_async(task.id, capture_trigger=trigger.value)
        except Exception:
            logger.exception("context capture failed for task #%s", task.id)
            return None

    async def _restore_context(self, task_id: int, trigger: CaptureTrigger) -> RestoreResult:
        context = getattr(self._app, "context", None)
        if (
            context is None
            or not self._app.config.context.capture_on_switch
            or not self._policy.should_restore(trigger)
        ):
            return RestoreResult.empty(task_id)
        try:
            snapshot = await asyncio.to_thread(context.restore_latest, task_id)
        except Exception:
            logger.warning("context restore failed for task #%s", task_id, exc_info=True)
            return RestoreResult.empty(task_id)
        if snapshot is None:
            return RestoreResult.empty(task_id)

        result = RestoreResult(task_id=task_id)
        recoverable_present = False
        display_only_present = False
        failed_hints = self._restore_field_hints(snapshot, "restore_failed_fields")
        degraded_hints = self._restore_field_hints(snapshot, "restore_degraded_fields")

        for field_name, priority in RESTORE_PRIORITY.items():
            value = getattr(snapshot, field_name, None)
            if not self._has_context_value(value):
                continue

            if priority in (RecoveryPriority.MUST_RESTORE, RecoveryPriority.BEST_EFFORT):
                recoverable_present = True
            elif priority == RecoveryPriority.DISPLAY_ONLY:
                display_only_present = True

            if field_name in failed_hints and priority == RecoveryPriority.MUST_RESTORE:
                result.failed.append(field_name)
                continue
            if field_name in degraded_hints and priority == RecoveryPriority.BEST_EFFORT:
                result.degraded.append(field_name)
                continue

            result.restored[field_name] = value

        if not recoverable_present and not display_only_present:
            return result

        if not recoverable_present and display_only_present:
            result.user_message = "No recoverable context is available; only recorded metadata was found."
            self._notify_restore_result(result, NotifyLevel.INFO)
            return result

        if result.failed:
            result.user_message = (
                "Could not fully restore context: "
                + ", ".join(sorted(result.failed))
            )
            self._notify_restore_result(result, NotifyLevel.WARNING)
            return result

        return result

    @staticmethod
    def _has_context_value(value: Any) -> bool:
        if isinstance(value, list):
            return bool(value)
        return bool(value)

    @staticmethod
    def _restore_field_hints(snapshot: Snapshot, key: str) -> set[str]:
        raw = snapshot.extra.get(key, [])
        if isinstance(raw, list):
            values = raw
        elif raw in (None, ""):
            values = []
        else:
            values = [raw]
        return {str(item) for item in values if str(item)}

    def _notify_restore_result(self, result: RestoreResult, level: NotifyLevel) -> None:
        if result.user_message is None:
            return
        try:
            self._app.notifications.notify(
                title="上下文恢复",
                body=result.user_message,
                level=level,
                extra={"restore_report": result.to_dict()},
            )
        except Exception:
            logger.exception("restore notification failed for task #%s", result.task_id)

    async def _auto_commit(self, message: str) -> None:
        if not self._app.config.git.auto_commit:
            return
        await asyncio.to_thread(self._app.vcs.commit, message)

    async def _auto_commit_state(self, task: Task) -> None:
        await self._auto_commit(f"{self._app.config.git.commit_prefix} task #{task.id} → {task.state.value}")

    async def _emit_task_created(self, *task_ids: int) -> None:
        from flow_engine.events import EventType
        from flow_engine.events_payload import TaskCreatedPayload

        for task_id in task_ids:
            await self._app.bus.emit(EventType.TASK_CREATED, TaskCreatedPayload(task_id=task_id))

    async def _invoke_started(self, task_id: int) -> None:
        await self._invoke_callback(self._on_task_started, task_id)

    async def _invoke_stopped(self) -> None:
        await self._invoke_callback(self._on_task_stopped)

    async def _invoke_callback(self, callback: Callable[..., Any] | None, *args: Any) -> None:
        if callback is None:
            return
        result = callback(*args)
        if inspect.isawaitable(result):
            await result
