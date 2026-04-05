"""HUD V2 主入口 — 最终集装 (Final Assembly).

将所有模块组装在一起：
    QApplication → HudApp → HudCanvas → DebugTextPlugin

架构连接顺序:
    1. 创建 QApplication（必须在任何 Qt 对象之前）
    2. 初始化 HudApp（DI 编排器，按配置组装所有核心模块）
    3. 注册 DebugTextPlugin 并执行 setup（创建 QLabel 并注册到 ctx）
    4. 创建 HudCanvas（透明悬浮画布）
    5. 将 ctx 中已注册的小部件挂载到 Canvas
    6. 显示 Canvas
    7. 进入 Qt 事件循环

运行方法:
    python -m flow_hud.main
    # 或
    python flow_hud/main.py
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)


def main() -> int:
    """启动 HUD V2 骨架应用."""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # ── 1. QApplication（必须先于所有 Qt 对象） ──
    from PySide6.QtWidgets import QApplication
    app_qt = QApplication.instance() or QApplication(sys.argv)
    app_qt.setApplicationName("Flow HUD V2")
    app_qt.setApplicationVersion("0.2.0")

    # ── 2. HudApp（配置驱动的 DI 编排器） ──
    from flow_hud.core.app import HudApp
    from flow_hud.core.config import HudConfig

    config = HudConfig(safe_mode=False)  # safe_mode=False 允许 entry_points 自动发现
    hud_app = HudApp(config=config)

    # ── 3. 注册 DebugTextPlugin ──
    from flow_hud.adapters.debug_text_plugin import DebugTextPlugin

    debug_plugin = DebugTextPlugin()
    hud_app.plugins.register(debug_plugin)

    # 手动 setup（discover() 仅扫描 entry_points，手动注册的插件需要手动 setup）
    debug_plugin.setup(hud_app.plugin_context)
    logger.info("DebugTextPlugin setup complete")

    # ── 4. 创建 HudCanvas ──
    from flow_hud.adapters.ui_canvas import HudCanvas

    canvas = HudCanvas()

    # ── 5. 将 plugin_context 中已注册的小部件挂载到 Canvas ──
    widgets = hud_app.plugin_context.get_widgets()
    for name, widget in widgets.items():
        canvas.mount_widget(name, widget)
        logger.info("Mounted widget: %r → canvas", name)

    # ── 6. 显示 Canvas ──
    canvas.resize(400, 100)
    canvas.move(100, 50)  # 屏幕左上角偏移，确保可见
    canvas.show()

    logger.info(
        "HUD V2 running — plugins: %s, canvas widgets: %s",
        hud_app.plugins.names(),
        canvas.mounted_names(),
    )

    # ── 7. Qt 事件循环 ──
    try:
        exit_code = app_qt.exec()
    finally:
        hud_app.shutdown()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
