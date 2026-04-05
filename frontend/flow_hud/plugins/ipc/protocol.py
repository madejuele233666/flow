from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Protocol

try:
    from flow_ipc import (
        ERR_DAEMON_OFFLINE,
        ERR_INTERNAL,
        ErrorObject,
        EVENT_SESSION_KEEPALIVE,
        HelloLimits,
        HelloResult,
        METHOD_SESSION_BYE,
        METHOD_SESSION_HELLO,
        METHOD_SESSION_PING,
        PROTOCOL_VERSION,
        PushFrame,
        RequestFrame,
        ResponseFrame,
        ROLE_PUSH,
        ROLE_RPC,
        TRANSPORT_TCP,
        TRANSPORT_UNIX,
        make_hello_params,
        parse_hello_result,
    )
except ModuleNotFoundError:
    shared_dir = Path(__file__).resolve().parents[4] / "shared"
    if str(shared_dir) not in sys.path:
        sys.path.insert(0, str(shared_dir))
    from flow_ipc import (  # type: ignore[no-redef]
        ERR_DAEMON_OFFLINE,
        ERR_INTERNAL,
        ErrorObject,
        EVENT_SESSION_KEEPALIVE,
        HelloLimits,
        HelloResult,
        METHOD_SESSION_BYE,
        METHOD_SESSION_HELLO,
        METHOD_SESSION_PING,
        PROTOCOL_VERSION,
        PushFrame,
        RequestFrame,
        ResponseFrame,
        ROLE_PUSH,
        ROLE_RPC,
        TRANSPORT_TCP,
        TRANSPORT_UNIX,
        make_hello_params,
        parse_hello_result,
    )


ERR_IPC_PROTOCOL_MISMATCH = "ERR_IPC_PROTOCOL_MISMATCH"
ERR_CONFIG_INVALID = "ERR_CONFIG_INVALID"


IpcWireRequest = RequestFrame
IpcWireResponse = ResponseFrame
IpcWirePush = PushFrame
IpcWireError = ErrorObject


class IpcClientProtocol(Protocol):
    """IPC plugin public boundary."""

    async def request(self, method: str, **params: Any) -> dict[str, Any]:
        ...


__all__ = [
    "ERR_CONFIG_INVALID",
    "ERR_DAEMON_OFFLINE",
    "ERR_INTERNAL",
    "ERR_IPC_PROTOCOL_MISMATCH",
    "EVENT_SESSION_KEEPALIVE",
    "HelloLimits",
    "HelloResult",
    "IpcClientProtocol",
    "IpcWireError",
    "IpcWirePush",
    "IpcWireRequest",
    "IpcWireResponse",
    "METHOD_SESSION_BYE",
    "METHOD_SESSION_HELLO",
    "METHOD_SESSION_PING",
    "PROTOCOL_VERSION",
    "ROLE_PUSH",
    "ROLE_RPC",
    "TRANSPORT_TCP",
    "TRANSPORT_UNIX",
    "make_hello_params",
    "parse_hello_result",
]
