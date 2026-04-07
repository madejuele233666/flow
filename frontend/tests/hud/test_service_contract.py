"""Service-contract tests for canonical HUD runtime boundaries."""

import os
import sys

import pytest
from PySide6.QtWidgets import QApplication

from flow_hud.adapters.debug_text_plugin import DebugTextPlugin
from flow_hud.core.app import HudApp
from flow_hud.core.config import HudConfig
from flow_hud.core.service import HudLocalService, HudServiceProtocol
from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.manifest import HudPluginManifest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def hud_app():
    config = HudConfig(safe_mode=False)
    app = HudApp(config=config, discover_plugins=False)
    yield app
    app.shutdown()


@pytest.fixture
def service(hud_app):
    return HudLocalService(hud_app)


class TestHudServiceProtocol:
    def test_local_service_is_instance_of_protocol(self, service):
        assert isinstance(service, HudServiceProtocol)

    def test_protocol_has_required_methods(self):
        for method_name in ["get_status", "transition_to", "register_widget", "list_plugins"]:
            assert hasattr(HudServiceProtocol, method_name)


class TestTransitionTo:
    def test_valid_transition_returns_port_safe_dict(self, service):
        result = service.transition_to("pulse")
        assert result == {"old_state": "ghost", "new_state": "pulse"}

    def test_invalid_target_raises_value_error(self, service):
        with pytest.raises(ValueError, match="invalid target state"):
            service.transition_to("flying")

    def test_illegal_transition_raises_value_error(self, service):
        with pytest.raises(ValueError):
            service.transition_to("command")


class TestRegisterWidget:
    def test_service_path_reports_reservation_not_mount(self, service):
        result = service.register_widget("w", "top_right")
        assert result == {
            "name": "w",
            "slot": "top_right",
            "reserved": True,
            "mounted": False,
        }

    def test_invalid_slot_is_rejected(self, service):
        with pytest.raises(ValueError, match="invalid widget slot"):
            service.register_widget("w", "not_a_slot")


class TestListPlugins:
    def test_returns_list_of_dicts(self, service, hud_app):
        hud_app.plugins.register(DebugTextPlugin())
        hud_app.setup_plugins()
        result = service.list_plugins()
        assert isinstance(result, list)
        assert all(isinstance(item, dict) for item in result)
        assert len(result) == 1
        for item in result:
            assert set(item.keys()) == {"name", "version", "description"}


class TestStatus:
    def test_active_plugins_excludes_setup_failures(self):
        class _FailingPlugin(HudPlugin):
            manifest = HudPluginManifest(name="failing")

            def setup(self, ctx) -> None:
                raise RuntimeError("boom")

        class _Spec:
            def __init__(self, plugin_class):
                self._plugin_class = plugin_class
                self.admin = False

            def load_plugin_class(self):
                return self._plugin_class

        app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
        try:
            service = HudLocalService(app)
            app.setup_plugins([_Spec(_FailingPlugin)])
            status = service.get_status()
            assert status["active_plugins"] == []
        finally:
            app.shutdown()

    def test_list_plugins_excludes_setup_failures(self):
        class _FailingPlugin(HudPlugin):
            manifest = HudPluginManifest(name="failing")

            def setup(self, ctx) -> None:
                raise RuntimeError("boom")

        class _Spec:
            def __init__(self, plugin_class):
                self._plugin_class = plugin_class
                self.admin = False

            def load_plugin_class(self):
                return self._plugin_class

        app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
        try:
            service = HudLocalService(app)
            app.setup_plugins([_Spec(_FailingPlugin)])
            assert service.list_plugins() == []
        finally:
            app.shutdown()

    def test_active_plugins_empty_after_shutdown(self):
        class _OkPlugin(HudPlugin):
            manifest = HudPluginManifest(name="ok")

            def setup(self, ctx) -> None:
                return None

        class _Spec:
            def __init__(self, plugin_class):
                self._plugin_class = plugin_class
                self.admin = False

            def load_plugin_class(self):
                return self._plugin_class

        app = HudApp(config=HudConfig(safe_mode=False), discover_plugins=False)
        try:
            service = HudLocalService(app)
            app.setup_plugins([_Spec(_OkPlugin)])
            assert service.get_status()["active_plugins"] == ["ok"]
            app.shutdown()
            assert service.get_status()["active_plugins"] == []
            assert service.list_plugins() == []
        finally:
            app.shutdown()
