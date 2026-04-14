import pytest
from unittest.mock import MagicMock, patch

from flow_hud.core.config import HudConfig
from flow_hud import runtime as runtime_module
from flow_hud.runtime import RUNTIME_DESKTOP, RUNTIME_WINDOWS, runtime_plugin_specs
from flow_hud.runtime import setup_runtime_plugins
from flow_hud.plugins import registry as registry_module
from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.manifest import HudPluginManifest
from flow_hud.plugins.registry import HudPluginRegistry


def test_desktop_runtime_profile_is_debug_only():
    specs = runtime_plugin_specs(RUNTIME_DESKTOP)

    assert [spec.import_path for spec in specs] == [
        "flow_hud.adapters.debug_text_plugin:DebugTextPlugin",
    ]
    assert [spec.admin for spec in specs] == [False]


def test_windows_runtime_profile_includes_ipc_plugin_as_admin():
    specs = runtime_plugin_specs(RUNTIME_WINDOWS)

    assert [spec.import_path for spec in specs] == [
        "flow_hud.plugins.ipc.plugin:IpcClientPlugin",
        "flow_hud.task_status.plugin:TaskStatusPlugin",
    ]
    assert [spec.admin for spec in specs] == [True, False]


def test_windows_main_uses_windows_runtime_profile(monkeypatch):
    import flow_hud.windows_main as windows_main

    seen = {}

    def _fake_run_hud(**kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(windows_main, "run_hud", _fake_run_hud)
    monkeypatch.setattr(windows_main.HudConfig, "load", staticmethod(lambda: HudConfig(safe_mode=False)))

    assert windows_main.main() == 0
    assert seen["runtime_profile"] == RUNTIME_WINDOWS
    assert seen["discover_plugins"] is False


class _FakeHudApp:
    def __init__(self):
        self.calls = []

    def setup_plugins(self, specs):
        self.calls.append(tuple(specs))


class _FakeSpec:
    def __init__(self, name: str, *, admin: bool = False):
        self.import_path = name
        self.admin = admin


def test_setup_runtime_plugins_delegates_to_single_authority():
    fake_app = _FakeHudApp()
    specs = [_FakeSpec("a"), _FakeSpec("b", admin=True)]

    setup_runtime_plugins(fake_app, specs)

    assert len(fake_app.calls) == 1
    assert fake_app.calls[0] == tuple(specs)


def test_setup_runtime_plugins_requires_setup_plugins_method():
    class _NoSetup:
        pass

    try:
        setup_runtime_plugins(_NoSetup(), [])
    except TypeError as exc:
        assert "setup_plugins" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_registry_discover_reports_only_successfully_registered_plugins(monkeypatch):
    class _DupPlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")

    class _EntryPoint:
        name = "dup"

        @staticmethod
        def load():
            return _DupPlugin

    class _EntryPoints:
        @staticmethod
        def select(group: str):
            assert group == "flow_hud.plugins"
            return [_EntryPoint(), _EntryPoint()]

    monkeypatch.setattr(registry_module, "entry_points", lambda: _EntryPoints())
    registry = HudPluginRegistry()

    discovered = registry.discover()

    assert discovered == ["dup"]
    assert registry.names() == ["dup"]


def test_create_hud_app_validates_profile_before_constructing_app(monkeypatch):
    with patch.dict("sys.modules", {"PySide6": MagicMock(), "PySide6.QtCore": MagicMock()}):
        import flow_hud.core.app as app_module

        constructed = {"count": 0}

        class _FakeHudApp:
            def __init__(self, *args, **kwargs):
                constructed["count"] += 1

            def shutdown(self):
                return None

        monkeypatch.setattr(app_module, "HudApp", _FakeHudApp)

        with pytest.raises(ValueError, match="unknown runtime profile"):
            runtime_module.create_hud_app(
                runtime_profile="does-not-exist",
                config=HudConfig(safe_mode=False),
                discover_plugins=False,
            )

        assert constructed["count"] == 0


def test_create_hud_app_shuts_down_on_setup_failure(monkeypatch):
    with patch.dict("sys.modules", {"PySide6": MagicMock(), "PySide6.QtCore": MagicMock()}):
        import flow_hud.core.app as app_module

        state = {"shutdown_called": 0}

        class _FakeHudApp:
            def __init__(self, *args, **kwargs):
                return None

            def shutdown(self):
                state["shutdown_called"] += 1

        def _boom(hud_app, plugin_specs):
            raise RuntimeError("boom")

        monkeypatch.setattr(app_module, "HudApp", _FakeHudApp)
        monkeypatch.setattr(runtime_module, "setup_runtime_plugins", _boom)

        with pytest.raises(RuntimeError, match="boom"):
            runtime_module.create_hud_app(
                runtime_profile=RUNTIME_DESKTOP,
                config=HudConfig(safe_mode=False),
                discover_plugins=False,
            )

        assert state["shutdown_called"] == 1
