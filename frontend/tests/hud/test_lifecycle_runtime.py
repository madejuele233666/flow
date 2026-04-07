import os
import sys
import threading

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from flow_hud.core.app import HudApp
from flow_hud.core.config import HudConfig
from flow_hud.core.events import HudBackgroundEventWorker, HudEvent, HudEventType
from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.manifest import HudPluginManifest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


class _Spec:
    def __init__(self, plugin_class, *, admin=False):
        self._plugin_class = plugin_class
        self.admin = admin

    def load_plugin_class(self):
        return self._plugin_class


def test_setup_is_invoked_once_with_profile_and_existing_registry_overlap():
    class DemoPlugin(HudPlugin):
        manifest = HudPluginManifest(name="demo")
        setup_calls = 0

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        app.plugins.register(DemoPlugin())

        app.setup_plugins([_Spec(DemoPlugin), _Spec(DemoPlugin)])
        app.setup_plugins([_Spec(DemoPlugin)])

        assert DemoPlugin.setup_calls == 1
    finally:
        app.shutdown()


def test_setup_plugins_does_not_reconstruct_already_active_profile_plugin():
    class DemoPlugin(HudPlugin):
        manifest = HudPluginManifest(name="demo")
        init_calls = 0
        setup_calls = 0

        def __init__(self) -> None:
            type(self).init_calls += 1

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        app.setup_plugins([_Spec(DemoPlugin)])
        app.setup_plugins([_Spec(DemoPlugin)])

        assert DemoPlugin.init_calls == 1
        assert DemoPlugin.setup_calls == 1
    finally:
        app.shutdown()


def test_setup_order_is_deterministic_with_profile_and_discovery_plugins():
    setup_order: list[str] = []

    class APlugin(HudPlugin):
        manifest = HudPluginManifest(name="a")

        def setup(self, ctx) -> None:
            setup_order.append("a")

    class BPlugin(HudPlugin):
        manifest = HudPluginManifest(name="b")

        def setup(self, ctx) -> None:
            setup_order.append("b")

    class CPlugin(HudPlugin):
        manifest = HudPluginManifest(name="c")

        def setup(self, ctx) -> None:
            setup_order.append("c")

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        # Simulate nondeterministic discovery registration order.
        app.plugins.register(CPlugin())
        app.plugins.register(APlugin())

        # Runtime profile plugin should setup first.
        app.setup_plugins([_Spec(BPlugin, admin=False)])

        assert setup_order == ["b", "a", "c"]
    finally:
        app.shutdown()


def test_profile_plugin_overrides_discovery_plugin_on_name_overlap():
    class DiscoveryPlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")
        setup_calls = 0

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

    class ProfilePlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")
        setup_calls = 0

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        app.plugins.register(DiscoveryPlugin())
        app.setup_plugins([_Spec(ProfilePlugin)])

        assert DiscoveryPlugin.setup_calls == 0
        assert ProfilePlugin.setup_calls == 1
        assert isinstance(app.plugins.get("dup"), ProfilePlugin)
    finally:
        app.shutdown()


def test_runtime_profile_duplicate_name_keeps_first_entry(caplog):
    class FirstPlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")
        setup_calls = 0

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

    class SecondPlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")
        setup_calls = 0

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        with caplog.at_level("WARNING"):
            app.setup_plugins([_Spec(FirstPlugin, admin=False), _Spec(SecondPlugin, admin=True)])

        assert isinstance(app.plugins.get("dup"), FirstPlugin)
        assert FirstPlugin.setup_calls == 1
        assert SecondPlugin.setup_calls == 0
        assert app.admin_routing_records()["dup"]["profile_admin"] is False
        assert any(
            "ignoring duplicate runtime-profile plugin 'dup'" in record.getMessage()
            for record in caplog.records
        )
    finally:
        app.shutdown()


def test_profile_replacement_is_ignored_after_plugin_already_setup():
    class InitialPlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")
        setup_calls = 0
        teardown_calls = 0

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

        def teardown(self) -> None:
            type(self).teardown_calls += 1

    class ReplacementPlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")
        setup_calls = 0
        teardown_calls = 0

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

        def teardown(self) -> None:
            type(self).teardown_calls += 1

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        app.plugins.register(InitialPlugin())
        app.setup_plugins()
        app.setup_plugins([_Spec(ReplacementPlugin)])

        assert isinstance(app.plugins.get("dup"), InitialPlugin)
        assert InitialPlugin.setup_calls == 1
        assert ReplacementPlugin.setup_calls == 0
    finally:
        app.shutdown()
        assert InitialPlugin.teardown_calls == 1
        assert ReplacementPlugin.teardown_calls == 0


