from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# 领域错误码 (Domain Error Codes)
# ---------------------------------------------------------------------------

ERR_DAEMON_OFFLINE = "ERR_DAEMON_OFFLINE"
ERR_IPC_PROTOCOL_MISMATCH = "ERR_IPC_PROTOCOL_MISMATCH"
ERR_INTERNAL = "ERR_INTERNAL"


# ---------------------------------------------------------------------------
# Wire 模型 (Wire Models) - 对应 JSON-RPC 报文结构
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IpcWireRequest:
    """IPC 请求包."""
    method: str
    params: dict[str, Any]
    id: str
    type: str = "request"


@dataclass(frozen=True)
class IpcWireResponse:
    """IPC 响应包."""
    id: str
    result: Any = None
    error: str | None = None
    type: str = "response"


@dataclass(frozen=True)
class IpcWirePush:
    """IPC 推送包."""
    event: str
    data: dict[str, Any]
    type: str = "push"


# ---------------------------------------------------------------------------
# IpcClientProtocol (边界隔离契约)
# ---------------------------------------------------------------------------

class IpcClientProtocol(Protocol):
    """IPC 插件对外暴露的唯一契约.
    
    业务插件应依赖此 Protocol 而非 IpcClientPlugin 具体的实现。
    """

    async def request(self, method: str, **params: Any) -> dict[str, Any]:
        """发起 IPC 请求并等待响应.
        
        返回值字典格式规范:
        {
            "ok": bool,
            "result": Any | None,
            "error_code": str | None,
            "message": str | None
        }
        """
        ...
