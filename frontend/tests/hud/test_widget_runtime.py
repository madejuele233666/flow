import os
import sys
import threading

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QLabel

from flow_hud.adapters.ui_canvas import HudCanvas
from flow_hud.core.app import HudApp
from flow_hud.core.config import HudConfig
from flow_hud.core.service import HudLocalService
from flow_hud.runtime import _wire_canvas_runtime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def hud_app():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    yield app
    app.shutdown()


def _drain_qt_events() -> None:
    app = QApplication.instance()
    assert app is not None
    app.processEvents()


def test_slot_rewrite_hook_affects_final_widget_slot(hud_app):
    class RewriteHook:
        def before_widget_register(self, payload):
            payload.slot = "center"

    hud_app.register_hook(RewriteHook(), owner="policy")

    result = hud_app.register_widget(
        name="timer",
        slot="top_right",
        widget=QLabel("timer"),
        owner="plugin-a",
        source="plugin",
    )

    assert result["slot"] == "center"
    mount = hud_app.get_widget_mount("timer")
    assert mount is not None
    _, slot = mount
    assert slot == "center"


def test_plugin_registration_does_not_claim_mounted_before_runtime_mount(hud_app):
    result = hud_app.register_widget(
        name="timer",
        slot="top_right",
        widget=QLabel("timer"),
        owner="plugin-a",
        source="plugin",
    )
    assert result["registered"] is True
    assert result["mounted"] is False


def test_invalid_slot_rejected(hud_app):
    with pytest.raises(ValueError, match="invalid widget slot"):
        hud_app.register_widget(
            name="timer",
            slot="invalid-slot",
            widget=QLabel("timer"),
            owner="plugin-a",
            source="plugin",
        )


def test_non_qwidget_plugin_widget_rejected(hud_app):
    with pytest.raises(ValueError, match="QWidget"):
        hud_app.register_widget(
            name="timer",
            slot="center",
            widget=object(),
            owner="plugin-a",
            source="plugin",
        )


def test_invalid_widget_registration_source_rejected(hud_app):
    with pytest.raises(ValueError, match="invalid widget registration source"):
        hud_app.register_widget(
            name="timer",
            slot="center",
            widget=None,
            owner=None,
            source="bogus",
        )


def test_service_source_rejects_widget_instance_and_owner(hud_app):
    with pytest.raises(ValueError, match="cannot include widget instance"):
        hud_app.register_widget(
            name="timer",
            slot="center",
            widget=QLabel("timer"),
            owner=None,
            source="service",
        )
    with pytest.raises(ValueError, match="cannot include owner"):
        hud_app.register_widget(
            name="timer",
            slot="center",
            widget=None,
            owner="plugin-a",
            source="service",
        )


def test_rejected_widget_registration_does_not_run_before_hook(hud_app):
    calls = []

    class Hook:
        def before_widget_register(self, payload):
            calls.append((payload.name, payload.slot))

    hud_app.register_hook(Hook(), owner="guard")

    with pytest.raises(ValueError, match="requires owner"):
        hud_app.register_widget(
            name="timer",
            slot="center",
            widget=QLabel("timer"),
            owner=None,
            source="plugin",
        )

    assert calls == []


def test_duplicate_name_replaces_previous_registration(hud_app):
    first = QLabel("first")
    second = QLabel("second")

    hud_app.register_widget("timer", "top_right", widget=first, owner="plugin-a", source="plugin")
    hud_app.register_widget("timer", "bottom_right", widget=second, owner="plugin-a", source="plugin")

    mount = hud_app.get_widget_mount("timer")
    assert mount is not None
    mounted_widget, mounted_slot = mount
    assert mounted_widget is second
    assert mounted_slot == "bottom_right"


def test_dynamic_registration_is_mounted_by_canvas_event_pipeline(hud_app):
    canvas = HudCanvas()
    _wire_canvas_runtime(hud_app, canvas)

    widget = QLabel("clock")
    hud_app.register_widget("clock", "top_right", widget=widget, owner="plugin-a", source="plugin")
    _drain_qt_events()

    assert canvas.mounted_slots()["clock"] == "top_right"


def test_same_qwidget_reregistration_moves_slot_without_delete(hud_app):
    canvas = HudCanvas()
    _wire_canvas_runtime(hud_app, canvas)

    widget = QLabel("clock")
    hud_app.register_widget("clock", "top_right", widget=widget, owner="plugin-a", source="plugin")
    _drain_qt_events()
    assert canvas.mounted_slots()["clock"] == "top_right"

    hud_app.register_widget("clock", "center", widget=widget, owner="plugin-a", source="plugin")
    _drain_qt_events()
    app = QApplication.instance()
    assert app is not None
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

    assert canvas.mounted_slots()["clock"] == "center"
    assert widget.text() == "clock"


def test_service_reservation_reports_mounted_false(hud_app):
    service = HudLocalService(hud_app)

    result = service.register_widget("ghost-reservation", "center")

    assert result == {
        "name": "ghost-reservation",
        "slot": "center",
        "reserved": True,
        "mounted": False,
    }


def test_service_reservation_overwrites_live_widget_and_unmounts_canvas(hud_app):
    canvas = HudCanvas()
    _wire_canvas_runtime(hud_app, canvas)

    widget = QLabel("clock")
    hud_app.register_widget("clock", "top_right", widget=widget, owner="plugin-a", source="plugin")
    _drain_qt_events()
    assert "clock" in canvas.mounted_names()

    service = HudLocalService(hud_app)
    service.register_widget("clock", "center")
    _drain_qt_events()

    assert "clock" not in canvas.mounted_names()


def test_unregistered_event_unmounts_canvas(hud_app):
    canvas = HudCanvas()
    _wire_canvas_runtime(hud_app, canvas)

    widget = QLabel("clock")
    hud_app.register_widget("clock", "top_right", widget=widget, owner="plugin-a", source="plugin")
    _drain_qt_events()
    assert "clock" in canvas.mounted_names()

    hud_app.unregister_widget("clock")
    _drain_qt_events()

    assert "clock" not in canvas.mounted_names()


def test_shutdown_unmounts_canvas_without_manual_event_drain(hud_app):
    canvas = HudCanvas()
    _wire_canvas_runtime(hud_app, canvas)

    widget = QLabel("clock")
    hud_app.register_widget("clock", "top_right", widget=widget, owner="plugin-a", source="plugin")
    _drain_qt_events()
    assert "clock" in canvas.mounted_names()

    hud_app.shutdown()

    assert "clock" not in canvas.mounted_names()


def test_register_widget_rejects_non_runtime_thread_call(hud_app):
    caught: list[Exception] = []

    def _worker() -> None:
        try:
            hud_app.register_widget(
                name="timer",
                slot="center",
                widget=object(),
                owner="plugin-a",
                source="plugin",
            )
        except Exception as exc:  # pragma: no cover - assertion below validates type/message
            caught.append(exc)

    thread = threading.Thread(target=_worker, name="widget-worker")
    thread.start()
    thread.join()

    assert len(caught) == 1
    assert isinstance(caught[0], ValueError)
    assert str(caught[0]) == "register_widget must run on HUD runtime thread"
    assert hud_app.get_widget_mount("timer") is None
