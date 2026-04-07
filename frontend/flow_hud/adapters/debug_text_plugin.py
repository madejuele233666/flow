"""DebugTextPlugin — 开发验证用插件.

以插件形式验证 HUD V2 骨架架构的完整工作链路：
    setup(ctx) → ctx.register_widget() → HudCanvas.mount_widget()

携带 HudPluginManifest(name="debug-text")，在 setup() 阶段
创建一个写着 "HUD V2 System Base initialized" 的 Qt 标签控件，
并通过 ctx.register_widget("debug", widget) 注册到画布。

用法（在 main.py 或测试中手动注册）:
    plugin = DebugTextPlugin()
    hud_app.plugins.register(plugin)
    hud_app.setup_plugins()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.manifest import HudPluginManifest

if TYPE_CHECKING:
    from flow_hud.plugins.context import HudPluginContext

logger = logging.getLogger(__name__)


class DebugTextPlugin(HudPlugin):
    """开发验证插件 — 在画布中央显示骨架初始化确认文本.

    验证整条工作链路：
        HudPlugin.setup(ctx)
          → ctx.register_widget(name, widget)
          → HudCanvas.mount_widget(name, widget)
          → 文本在透明悬浮窗上可见
    """

    manifest = HudPluginManifest(
        name="debug-text",
        version="0.1.0",
        description="开发验证插件 — 在 HUD 画布上显示骨架初始化确认文本",
        author="flow-hud",
    )

    def __init__(self) -> None:
        self._label: QLabel | None = None

    def setup(self, ctx: HudPluginContext) -> None:
        """创建调试标签并注册到 HUD 画布."""
        self._label = QLabel("HUD V2 System Base initialized")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 220);
                background-color: rgba(0, 0, 0, 140);
                border: 1px solid rgba(255, 255, 255, 60);
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
                font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
                font-weight: 500;
            }
        """)

        ctx.register_widget("debug", self._label)
        logger.info("DebugTextPlugin: widget registered to canvas")

    def teardown(self) -> None:
        """释放 Qt 小部件资源."""
        if self._label is not None:
            self._label.deleteLater()
            self._label = None
        logger.debug("DebugTextPlugin: torn down")
