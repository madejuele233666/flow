"""终端通知后端 — Notifier 的默认实现."""

from __future__ import annotations

import sys

from flow_engine.notifications.base import Notification, Notifier, NotifyLevel

# 级别对应的终端图标
_ICONS: dict[NotifyLevel, str] = {
    NotifyLevel.INFO: "ℹ️ ",
    NotifyLevel.WARNING: "⚠️ ",
    NotifyLevel.SUCCESS: "✅",
    NotifyLevel.ERROR: "❌",
}


class TerminalNotifier(Notifier):
    """将通知输出到终端 stderr（不干扰 stdout 管道）."""

    @property
    def name(self) -> str:
        return "terminal"

    def send(self, notification: Notification) -> bool:
        icon = _ICONS.get(notification.level, "")
        print(
            f"{icon} [{notification.title}] {notification.body}",
            file=sys.stderr,
        )
        return True
