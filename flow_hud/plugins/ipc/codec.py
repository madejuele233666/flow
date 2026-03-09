from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from flow_hud.plugins.ipc.protocol import IpcWirePush, IpcWireRequest, IpcWireResponse


def encode_message(msg: IpcWireRequest | IpcWireResponse | IpcWirePush) -> bytes:
    """按行分隔 JSON 格式编码消息."""
    payload = asdict(msg)
    # 确保没有换行符干扰协议边界
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def decode_message(data: bytes) -> IpcWireRequest | IpcWireResponse | IpcWirePush:
    """解码行分隔 JSON 消息.
    
    Raises:
        ValueError: 如果 JSON 格式错误或缺少 type 字段。
        KeyError: 如果缺少必要的协议字段。
    """
    raw = json.loads(data.decode("utf-8").strip())
    msg_type = raw.get("type")

    if msg_type == "request":
        return IpcWireRequest(
            method=raw["method"],
            params=raw.get("params", {}),
            id=raw["id"]
        )
    elif msg_type == "response":
        return IpcWireResponse(
            id=raw["id"],
            result=raw.get("result"),
            error=raw.get("error")
        )
    elif msg_type == "push":
        return IpcWirePush(
            event=raw["event"],
            data=raw.get("data", {})
        )
    else:
        raise ValueError(f"Unknown IPC message type: {msg_type}")
