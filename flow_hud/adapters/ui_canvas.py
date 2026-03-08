"""HUD UI 画布 (UI Canvas) — 透明悬浮底板.

对标 design.md Decision 10 — MVP 防腐层与 UI 画布隔离。

设计要点:
- 完全透明、无边框、无系统焦点的底板 QMainWindow。
- 不承载任何业务逻辑 — 仅作为插件动态插入小部件的容器。
- 插件通过 HudPluginContext.register_widget(name, widget) 注册小部件，
  画布在收到 WIDGET_REGISTERED 事件后将小部件挂载到布局中。
- 窗口保持最顶层 (WindowStaysOnTopHint)，鼠标事件穿透（WA_TransparentForMouseEvents）。

生命周期:
    canvas = HudCanvas()
    canvas.show()                        # 显示透明悬浮窗
    canvas.mount_widget(\"debug\", widget)  # 手动挂载（或由 HudApp 通过事件驱动）
    canvas.close()                       # 关闭
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class HudCanvas(QMainWindow):
    """完全透明、无边框的 HUD 底板窗口.

    职责：
    - 提供透明「画布」供插件动态插入 QWidget 碎片。
    - 不感知任何业务逻辑，不直接持有 HudApp 引用。
    - 通过 mount_widget(name, widget) 动态组合视觉部件。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._widgets: dict[str, QWidget] = {}

        self._setup_window()
        self._setup_layout()

    def _setup_window(self) -> None:
        """配置透明无边框窗口属性."""
        # 无边框 + 始终置顶
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # 不在任务栏显示
        )

        # 透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 不获取系统焦点（不干扰用户当前应用）
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # 默认全屏（覆盖整个屏幕以支持任意位置插入部件）
        self.setWindowTitle("Flow HUD V2")

    def _setup_layout(self) -> None:
        """初始化中央容器和布局."""
        self._central = QWidget(self)
        self._central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._layout = QVBoxLayout(self._central)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.setCentralWidget(self._central)

    def mount_widget(self, name: str, widget: QWidget) -> None:
        """将插件提供的小部件挂载到画布.

        Args:
            name: 小部件唯一标识符（用于后续 unmount）
            widget: 要挂载的 Qt 小部件实例

        Note:
            当前实现使用 VBoxLayout 顺序追加。
            后续扩展可支持按 slot 名称定位（如 \"top_right\", \"center\"）。
        """
        if name in self._widgets:
            logger.warning("widget %r already mounted, replacing", name)
            old = self._widgets[name]
            self._layout.removeWidget(old)
            old.setParent(None)

        widget.setParent(self._central)
        self._layout.addWidget(widget)
        self._widgets[name] = widget
        logger.info("HudCanvas: mounted widget %r", name)

    def unmount_widget(self, name: str) -> None:
        """卸载并销毁指定小部件.

        Args:
            name: 小部件唯一标识符
        """
        widget = self._widgets.pop(name, None)
        if widget:
            self._layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
            logger.info("HudCanvas: unmounted widget %r", name)

    def mounted_names(self) -> list[str]:
        """返回已挂载的小部件名称列表."""
        return list(self._widgets.keys())
