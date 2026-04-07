from flow_hud.runtime import RUNTIME_DESKTOP, RUNTIME_WINDOWS, runtime_plugin_specs
from flow_hud.runtime import setup_runtime_plugins


def test_desktop_runtime_profile_is_debug_only():
    specs = runtime_plugin_specs(RUNTIME_DESKTOP)

    assert [spec.import_path for spec in specs] == [
        "flow_hud.adapters.debug_text_plugin:DebugTextPlugin",
    ]
    assert [spec.admin for spec in specs] == [False]


def test_windows_runtime_profile_includes_ipc_plugin_as_admin():
    specs = runtime_plugin_specs(RUNTIME_WINDOWS)

    assert [spec.import_path for spec in specs] == [
        "flow_hud.adapters.debug_text_plugin:DebugTextPlugin",
        "flow_hud.plugins.ipc.plugin:IpcClientPlugin",
    ]
    assert [spec.admin for spec in specs] == [False, True]


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