def test_admin_routing_is_deterministic_and_recorded():
    class StandardPlugin(HudPlugin):
        manifest = HudPluginManifest(name="standard")
        owner_seen = None

        def setup(self, ctx) -> None:
            type(self).owner_seen = ctx.owner

    class AdminPlugin(HudPlugin):
        manifest = HudPluginManifest(name="admin")
        owner_seen = None

        def setup(self, ctx) -> None:
            type(self).owner_seen = ctx.owner

    config = HudConfig(safe_mode=False)
    config.admin_plugins = ["standard"]
    app = HudApp(config=config, discover_plugins=False)
    try:
        app.plugins.register(StandardPlugin())
        app.setup_plugins([_Spec(AdminPlugin, admin=True)])

        routing = app.admin_routing_records()
        assert routing["admin"]["final_admin"] is True
        assert routing["admin"]["profile_admin"] is True
        assert routing["admin"]["config_admin"] is False
        assert routing["standard"]["final_admin"] is True
        assert routing["standard"]["profile_admin"] is False
        assert routing["standard"]["config_admin"] is True
        assert routing["standard"]["conflict"] is True
        assert routing["standard"]["resolved_by_merge"] is True
        assert StandardPlugin.owner_seen == "standard"
        assert AdminPlugin.owner_seen == "admin"
    finally:
        app.shutdown()


def test_admin_routing_record_is_kept_when_setup_fails():
    class FailingPlugin(HudPlugin):
        manifest = HudPluginManifest(name="failing")

        def setup(self, ctx) -> None:
            raise RuntimeError("boom")

    config = HudConfig(safe_mode=False)
    config.admin_plugins = ["failing"]
    app = HudApp(config=config, discover_plugins=False)
    try:
        app.setup_plugins([_Spec(FailingPlugin, admin=False)])
        routing = app.admin_routing_records()
        assert routing["failing"]["final_admin"] is True
        assert routing["failing"]["profile_admin"] is False
        assert routing["failing"]["config_admin"] is True
        assert routing["failing"]["conflict"] is True
        assert routing["failing"]["resolved_by_merge"] is True
    finally:
        app.shutdown()


def test_setup_failure_cleans_partial_owner_registrations_immediately():
    class PartialFailPlugin(HudPlugin):
        manifest = HudPluginManifest(name="partial-fail")
        teardown_calls = 0

        def __init__(self) -> None:
            self._handler = lambda event: None

        def setup(self, ctx) -> None:
            ctx.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, self._handler)
            ctx.register_hook(self)
            ctx.register_widget("partial-fail-widget", QLabel("partial"), slot="center")
            raise RuntimeError("boom")

        def on_after_state_transition(self, payload):
            return None

        def teardown(self) -> None:
            type(self).teardown_calls += 1

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        app.setup_plugins([_Spec(PartialFailPlugin)])

        assert app.get_widget_mount("partial-fail-widget") is None
        mouse_handlers = list(app.event_bus._subscribers.get(HudEventType.MOUSE_GLOBAL_MOVE, []))
        assert mouse_handlers == []
        assert all(app.hook_manager._handlers[name] == [] for name in app.hook_manager._handlers)
        assert app.hook_manager._breakers == {}
        assert PartialFailPlugin.teardown_calls == 1
    finally:
        app.shutdown()


def test_admin_routing_conflict_uses_merged_policy():
    class ConflictPlugin(HudPlugin):
        manifest = HudPluginManifest(name="conflict")
        owner_seen = None

        def setup(self, ctx) -> None:
            type(self).owner_seen = ctx.owner

    config = HudConfig(safe_mode=False)
    config.admin_plugins = ["conflict"]
    app = HudApp(config=config, discover_plugins=False)
    try:
        app.setup_plugins([_Spec(ConflictPlugin, admin=False)])
        routing = app.admin_routing_records()
        assert routing["conflict"]["final_admin"] is True
        assert routing["conflict"]["profile_admin"] is False
        assert routing["conflict"]["config_admin"] is True
        assert routing["conflict"]["conflict"] is True
        assert routing["conflict"]["resolved_by_merge"] is True
        assert ConflictPlugin.owner_seen == "conflict"
    finally:
        app.shutdown()


