from __future__ import annotations

from typing import Any, Callable

from flow_hud.adapters.ipc_messages import TaskStateChangedIpcPayload, TimerTickPayload
from flow_hud.core.events_payload import IpcMessageReceivedPayload

from .models import TaskStatusSnapshot

StatusRequester = Callable[[], dict[str, Any]]
SnapshotPublisher = Callable[[TaskStatusSnapshot], None]


class TaskStatusController:
    """Normalize backend status and push payloads into a UI-safe snapshot."""

    def __init__(
        self,
        *,
        request_status: StatusRequester,
        publish_snapshot: SnapshotPublisher,
    ) -> None:
        self._request_status = request_status
        self._publish_snapshot = publish_snapshot
        self._snapshot = TaskStatusSnapshot.offline()

    @property
    def snapshot(self) -> TaskStatusSnapshot:
        return self._snapshot

    def bootstrap(self) -> TaskStatusSnapshot:
        snapshot = self._refresh_snapshot()
        self._set_snapshot(snapshot)
        return snapshot

    def handle_ipc_payload(self, payload: object) -> TaskStatusSnapshot | None:
        snapshot: TaskStatusSnapshot | None = None

        if isinstance(payload, TaskStateChangedIpcPayload):
            snapshot = self._refresh_snapshot()
        elif isinstance(payload, TimerTickPayload):
            snapshot = self._snapshot_from_timer_tick(payload)
        elif isinstance(payload, IpcMessageReceivedPayload):
            snapshot = self._snapshot_from_raw_ipc(payload)

        if snapshot is not None:
            self._set_snapshot(snapshot)
        return snapshot

    def handle_connection_established(self) -> TaskStatusSnapshot:
        snapshot = self._refresh_snapshot()
        self._set_snapshot(snapshot)
        return snapshot

    def handle_connection_lost(self) -> TaskStatusSnapshot:
        snapshot = TaskStatusSnapshot.offline()
        self._set_snapshot(snapshot)
        return snapshot

    def _set_snapshot(self, snapshot: TaskStatusSnapshot) -> None:
        self._snapshot = snapshot
        self._publish_snapshot(snapshot)

    def _refresh_snapshot(self) -> TaskStatusSnapshot:
        try:
            response = self._request_status()
        except Exception:
            return TaskStatusSnapshot.offline()
        return self._normalize_status_response(response)

    def _normalize_status_response(self, response: dict[str, Any]) -> TaskStatusSnapshot:
        if not isinstance(response, dict) or response.get("ok") is not True:
            return TaskStatusSnapshot.offline()

        result = response.get("result")
        if not isinstance(result, dict):
            return TaskStatusSnapshot.offline()

        if "active" not in result:
            return TaskStatusSnapshot.offline()

        active = result["active"]
        if active is None:
            return TaskStatusSnapshot.empty()
        if not isinstance(active, dict):
            return TaskStatusSnapshot.offline()

        title = active.get("title")
        state_label = active.get("state")
        if not isinstance(title, str) or not title.strip():
            return TaskStatusSnapshot.offline()
        if not isinstance(state_label, str) or not state_label.strip():
            return TaskStatusSnapshot.offline()

        duration_min = self._coerce_optional_int(active.get("duration_min"))
        task_id = self._coerce_optional_int(active.get("id"))
        break_suggested = bool(result.get("break_suggested", False))

        return TaskStatusSnapshot.active(
            task_id=task_id,
            title=title,
            state_label=state_label,
            duration_min=duration_min,
            break_suggested=break_suggested,
        )

    def _snapshot_from_timer_tick(self, payload: TimerTickPayload) -> TaskStatusSnapshot | None:
        current = self._snapshot
        if current.mode.value != "active":
            return None
        if payload.task_id is not None and current.task_id is not None and payload.task_id != current.task_id:
            return None

        elapsed_min = max(0, payload.tick // 60)
        next_duration = max(current.duration_min or 0, elapsed_min)
        if current.duration_min == next_duration:
            return None
        return current.with_duration(next_duration)

    def _snapshot_from_raw_ipc(self, payload: IpcMessageReceivedPayload) -> TaskStatusSnapshot | None:
        if payload.method == "task.state_changed":
            return self._refresh_snapshot()
        if payload.method != "timer.tick":
            return None

        data = payload.data if isinstance(payload.data, dict) else {}
        raw_tick = data.get("tick", data.get("elapsed"))
        try:
            tick = int(raw_tick)
        except (TypeError, ValueError):
            return None

        return self._snapshot_from_timer_tick(
            TimerTickPayload(
                tick=tick,
                task_id=self._coerce_optional_int(data.get("task_id")),
            )
        )

    @staticmethod
    def _coerce_optional_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
