"""IPC 消息协议 — JSON-RPC 风格的请求/响应/推送格式.

设计要点：
- 借鉴 JSON-RPC 2.0 但更精简：无 batch 支持，无复杂嵌套。
- 三种消息类型：Request (CLI→Daemon), Response (Daemon→CLI), Push (Daemon→TUI)。
- 全部消息以 newline-delimited JSON 传输（每行一个完整 JSON 对象）。
- 与传输层完全解耦：只关心序列化/反序列化，不关心是 Socket 还是 WebSocket。

用法:
    req = Request(method="task.start", params={"task_id": 1})
    wire = encode(req)  # bytes
    msg = decode(wire)  # Request | Response | Push
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 消息类型
# ---------------------------------------------------------------------------

class MessageType(str, Enum):
    """三种 IPC 消息类型."""

    REQUEST = "request"     # Client → Daemon: 请求执行某操作
    RESPONSE = "response"   # Daemon → Client: 对 Request 的回复
    PUSH = "push"           # Daemon → Client: 主动推送（如 TimerTick）


# ---------------------------------------------------------------------------
# 消息数据结构
# ---------------------------------------------------------------------------

@dataclass
class Request:
    """客户端请求 — method + params 风格（类 JSON-RPC）.

    Attributes:
        id: 唯一请求 ID，用于匹配 Response。
        method: 远程方法名（如 "task.start", "task.list"）。
        params: 方法参数字典。
    """

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex[:8])

    @property
    def msg_type(self) -> MessageType:
        return MessageType.REQUEST


@dataclass
class Response:
    """Daemon 回复 — 一定对应一个 Request.id.

    Attributes:
        id: 对应的 Request ID。
        result: 成功时的返回值。
        error: 失败时的错误信息（与 result 互斥）。
    """

    id: str
    result: Any = None
    error: str | None = None

    @property
    def msg_type(self) -> MessageType:
        return MessageType.RESPONSE

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class Push:
    """Daemon 主动推送 — 无 ID，无需回复.

    Attributes:
        event: 推送事件名（如 "timer.tick", "task.state_changed"）。
        data: 事件数据。
    """

    event: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def msg_type(self) -> MessageType:
        return MessageType.PUSH


# ---------------------------------------------------------------------------
# 编解码 — newline-delimited JSON
# ---------------------------------------------------------------------------

def encode(msg: Request | Response | Push) -> bytes:
    """将消息序列化为传输格式（一行 JSON + 换行符）."""
    payload: dict[str, Any] = {"type": msg.msg_type.value}
    payload.update(asdict(msg))
    return (json.dumps(payload, ensure_ascii=False, default=str) + "\n").encode("utf-8")


def decode(data: bytes) -> Request | Response | Push:
    """将传输格式反序列化为消息对象.

    Raises:
        ValueError: 未知的消息类型或格式错误。
    """
    raw = json.loads(data.decode("utf-8").strip())
    msg_type = raw.pop("type", None)

    if msg_type == MessageType.REQUEST.value:
        return Request(
            method=raw["method"],
            params=raw.get("params", {}),
            id=raw.get("id", ""),
        )
    elif msg_type == MessageType.RESPONSE.value:
        return Response(
            id=raw["id"],
            result=raw.get("result"),
            error=raw.get("error"),
        )
    elif msg_type == MessageType.PUSH.value:
        return Push(
            event=raw["event"],
            data=raw.get("data", {}),
        )
    else:
        raise ValueError(f"unknown IPC message type: {msg_type}")
