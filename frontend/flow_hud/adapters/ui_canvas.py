"""HUD UI canvas with slot-aware widget composition."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QMainWindow, QVBoxLayout, QWidget

from flow_hud.core.widget_slots import VALID_WIDGET_SLOTS


@dataclass(frozen=True)
class _MountedWidget:
    widget: QWidget
    slot: str


class HudCanvas(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._widgets: dict[str, _MountedWidget] = {}
        self._slot_hosts: dict[str, QWidget] = {}
        self._slot_layouts: dict[str, QVBoxLayout] = {}

        self._setup_window()
        self._setup_layout()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("Flow HUD V2")

    def _setup_layout(self) -> None:
        self._central = QWidget(self)
        self._central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._grid = QGridLayout(self._central)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(8)

        slot_cells = {
            "top_left": (0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            "top_right": (0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            "center": (1, 1, Qt.AlignmentFlag.AlignCenter),
            "bottom_left": (2, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            "bottom_right": (2, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
        }

        for slot, (row, col, align) in slot_cells.items():
            host = QWidget(self._central)
            host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            layout = QVBoxLayout(host)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            layout.setAlignment(align)

            self._slot_hosts[slot] = host
            self._slot_layouts[slot] = layout
            self._grid.addWidget(host, row, col, alignment=align)

        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(2, 1)
        self._grid.setRowStretch(0, 1)
        self._grid.setRowStretch(1, 1)
        self._grid.setRowStretch(2, 1)

        self.setCentralWidget(self._central)

    def mount_widget(self, name: str, widget: QWidget, *, slot: str = "center") -> None:
        if slot not in VALID_WIDGET_SLOTS:
            allowed = ", ".join(sorted(VALID_WIDGET_SLOTS))
            raise ValueError(f"invalid widget slot: {slot!r}; allowed: {allowed}")

        mounted = self._widgets.get(name)
        if mounted is not None:
            if mounted.widget is widget:
                if mounted.slot == slot:
                    return
                old_layout = self._slot_layouts[mounted.slot]
                old_layout.removeWidget(widget)
            else:
                self.unmount_widget(name)

        host_layout = self._slot_layouts[slot]
        widget.setParent(self._slot_hosts[slot])
        host_layout.addWidget(widget)
        self._widgets[name] = _MountedWidget(widget=widget, slot=slot)

    def unmount_widget(self, name: str) -> None:
        mounted = self._widgets.pop(name, None)
        if mounted is None:
            return

        layout = self._slot_layouts[mounted.slot]
        layout.removeWidget(mounted.widget)
        mounted.widget.setParent(None)
        mounted.widget.deleteLater()

    def mounted_names(self) -> list[str]:
        return list(self._widgets.keys())

    def mounted_slots(self) -> dict[str, str]:
        return {name: record.slot for name, record in self._widgets.items()}
