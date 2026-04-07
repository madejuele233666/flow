"""HUD 插件注册表 (Plugin Registry).

对标主引擎 plugins/registry.py → PluginRegistry — 完整复刻，适配 HUD。

支持两种注册方式：
1. 编程式：registry.register(MyPlugin())
2. 自动发现：registry.discover() 扫描 entry_points(group=\"flow_hud.plugins\")

entry_points 用法（第三方插件的 pyproject.toml）:
    [project.entry-points.\"flow_hud.plugins\"]
    my-plugin = \"my_package.plugin:MyPluginClass\"
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from flow_hud.plugins.base import HudPlugin

if TYPE_CHECKING:
    from flow_hud.plugins.context import HudPluginContext, HudAdminContext

logger = logging.getLogger(__name__)

# entry_points API
if sys.version_info >= (3, 12):
    from importlib.metadata import entry_points
else:
    from importlib.metadata import entry_points

# HUD 插件 entry_points 组名（对标主引擎 \"flow_engine.plugins\"）
ENTRY_POINT_GROUP = "flow_hud.plugins"


class HudPluginRegistry:
    """HUD 插件发现、注册与管理.

    对标主引擎 PluginRegistry — 完整 API 复刻。

    支持：
    - 编程式注册（开发/测试阶段首选）
    - entry_points 自动发现（生产环境 pip install 即注册）
    - 白名单分级 Context 下发（普通 vs Admin 权限）
    - 逆序 teardown（保证依赖清理顺序）
    """

    def __init__(self) -> None:
        self._plugins: dict[str, HudPlugin] = {}

    def register(self, plugin: HudPlugin) -> bool:
        """注册一个插件实例（编程式）."""
        name = plugin.manifest.name
        if name in self._plugins:
            logger.warning("plugin %r already registered, skipping", name)
            return False
        self._plugins[name] = plugin
        logger.info("plugin registered: %s v%s", name, plugin.manifest.version)
        return True

    def replace(self, plugin: HudPlugin) -> None:
        """Replace an existing plugin implementation by manifest name."""
        name = plugin.manifest.name
        previous = self._plugins.get(name)
        self._plugins[name] = plugin
        if previous is None:
            logger.info("plugin registered: %s v%s", name, plugin.manifest.version)
            return
        logger.warning(
            "plugin %r implementation replaced: %s -> %s",
            name,
            type(previous).__name__,
            type(plugin).__name__,
        )

    def discover(self) -> list[str]:
        """扫描 Python entry_points 自动发现并注册插件.

        第三方包通过 pyproject.toml 声明 entry_points 即可被发现。

        Returns:
            成功发现的插件名列表。
        """
        discovered: list[str] = []
        eps = entry_points()

        if hasattr(eps, "select"):
            plugin_eps = eps.select(group=ENTRY_POINT_GROUP)
        else:
            plugin_eps = eps.get(ENTRY_POINT_GROUP, [])

        for ep in plugin_eps:
            try:
                plugin_cls = ep.load()
                if isinstance(plugin_cls, type) and issubclass(plugin_cls, HudPlugin):
                    plugin = plugin_cls()
                    self.register(plugin)
                    discovered.append(plugin.manifest.name)
                else:
                    logger.warning(
                        "entry_point %r does not point to a HudPlugin subclass", ep.name,
                    )
            except Exception:
                logger.exception("failed to load plugin from entry_point: %r", ep.name)

        if discovered:
            logger.info("auto-discovered %d plugins: %s", len(discovered), discovered)
        return discovered

    def setup_all(
        self,
        ctx: HudPluginContext,
        admin_ctx: HudAdminContext | None = None,
        admin_names: list[str] | None = None,
    ) -> None:
        """Deprecated bypass path kept only for compatibility guardrails."""
        raise RuntimeError(
            "HudPluginRegistry.setup_all is disabled; use HudApp.setup_plugins(...) as "
            "the single lifecycle authority"
        )

    def teardown_all(self) -> None:
        """Deprecated bypass path kept only for compatibility guardrails."""
        raise RuntimeError(
            "HudPluginRegistry.teardown_all is disabled; use HudApp.shutdown() as "
            "the single lifecycle authority"
        )

    def get(self, name: str) -> HudPlugin | None:
        """按名称获取插件实例."""
        return self._plugins.get(name)

    def all(self) -> list[HudPlugin]:
        """返回全部已注册插件实例列表."""
        return list(self._plugins.values())

    def names(self) -> list[str]:
        """返回全部已注册插件名列表."""
        return list(self._plugins.keys())
