"""HUD 插件基类 (Plugin Base).

对标主引擎 plugins/registry.py → FlowPlugin(ABC) — 完整复刻。

用法:
    from flow_hud.plugins.base import HudPlugin
    from flow_hud.plugins.manifest import HudPluginManifest

    class MyPlugin(HudPlugin):
        manifest = HudPluginManifest(
            name=\"my-plugin\",
            version=\"1.0.0\",
            description=\"我的 HUD 插件\",
        )

        def setup(self, ctx) -> None:
            ctx.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, self.on_mouse_move)
            ctx.register_hook(self)

        def teardown(self) -> None:
            # 释放资源
            pass

        def on_after_state_transition(self, payload) -> None:
            print(f\"State changed: {payload.old_state} → {payload.new_state}\")
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from flow_hud.plugins.manifest import HudPluginManifest

if TYPE_CHECKING:
    from flow_hud.plugins.context import HudPluginContext


class HudPlugin(ABC):
    """所有 HUD 插件的基类.

    对标主引擎 FlowPlugin(ABC) — 完整复刻。

    子类必须：
    1. 定义类属性 manifest: HudPluginManifest（或覆盖 name 属性）
    2. 按需实现 setup(ctx) 与 teardown()

    在 setup 中通过 HudPluginContext 可以：
    - ctx.subscribe_event(event_type, handler)   # 订阅事件
    - ctx.register_widget(name, widget)          # 注册 UI 插槽
    - ctx.register_hook(self)                    # 注册钩子实现
    - ctx.get_extension_config(\"plugin_name\")    # 获取插件配置
    """

    manifest: HudPluginManifest = HudPluginManifest(name="unnamed")

    def setup(self, ctx: HudPluginContext) -> None:
        """插件初始化 — 通过 HudPluginContext 安全沙盒与系统交互.

        类似 Obsidian 的 onload() / VSCode 的 activate()。
        ctx 只暴露注册 API，不暴露底层内部状态。
        """

    def teardown(self) -> None:
        """插件清理 — 释放资源.

        类似 Obsidian 的 onunload() / VSCode 的 deactivate()。
        """

    @property
    def name(self) -> str:
        """插件名称（只读，来源于 manifest）."""
        return self.manifest.name