def test_teardown_failure_does_not_leak_owner_registrations():
    calls = []

    class LeakyPlugin(HudPlugin):
        manifest = HudPluginManifest(name="leaky")

        def __init__(self) -> None:
            self._handler = lambda event: None

        def setup(self, ctx) -> None:
            calls.append(("owner", ctx.owner))
            ctx.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, self._handler)
            ctx.register_hook(self)
            ctx.register_widget("leaky-widget", QLabel("leaky"), slot="center")

        def on_after_state_transition(self, payload):
            return None

        def teardown(self) -> None:
            raise RuntimeError("boom")

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        app.plugins.register(LeakyPlugin())
        app.setup_plugins()

        assert calls == [("owner", "leaky")]
        assert app.get_widget_mount("leaky-widget") is not None

        mouse_handlers_before = list(app.event_bus._subscribers.get(HudEventType.MOUSE_GLOBAL_MOVE, []))
        assert len(mouse_handlers_before) == 1

        app.shutdown()

        assert app.get_widget_mount("leaky-widget") is None
        mouse_handlers_after = list(app.event_bus._subscribers.get(HudEventType.MOUSE_GLOBAL_MOVE, []))
        assert mouse_handlers_after == []
        assert all(app.hook_manager._handlers[name] == [] for name in app.hook_manager._handlers)
        assert app.hook_manager._breakers == {}
    finally:
        # allow calling in tests where shutdown already happened
        try:
            app.shutdown()
        except Exception:
            pass


def test_owner_widget_cleanup_runs_in_reverse_registration_order():
    class TrackingHudApp(HudApp):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.unregistered_names: list[str] = []

        def unregister_widget(self, name: str) -> None:
            self.unregistered_names.append(name)
            super().unregister_widget(name)

    class MultiWidgetPlugin(HudPlugin):
        manifest = HudPluginManifest(name="multi-widget")

        def setup(self, ctx) -> None:
            ctx.register_widget("first", QLabel("first"), slot="center")
            ctx.register_widget("second", QLabel("second"), slot="top_right")

        def teardown(self) -> None:
            raise RuntimeError("boom")

    app = TrackingHudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        app.plugins.register(MultiWidgetPlugin())
        app.setup_plugins()
        app.shutdown()
        assert app.unregistered_names == ["second", "first"]
    finally:
        try:
            app.shutdown()
        except Exception:
            pass


def test_registry_setup_all_bypass_is_disabled():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        try:
            app.plugins.setup_all(app.plugin_context)
        except RuntimeError as exc:
            assert "HudApp.setup_plugins" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        app.shutdown()


def test_registry_teardown_all_bypass_is_disabled():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        try:
            app.plugins.teardown_all()
        except RuntimeError as exc:
            assert "HudApp.shutdown" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        app.shutdown()


def test_setup_plugins_rejects_non_runtime_thread():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        caught: list[Exception] = []

        def _worker() -> None:
            try:
                app.setup_plugins()
            except Exception as exc:  # pragma: no cover - assertion below validates type/message
                caught.append(exc)

        thread = threading.Thread(target=_worker, name="setup-worker")
        thread.start()
        thread.join()

        assert len(caught) == 1
        assert isinstance(caught[0], ValueError)
        assert str(caught[0]) == "setup_plugins must run on HUD runtime thread"
    finally:
        app.shutdown()


def test_shutdown_rejects_non_runtime_thread():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        caught: list[Exception] = []

        def _worker() -> None:
            try:
                app.shutdown()
            except Exception as exc:  # pragma: no cover - assertion below validates type/message
                caught.append(exc)

        thread = threading.Thread(target=_worker, name="shutdown-worker")
        thread.start()
        thread.join()

        assert len(caught) == 1
        assert isinstance(caught[0], ValueError)
        assert str(caught[0]) == "shutdown must run on HUD runtime thread"
    finally:
        app.shutdown()


def test_emit_background_rejects_non_dataclass_payload():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        with pytest.raises(TypeError, match="dataclass"):
            app.emit_background_event(HudEventType.MOUSE_GLOBAL_MOVE, {"x": 1})
    finally:
        app.shutdown()


def test_subscribe_event_rejects_non_runtime_thread():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        caught: list[Exception] = []

        def _worker() -> None:
            try:
                app.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, lambda event: None, owner="plugin-a")
            except Exception as exc:  # pragma: no cover - assertion below validates type/message
                caught.append(exc)

        thread = threading.Thread(target=_worker, name="subscribe-worker")
        thread.start()
        thread.join()

        assert len(caught) == 1
        assert isinstance(caught[0], ValueError)
        assert str(caught[0]) == "subscribe_event must run on HUD runtime thread"
    finally:
        app.shutdown()


