from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import os
import sys
import pytest

pytest.importorskip("PySide6")

from flow_hud.core.events import HudEventType
from flow_hud.core.events_payload import IpcConnectionStatusPayload, IpcMessageReceivedPayload
from flow_hud.task_status.models import TaskStatusMode, TaskStatusSnapshot, TaskStatusUpdatedPayload
from flow_hud.task_status.plugin import TaskStatusPlugin
from flow_hud.task_status.widget import TaskStatusWidget
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


class _RecordingEventBus:
    def __init__(self, subscriptions: dict[HudEventType, list], *, dispatch_immediately: bool) -> None:
        self._subscriptions = subscriptions
        self._dispatch_immediately = dispatch_immediately
        self.emitted: list[tuple[HudEventType, object]] = []

    def emit(self, event_type: HudEventType, payload: object) -> None:
        self.emitted.append((event_type, payload))
        if not self._dispatch_immediately:
            return
        for handler in list(self._subscriptions.get(event_type, [])):
            handler(SimpleNamespace(payload=payload))

    def subscribe(self, event_type: HudEventType, handler) -> None:
        self._subscriptions.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: HudEventType, handler) -> None:
        handlers = self._subscriptions.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit_background(self, event_type: HudEventType, payload: object) -> None:
        self.emit(event_type, payload)


class _FakeContext:
    def __init__(self, status_response: dict[str, Any], *, dispatch_immediately: bool) -> None:
        self.owner = "task-status"
        self._status_response = status_response
        self.subscriptions: dict[HudEventType, list] = {}
        self.widgets: dict[str, object] = {}
        self.event_bus = _RecordingEventBus(self.subscriptions, dispatch_immediately=dispatch_immediately)

    def subscribe_event(self, event_type, handler) -> None:
        self.subscriptions.setdefault(event_type, []).append(handler)

    def register_widget(self, name: str, widget: object, *, slot: str = "center") -> dict[str, Any]:
        self.widgets[name] = widget
        return {"name": name, "slot": slot, "registered": True, "mounted": False}

    async def request_ipc(self, method: str, **params: Any) -> dict[str, Any]:
        assert method == "status"
        assert params == {}
        return self._status_response


def _active_status(*, duration_min: int = 1, break_suggested: bool = False) -> dict[str, Any]:
    return {
        "ok": True,
        "result": {
            "active": {
                "id": 7,
                "title": "deep work",
                "state": "In Progress",
                "duration_min": duration_min,
            },
            "break_suggested": break_suggested,
        },
        "error_code": None,
        "message": None,
    }


def test_background_ipc_path_only_emits_foreground_update_before_widget_mutation() -> None:
    ctx = _FakeContext(_active_status(duration_min=1), dispatch_immediately=False)
    plugin = TaskStatusPlugin()
    plugin.setup(ctx)

    widget = ctx.widgets["task-status"]
    widget.render_snapshot = MagicMock(wraps=widget.render_snapshot)
    ctx.event_bus.emitted.clear()

    bg_handler = ctx.subscriptions[HudEventType.IPC_MESSAGE_RECEIVED][0]
    fg_handler = ctx.subscriptions[HudEventType.TASK_STATUS_UPDATED][0]

    bg_handler(
        SimpleNamespace(payload=IpcMessageReceivedPayload(method="timer.tick", data={"tick": 120, "task_id": 7}))
    )

    assert widget.render_snapshot.call_count == 0
    assert len(ctx.event_bus.emitted) == 1
    event_type, payload = ctx.event_bus.emitted[0]
    assert event_type == HudEventType.TASK_STATUS_UPDATED
    assert isinstance(payload, TaskStatusUpdatedPayload)

    fg_handler(SimpleNamespace(payload=payload))

    assert widget.render_snapshot.call_count == 1
    assert widget.snapshot.duration_min == 2


def test_widget_renders_empty_and_break_suggestion_states() -> None:
    widget = TaskStatusWidget()

    widget.render_snapshot(TaskStatusSnapshot.empty())
    assert widget.findChild(type(widget._state_label), "task-status-state").text() == "No active task"
    assert widget.findChild(type(widget._badge_label), "task-status-badge").isHidden()

    widget.render_snapshot(
        TaskStatusSnapshot.active(
            task_id=7,
            title="deep work",
            state_label="In Progress",
            duration_min=26,
            break_suggested=True,
        )
    )
    assert widget.findChild(type(widget._title_label), "task-status-title").text() == "deep work"
    assert widget.findChild(type(widget._meta_label), "task-status-meta").text() == "26 min focus"
    assert widget.findChild(type(widget._badge_label), "task-status-badge").text() == "Break suggested"
    assert not widget.findChild(type(widget._badge_label), "task-status-badge").isHidden()


def test_connection_established_event_refreshes_widget_after_offline_start() -> None:
    responses = iter(
        [
            {
                "ok": False,
                "result": None,
                "error_code": "ERR_DAEMON_OFFLINE",
                "message": "offline",
            },
            _active_status(duration_min=8, break_suggested=False),
        ]
    )

    class _SequentialContext(_FakeContext):
        async def request_ipc(self, method: str, **params: Any) -> dict[str, Any]:
            assert method == "status"
            return next(responses)

    ctx = _SequentialContext(_active_status(), dispatch_immediately=True)
    plugin = TaskStatusPlugin()
    plugin.setup(ctx)

    widget = ctx.widgets["task-status"]
    assert widget.snapshot.state_label == "Backend offline"

    connection_handler = ctx.subscriptions[HudEventType.IPC_CONNECTION_ESTABLISHED][0]
    connection_handler(SimpleNamespace(payload=IpcConnectionStatusPayload(connected=True)))

    assert widget.snapshot.mode == TaskStatusMode.ACTIVE
    assert widget.snapshot.duration_min == 8


def test_connection_lost_event_degrades_active_widget_to_offline() -> None:
    ctx = _FakeContext(_active_status(duration_min=4), dispatch_immediately=True)
    plugin = TaskStatusPlugin()
    plugin.setup(ctx)

    widget = ctx.widgets["task-status"]
    assert widget.snapshot.mode == TaskStatusMode.ACTIVE

    lost_handler = ctx.subscriptions[HudEventType.IPC_CONNECTION_LOST][0]
    lost_handler(SimpleNamespace(payload=IpcConnectionStatusPayload(connected=False)))

    assert widget.snapshot.mode == TaskStatusMode.OFFLINE
    assert widget.snapshot.state_label == "Backend offline"
