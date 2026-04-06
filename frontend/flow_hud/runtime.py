"""Runtime profiles and startup assembly for Flow HUD."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from flow_hud.core.app import HudApp
    from flow_hud.core.config import HudConfig

logger = logging.getLogger(__name__)

APP_NAME = "Flow HUD V2"
APP_VERSION = "0.2.0"

RUNTIME_DESKTOP = "desktop"
RUNTIME_WINDOWS = "windows"


@dataclass(frozen=True)
class RuntimePluginSpec:
    """Repo-owned plugin composition entry for a runtime profile."""

    import_path: str
    admin: bool = False

    def load_plugin_class(self) -> type:
        from flow_hud.plugins.base import HudPlugin

        module_name, separator, class_name = self.import_path.partition(":")
        if not separator or not module_name or not class_name:
            raise ValueError(f"invalid plugin import path: {self.import_path}")
        module = import_module(module_name)
        plugin_class = getattr(module, class_name, None)
        if plugin_class is None:
            raise ValueError(f"plugin class not found: {self.import_path}")
        if not isinstance(plugin_class, type) or not issubclass(plugin_class, HudPlugin):
            raise ValueError(f"plugin class is not a HudPlugin subclass: {self.import_path}")
        return plugin_class


_RUNTIME_PLUGIN_SPECS: dict[str, tuple[RuntimePluginSpec, ...]] = {
    RUNTIME_DESKTOP: (
        RuntimePluginSpec("flow_hud.adapters.debug_text_plugin:DebugTextPlugin"),
    ),
    RUNTIME_WINDOWS: (
        RuntimePluginSpec("flow_hud.adapters.debug_text_plugin:DebugTextPlugin"),
        RuntimePluginSpec("flow_hud.plugins.ipc.plugin:IpcClientPlugin", admin=True),
    ),
}


def runtime_plugin_specs(runtime_profile: str) -> tuple[RuntimePluginSpec, ...]:
    try:
        return _RUNTIME_PLUGIN_SPECS[runtime_profile]
    except KeyError as exc:
        raise ValueError(f"unknown runtime profile: {runtime_profile}") from exc


def create_hud_app(
    *,
    runtime_profile: str,
    config: "HudConfig | None" = None,
    discover_plugins: bool = True,
) -> "HudApp":
    from flow_hud.core.app import HudApp
    from flow_hud.core.config import HudConfig

    hud_config = config or HudConfig.load()
    hud_app = HudApp(config=hud_config, discover_plugins=discover_plugins)
    setup_runtime_plugins(hud_app, runtime_plugin_specs(runtime_profile))

    return hud_app


def setup_runtime_plugins(hud_app, plugin_specs: Iterable[RuntimePluginSpec]) -> None:
    for spec in plugin_specs:
        plugin_class = spec.load_plugin_class()
        plugin_name = plugin_class.manifest.name
        if hud_app.plugins.get(plugin_name) is not None:
            logger.info("Runtime profile plugin %r already registered, skipping explicit setup", plugin_name)
            continue

        plugin = plugin_class()
        if not hud_app.plugins.register(plugin):
            continue
        target_ctx = hud_app.admin_context if spec.admin else hud_app.plugin_context
        plugin.setup(target_ctx)


def _mount_canvas_widgets(canvas, widget_items: Iterable[tuple[str, object]]) -> None:
    for name, widget in widget_items:
        canvas.mount_widget(name, widget)
        logger.info("Mounted widget: %r -> canvas", name)


def run_hud(
    *,
    runtime_profile: str,
    config: "HudConfig | None" = None,
    discover_plugins: bool = True,
) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from PySide6.QtWidgets import QApplication

    from flow_hud.adapters.ui_canvas import HudCanvas

    app_qt = QApplication.instance() or QApplication(sys.argv)
    app_qt.setApplicationName(APP_NAME)
    app_qt.setApplicationVersion(APP_VERSION)

    hud_app = None
    try:
        hud_app = create_hud_app(
            runtime_profile=runtime_profile,
            config=config,
            discover_plugins=discover_plugins,
        )
        canvas = HudCanvas()
        _mount_canvas_widgets(canvas, hud_app.plugin_context.get_widgets().items())

        canvas.resize(400, 100)
        canvas.move(100, 50)
        canvas.show()

        logger.info(
            "HUD runtime running (profile=%s, plugins=%s, canvas widgets=%s)",
            runtime_profile,
            hud_app.plugins.names(),
            canvas.mounted_names(),
        )
        return app_qt.exec()
    finally:
        if hud_app is not None:
            hud_app.shutdown()
