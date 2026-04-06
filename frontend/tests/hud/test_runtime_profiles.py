from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.manifest import HudPluginManifest
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


class _FakeRegistry:
    def __init__(self, existing=None):
        self._plugins = dict(existing or {})

    def get(self, name):
        return self._plugins.get(name)

    def register(self, plugin):
        if plugin.manifest.name in self._plugins:
            return False
        self._plugins[plugin.manifest.name] = plugin
        return True


class _FakeHudApp:
    def __init__(self, existing=None):
        self.plugins = _FakeRegistry(existing=existing)
        self.plugin_context = object()
        self.admin_context = object()


class _FakeSpec:
    def __init__(self, plugin_class, *, admin=False):
        self._plugin_class = plugin_class
        self.admin = admin

    def load_plugin_class(self):
        return self._plugin_class


def test_setup_runtime_plugins_skips_duplicate_plugin_registration():
    class ExistingPlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")

    class DuplicatePlugin(HudPlugin):
        manifest = HudPluginManifest(name="dup")
        instances_created = 0
        setup_calls = 0

        def __init__(self):
            type(self).instances_created += 1

        def setup(self, ctx) -> None:
            type(self).setup_calls += 1

    fake_app = _FakeHudApp(existing={"dup": ExistingPlugin()})

    setup_runtime_plugins(fake_app, [_FakeSpec(DuplicatePlugin)])

    assert DuplicatePlugin.instances_created == 0
    assert DuplicatePlugin.setup_calls == 0


def test_setup_runtime_plugins_uses_admin_context_for_admin_specs():
    class AdminPlugin(HudPlugin):
        manifest = HudPluginManifest(name="admin")
        received_context = None

        def setup(self, ctx) -> None:
            type(self).received_context = ctx

    fake_app = _FakeHudApp()

    setup_runtime_plugins(fake_app, [_FakeSpec(AdminPlugin, admin=True)])

    assert AdminPlugin.received_context is fake_app.admin_context
