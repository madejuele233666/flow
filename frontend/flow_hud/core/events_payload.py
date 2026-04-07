"""强类型事件载荷 (Typed Event Payloads).

对标主引擎 events_payload.py — 每个 HudEventType 对应一个 frozen dataclass。
替代弱类型 dict 传参，提供 IDE 自动补全和 mypy 静态检查。

【防腐规定】该文件内严禁出现任何 PySide6 或外设相关的 import。

用法:
    from flow_hud.core.events_payload import MouseMovePayload
    bus.emit(HudEventType.MOUSE_GLOBAL_MOVE, MouseMovePayload(x=100, y=200))

    # 订阅端
    def on_mouse_move(event: HudEvent) -> None:
        p: MouseMovePayload = event.payload
        print(p.x, p.y)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# 鼠标事件载荷
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MouseMovePayload:
    """全局鼠标坐标更新 — MOUSE_GLOBAL_MOVE 事件载荷."""

    x: int
    y: int
    screen_index: int = 0


# ---------------------------------------------------------------------------
# 状态事件载荷
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StateTransitionedPayload:
    """HUD 状态完成转换后的广播 — STATE_TRANSITIONED 事件载荷.

    使用字符串而非 HudState 枚举，确保载荷完全无领域类型依赖。
    """

    old_state: str   # HudState.value
    new_state: str   # HudState.value


# ---------------------------------------------------------------------------
# IPC 事件载荷
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IpcMessageReceivedPayload:
    """从 Flow Engine 后端接收到的 IPC 消息 — IPC_MESSAGE_RECEIVED 事件载荷."""

    method: str
    data: dict[str, Any]


# ---------------------------------------------------------------------------
# UI 注册事件载荷
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WidgetRegisteredPayload:
    """UI 插槽注册通知 — WIDGET_REGISTERED 事件载荷."""

    name: str
    slot: str


@dataclass(frozen=True)
class WidgetUnregisteredPayload:
    """UI 插槽卸载通知 — WIDGET_UNREGISTERED 事件载荷."""

    name: str
