"""插件注册表 — FlowPlugin 基类 + 自动发现.

设计来源：
- Obsidian: Plugin 基类 + onload/onunload + this.app 注入
- VSCode: package.json manifest 声明式元数据
- Home Assistant: async_setup_entry(hass) setup 注入
- Python entry_points: pip install 即注册

用法（第三方插件）：
    # my_plugin/plugin.py
    class TelegramPlugin(FlowPlugin):
        manifest = PluginManifest(
            name="telegram-notifier",
            version="1.0.0",
            description="Telegram 通知",
        )

        def setup(self, app):
            token = app.config.extensions.get("telegram", {}).get("bot_token")
            self._bot = TelegramBot(token)
            app.hooks.register(self)

        def on_after_transition(self, task, old_state, new_state):
            self._bot.send(f"{task.title}: {old_state} → {new_state}")

    # my_plugin/pyproject.toml
    [project.entry-points."flow_engine.plugins"]
    telegram = "my_plugin.plugin:TelegramPlugin"
"""

from __future__ import annotations

import logging
import sys
from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flow_engine.app import FlowApp

logger = logging.getLogger(__name__)

# entry_points API 从 importlib.metadata 获取
if sys.version_info >= (3, 12):
    from importlib.metadata import entry_points
else:
    from importlib.metadata import entry_points


# ---------------------------------------------------------------------------
# 插件元信息
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PluginManifest:
    """声明式插件元数据（类似 package.json / manifest.json）."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    requires: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 插件基类
# ---------------------------------------------------------------------------

class FlowPlugin(ABC):
    """所有 Flow Engine 插件的基类.

    子类必须：
    1. 定义类属性 `manifest: PluginManifest`
    2. 实现 `setup(app)` 方法

    在 setup 中通过 app 引用可以：
    - app.hooks.register(self)            # 注册钩子
    - app.notifications.register(...)     # 注册通知后端
    - app.exporters.register(...)         # 注册导出格式
    - app.ranker.add_factor(...)          # 注册排序因子
    - app.cli_group.add_command(...)      # 注册 CLI 命令
    """

    manifest: PluginManifest = PluginManifest(name="unnamed")

    def setup(self, app: FlowApp) -> None:
        """插件初始化 — 通过 app 注入获取整个系统.

        类似 Obsidian 的 onload() / VSCode 的 activate()。
        """

    def teardown(self) -> None:
        """插件清理 — 释放资源.

        类似 Obsidian 的 onunload() / VSCode 的 deactivate()。
        """

    @property
    def name(self) -> str:
        return self.manifest.name


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

ENTRY_POINT_GROUP = "flow_engine.plugins"


class PluginRegistry:
    """插件发现、注册与管理.

    支持两种注册方式：
    1. 编程式: registry.register(MyPlugin())
    2. 自动发现: registry.discover() 扫描 entry_points
    """

    def __init__(self) -> None:
        self._plugins: dict[str, FlowPlugin] = {}

    def register(self, plugin: FlowPlugin) -> None:
        """注册一个插件实例."""
        name = plugin.manifest.name
        if name in self._plugins:
            logger.warning("plugin %s already registered, skipping", name)
            return
        self._plugins[name] = plugin
        logger.info(
            "plugin registered: %s v%s", name, plugin.manifest.version,
        )

    def discover(self) -> list[str]:
        """扫描 Python entry_points 自动发现并注册插件.

        第三方包通过 pyproject.toml 声明 entry_points 即可被发现。

        Returns:
            成功发现的插件名列表。
        """
        discovered: list[str] = []
        eps = entry_points()

        # Python 3.12+ 和旧版的 API 略有不同
        if hasattr(eps, "select"):
            plugin_eps = eps.select(group=ENTRY_POINT_GROUP)
        else:
            plugin_eps = eps.get(ENTRY_POINT_GROUP, [])

        for ep in plugin_eps:
            try:
                plugin_cls = ep.load()
                if isinstance(plugin_cls, type) and issubclass(plugin_cls, FlowPlugin):
                    plugin = plugin_cls()
                    self.register(plugin)
                    discovered.append(plugin.manifest.name)
                else:
                    logger.warning(
                        "entry_point %s does not point to a FlowPlugin subclass", ep.name,
                    )
            except Exception:
                logger.exception("failed to load plugin from entry_point: %s", ep.name)

        if discovered:
            logger.info("auto-discovered %d plugins: %s", len(discovered), discovered)
        return discovered

    def setup_all(self, app: FlowApp) -> None:
        """对所有已注册的插件调用 setup(app)."""
        for name, plugin in self._plugins.items():
            try:
                plugin.setup(app)
                logger.info("plugin %s setup complete", name)
            except Exception:
                logger.exception("plugin %s setup failed", name)

    def teardown_all(self) -> None:
        """对所有已注册的插件调用 teardown()."""
        for name, plugin in self._plugins.items():
            try:
                plugin.teardown()
            except Exception:
                logger.exception("plugin %s teardown failed", name)

    def get(self, name: str) -> FlowPlugin | None:
        """按名称获取插件."""
        return self._plugins.get(name)

    def all(self) -> list[FlowPlugin]:
        """返回全部已注册插件."""
        return list(self._plugins.values())

    def names(self) -> list[str]:
        """返回全部已注册插件名."""
        return list(self._plugins.keys())
