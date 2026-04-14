from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from flow_hud.ui_tokens.task_status import (
    TASK_STATUS_BREAK_SUGGESTED_TEXT,
    TASK_STATUS_LAYOUT_MARGINS,
    TASK_STATUS_LAYOUT_SPACING,
    format_task_status_duration,
    task_status_meta_text,
    TASK_STATUS_STYLE,
)

from .models import TaskStatusMode, TaskStatusSnapshot


class TaskStatusWidget(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self._snapshot = TaskStatusSnapshot.offline()

        self.setObjectName("task-status-card")
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TASK_STATUS_LAYOUT_MARGINS)
        layout.setSpacing(TASK_STATUS_LAYOUT_SPACING)

        self._state_label = QLabel(self)
        self._state_label.setObjectName("task-status-state")

        self._title_label = QLabel(self)
        self._title_label.setObjectName("task-status-title")
        self._title_label.setWordWrap(True)

        self._meta_label = QLabel(self)
        self._meta_label.setObjectName("task-status-meta")
        self._meta_label.setWordWrap(True)

        self._badge_label = QLabel(self)
        self._badge_label.setObjectName("task-status-badge")
        self._badge_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._state_label)
        layout.addWidget(self._title_label)
        layout.addWidget(self._meta_label)
        layout.addWidget(self._badge_label)

        self.setStyleSheet(TASK_STATUS_STYLE)

        self.render_snapshot(self._snapshot)

    @property
    def snapshot(self) -> TaskStatusSnapshot:
        return self._snapshot

    def render_snapshot(self, snapshot: TaskStatusSnapshot) -> None:
        self._snapshot = snapshot

        if snapshot.mode == TaskStatusMode.ACTIVE:
            self._state_label.setText(snapshot.state_label)
            self._title_label.setText(snapshot.title)
            self._meta_label.setText(format_task_status_duration(snapshot.duration_min))
            self._badge_label.setText(TASK_STATUS_BREAK_SUGGESTED_TEXT if snapshot.break_suggested else "")
            self._badge_label.setVisible(snapshot.break_suggested)
            return

        if snapshot.mode == TaskStatusMode.EMPTY:
            self._state_label.setText(snapshot.state_label)
            self._title_label.setText(snapshot.title)
            self._meta_label.setText(task_status_meta_text(snapshot.mode.value))
            self._badge_label.setText("")
            self._badge_label.setVisible(False)
            return

        self._state_label.setText(snapshot.state_label)
        self._title_label.setText(snapshot.title)
        self._meta_label.setText(task_status_meta_text(snapshot.mode.value))
        self._badge_label.setText("")
        self._badge_label.setVisible(False)
