import os
import sys
import threading

import pytest
from PySide6.QtWidgets import QApplication

from flow_hud.core.app import HudApp
from flow_hud.core.config import HudConfig
from flow_hud.core.events import HudEventType
from flow_hud.core.service import HudLocalService

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


def test_veto_blocks_transition_and_no_transitioned_event(hud_app):
    service = HudLocalService(hud_app)
    events = []

    class VetoHook:
        def before_state_transition(self, payload):
            return False

    hud_app.register_hook(VetoHook(), owner="veto")
    hud_app.event_bus.subscribe(HudEventType.STATE_TRANSITIONED, lambda event: events.append(event))

    with pytest.raises(ValueError, match="vetoed"):
        service.transition_to("pulse")

    _drain_qt_events()
    assert hud_app.current_state_value() == "ghost"
    assert events == []


def test_successful_transition_emits_after_event_once(hud_app):
    service = HudLocalService(hud_app)
    events = []

    hud_app.event_bus.subscribe(HudEventType.STATE_TRANSITIONED, lambda event: events.append(event))

    result = service.transition_to("pulse")
    _drain_qt_events()

    assert result == {"old_state": "ghost", "new_state": "pulse"}
    assert len(events) == 1
    payload = events[0].payload
    assert payload.old_state == "ghost"
    assert payload.new_state == "pulse"


def test_after_transition_hook_runs_before_shutdown_without_event_drain(hud_app):
    calls = []

    class AfterHook:
        def on_after_state_transition(self, payload):
            calls.append((payload.old_state, payload.new_state))

    hud_app.register_hook(AfterHook(), owner="after")
    hud_app.transition_to("pulse")
    hud_app.shutdown()

    assert calls == [("ghost", "pulse")]


def test_admin_context_has_canonical_transition_api_without_state_machine_escape(hud_app):
    admin_ctx = hud_app._admin_context_for_owner("admin")

    assert not hasattr(admin_ctx, "state_machine")
    assert admin_ctx.current_state == "ghost"

    result = admin_ctx.request_transition("pulse")
    assert result == {"old_state": "ghost", "new_state": "pulse"}


def test_plugin_context_uses_narrow_runtime_gateway(hud_app):
    plugin_ctx = hud_app._plugin_context_for_owner("plugin")

    assert not hasattr(plugin_ctx, "with_owner")
    assert not hasattr(plugin_ctx, "_with_owner")
    assert not hasattr(plugin_ctx, "_runtime")
    assert not hasattr(plugin_ctx, "_transition_to")
    assert not hasattr(plugin_ctx, "request_transition")
    gateway = getattr(plugin_ctx, "_HudPluginContext__runtime_gateway")
    assert not hasattr(gateway, "transition_to")


def test_transition_rejects_non_runtime_thread_call(hud_app):
    caught: list[Exception] = []

    def _worker() -> None:
        try:
            hud_app.transition_to("pulse")
        except Exception as exc:  # pragma: no cover - assertion below validates type/message
            caught.append(exc)

    thread = threading.Thread(target=_worker, name="transition-worker")
    thread.start()
    thread.join()

    assert len(caught) == 1
    assert isinstance(caught[0], ValueError)
    assert str(caught[0]) == "transition_to must run on HUD runtime thread"
    assert hud_app.current_state_value() == "ghost"


def test_extension_config_is_returned_as_copy():
    config = HudConfig(safe_mode=False)
    config.extensions = {"plugin-a": {"nested": {"count": 1}}}
    hud_app = HudApp(config=config, discover_plugins=False)
    try:
        plugin_ctx = hud_app._plugin_context_for_owner("plugin-a")
        ext = plugin_ctx.get_extension_config("plugin-a")
        ext["nested"]["count"] = 99

        assert hud_app.config.extensions["plugin-a"]["nested"]["count"] == 1
    finally:
        hud_app.shutdown()
