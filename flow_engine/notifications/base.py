"""通知后端抽象接口 + 聚合服务.

设计要点：
- Notifier ABC 定义单个后端合约（终端 / Webhook / Telegram / 桌面等）
- NotificationService 聚合多个后端，广播通知
- 插件通过 app.notifications.register(MyNotifier()) 注册新后端
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NotifyLevel(str, Enum):
    """通知级别."""
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class Notification:
    """通知载荷."""
    title: str
    body: str
    level: NotifyLevel = NotifyLevel.INFO
    extra: dict[str, Any] | None = None


class Notifier(ABC):
    """通知后端合约.

    实现此接口的类可以发送通知到特定渠道。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """后端标识名."""

    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """发送一条通知.

        Returns:
            是否发送成功。
        """

    def available(self) -> bool:
        """后端是否可用（默认可用）."""
        return True


class NotificationService:
    """通知聚合服务 — 广播到全部已注册后端.

    用法：
        svc = NotificationService()
        svc.register(TerminalNotifier())
        svc.register(WebhookNotifier(url))
        svc.notify("标题", "内容", level=NotifyLevel.SUCCESS)
    """

    def __init__(self) -> None:
        self._backends: list[Notifier] = []

    def register(self, notifier: Notifier) -> None:
        """注册一个通知后端."""
        self._backends.append(notifier)
        logger.info("notification backend registered: %s", notifier.name)

    def unregister(self, name: str) -> None:
        """按名称移除后端."""
        self._backends = [b for b in self._backends if b.name != name]

    def notify(
        self,
        title: str,
        body: str,
        level: NotifyLevel = NotifyLevel.INFO,
        extra: dict[str, Any] | None = None,
    ) -> int:
        """广播通知到所有可用后端.

        Returns:
            成功发送的后端数量。
        """
        notification = Notification(title=title, body=body, level=level, extra=extra)
        sent = 0
        for backend in self._backends:
            if not backend.available():
                continue
            try:
                if backend.send(notification):
                    sent += 1
            except Exception:
                logger.exception("notification backend %s failed", backend.name)
        return sent

    def backends(self) -> list[str]:
        """返回全部已注册后端名."""
        return [b.name for b in self._backends]