def test_register_hook_rejects_non_runtime_thread():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        caught: list[Exception] = []

        class _Hook:
            def on_after_state_transition(self, payload):
                return None

        def _worker() -> None:
            try:
                app.register_hook(_Hook(), owner="plugin-a")
            except Exception as exc:  # pragma: no cover - assertion below validates type/message
                caught.append(exc)

        thread = threading.Thread(target=_worker, name="hook-worker")
        thread.start()
        thread.join()

        assert len(caught) == 1
        assert isinstance(caught[0], ValueError)
        assert str(caught[0]) == "register_hook must run on HUD runtime thread"
    finally:
        app.shutdown()


def test_root_context_rejects_ownerless_registration():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        with pytest.raises(ValueError, match="owner-scoped context required"):
            app.plugin_context.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, lambda event: None)
        with pytest.raises(ValueError, match="owner-scoped context required"):
            app.plugin_context.register_hook(object())
        with pytest.raises(ValueError, match="owner-scoped context required"):
            app.plugin_context.register_widget("x", QLabel("x"), slot="center")
    finally:
        app.shutdown()


def test_app_rejects_ownerless_plugin_scoped_registration_calls():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        with pytest.raises(ValueError, match="requires owner"):
            app.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, lambda event: None, owner=None)
        with pytest.raises(ValueError, match="requires owner"):
            app.register_hook(object(), owner=None)
        with pytest.raises(ValueError, match="requires owner"):
            app.register_widget("x", "center", widget=QLabel("x"), owner=None, source="plugin")
    finally:
        app.shutdown()


def test_mutations_rejected_after_shutdown():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    app.shutdown()

    with pytest.raises(ValueError, match="after shutdown"):
        app.transition_to("pulse")
    with pytest.raises(ValueError, match="after shutdown"):
        app.register_widget("ghost", "center", widget=None, owner=None, source="service")
    with pytest.raises(ValueError, match="after shutdown"):
        app.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, lambda event: None, owner="plugin-a")
    with pytest.raises(ValueError, match="after shutdown"):
        app.emit_event(HudEventType.STATE_TRANSITIONED, None)
    with pytest.raises(ValueError, match="after shutdown"):
        app.emit_background_event(HudEventType.STATE_TRANSITIONED, None)


def test_plugin_context_cannot_emit_host_owned_lifecycle_events():
    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        ctx = app._plugin_context_for_owner("plugin-a")
        for event_type in (
            HudEventType.STATE_TRANSITIONED,
            HudEventType.WIDGET_REGISTERED,
            HudEventType.WIDGET_UNREGISTERED,
        ):
            with pytest.raises(ValueError, match="host-owned lifecycle events"):
                ctx.event_bus.emit(event_type, None)
            with pytest.raises(ValueError, match="host-owned lifecycle events"):
                ctx.event_bus.emit_background(event_type, None)
    finally:
        app.shutdown()


def test_transition_is_rejected_during_shutdown():
    class _TransitionInTeardownPlugin(HudPlugin):
        manifest = HudPluginManifest(name="teardown-transition")
        teardown_error = None

        def __init__(self) -> None:
            self._ctx = None

        def setup(self, ctx) -> None:
            self._ctx = ctx

        def teardown(self) -> None:
            assert self._ctx is not None
            try:
                self._ctx.request_transition("pulse")
            except Exception as exc:  # pragma: no cover - assertion below validates type/message
                type(self).teardown_error = exc

    app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
    try:
        app.setup_plugins([_Spec(_TransitionInTeardownPlugin, admin=True)])
        app.shutdown()
        assert isinstance(_TransitionInTeardownPlugin.teardown_error, ValueError)
        assert str(_TransitionInTeardownPlugin.teardown_error) == "transition_to unavailable during shutdown"
    finally:
        app.shutdown()


def test_background_worker_stop_timeout_preserves_live_thread_reference():
    gate = threading.Event()

    def _slow_handler(event) -> None:
        gate.wait(timeout=1.0)

    worker = HudBackgroundEventWorker(max_retries=1)
    worker.start()
    worker.enqueue(HudEvent(type=HudEventType.MOUSE_GLOBAL_MOVE), [_slow_handler])

    worker.stop(timeout=0.001)
    assert worker._thread is not None
    assert worker._thread.is_alive()

    gate.set()
    worker.stop(timeout=1.0)
    assert worker._thread is None
