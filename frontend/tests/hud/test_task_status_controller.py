from __future__ import annotations

from flow_hud.adapters.ipc_messages import TimerTickPayload
from flow_hud.core.events_payload import IpcMessageReceivedPayload
from flow_hud.task_status.controller import TaskStatusController
from flow_hud.task_status.models import TaskStatusMode


def _active_status(*, duration_min: int = 12, break_suggested: bool = True) -> dict:
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


def test_bootstrap_produces_active_snapshot() -> None:
    emitted = []
    controller = TaskStatusController(
        request_status=lambda: _active_status(),
        publish_snapshot=emitted.append,
    )

    snapshot = controller.bootstrap()

    assert snapshot.mode == TaskStatusMode.ACTIVE
    assert snapshot.title == "deep work"
    assert snapshot.state_label == "In Progress"
    assert snapshot.duration_min == 12
    assert snapshot.break_suggested is True
    assert emitted == [snapshot]


def test_bootstrap_degrades_to_offline_when_daemon_unreachable() -> None:
    emitted = []
    controller = TaskStatusController(
        request_status=lambda: {
            "ok": False,
            "result": None,
            "error_code": "ERR_DAEMON_OFFLINE",
            "message": "offline",
        },
        publish_snapshot=emitted.append,
    )

    snapshot = controller.bootstrap()

    assert snapshot.mode == TaskStatusMode.OFFLINE
    assert emitted == [snapshot]


def test_bootstrap_produces_empty_snapshot_when_no_active_task() -> None:
    emitted = []
    controller = TaskStatusController(
        request_status=lambda: {
            "ok": True,
            "result": {"active": None, "break_suggested": False},
            "error_code": None,
            "message": None,
        },
        publish_snapshot=emitted.append,
    )

    snapshot = controller.bootstrap()

    assert snapshot.mode == TaskStatusMode.EMPTY
    assert snapshot.state_label == "No active task"
    assert emitted == [snapshot]


def test_missing_active_field_degrades_to_offline_snapshot() -> None:
    emitted = []
    controller = TaskStatusController(
        request_status=lambda: {
            "ok": True,
            "result": {"break_suggested": False},
            "error_code": None,
            "message": None,
        },
        publish_snapshot=emitted.append,
    )

    snapshot = controller.bootstrap()

    assert snapshot.mode == TaskStatusMode.OFFLINE
    assert emitted == [snapshot]


def test_incomplete_active_payload_degrades_to_offline_snapshot() -> None:
    emitted = []
    controller = TaskStatusController(
        request_status=lambda: {
            "ok": True,
            "result": {
                "active": {
                    "id": 7,
                    "title": "deep work",
                },
                "break_suggested": False,
            },
            "error_code": None,
            "message": None,
        },
        publish_snapshot=emitted.append,
    )

    snapshot = controller.bootstrap()

    assert snapshot.mode == TaskStatusMode.OFFLINE
    assert emitted == [snapshot]


def test_timer_tick_updates_duration_without_reaching_into_transport_shape() -> None:
    emitted = []
    controller = TaskStatusController(
        request_status=lambda: _active_status(duration_min=1, break_suggested=False),
        publish_snapshot=emitted.append,
    )
    controller.bootstrap()
    emitted.clear()

    snapshot = controller.handle_ipc_payload(TimerTickPayload(tick=125, task_id=7))

    assert snapshot is not None
    assert snapshot.duration_min == 2
    assert emitted == [snapshot]


def test_malformed_timer_payload_is_ignored_safely() -> None:
    emitted = []
    controller = TaskStatusController(
        request_status=lambda: _active_status(duration_min=3, break_suggested=False),
        publish_snapshot=emitted.append,
    )
    controller.bootstrap()
    baseline = emitted[-1]
    emitted.clear()

    snapshot = controller.handle_ipc_payload(
        IpcMessageReceivedPayload(method="timer.tick", data={"tick": "bad"})
    )

    assert snapshot is None
    assert emitted == []
    assert controller.snapshot == baseline


def test_request_exceptions_degrade_to_offline_snapshot() -> None:
    emitted = []

    def _boom() -> dict:
        raise RuntimeError("transport blew up")

    controller = TaskStatusController(
        request_status=_boom,
        publish_snapshot=emitted.append,
    )

    snapshot = controller.bootstrap()

    assert snapshot.mode == TaskStatusMode.OFFLINE
    assert emitted == [snapshot]


def test_connection_recovery_refreshes_to_active_snapshot() -> None:
    emitted = []
    responses = iter(
        [
            {
                "ok": False,
                "result": None,
                "error_code": "ERR_DAEMON_OFFLINE",
                "message": "offline",
            },
            _active_status(duration_min=9, break_suggested=False),
        ]
    )
    controller = TaskStatusController(
        request_status=lambda: next(responses),
        publish_snapshot=emitted.append,
    )

    first = controller.bootstrap()
    recovered = controller.handle_connection_established()

    assert first.mode == TaskStatusMode.OFFLINE
    assert recovered.mode == TaskStatusMode.ACTIVE
    assert recovered.duration_min == 9
    assert emitted == [first, recovered]


def test_connection_recovery_refreshes_to_empty_snapshot() -> None:
    emitted = []
    responses = iter(
        [
            {
                "ok": False,
                "result": None,
                "error_code": "ERR_DAEMON_OFFLINE",
                "message": "offline",
            },
            {
                "ok": True,
                "result": {"active": None, "break_suggested": False},
                "error_code": None,
                "message": None,
            },
        ]
    )
    controller = TaskStatusController(
        request_status=lambda: next(responses),
        publish_snapshot=emitted.append,
    )

    first = controller.bootstrap()
    recovered = controller.handle_connection_established()

    assert first.mode == TaskStatusMode.OFFLINE
    assert recovered.mode == TaskStatusMode.EMPTY
    assert emitted == [first, recovered]
