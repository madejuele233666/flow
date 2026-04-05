from __future__ import annotations

import asyncio
from uuid import uuid4

from flow_hud.plugins.ipc import codec
from flow_hud.plugins.ipc.protocol import (
    HelloResult,
    IpcWireRequest,
    IpcWireResponse,
    METHOD_SESSION_HELLO,
    PROTOCOL_VERSION,
    make_hello_params,
    parse_hello_result,
)


class IpcProtocolError(RuntimeError):
    pass


async def negotiate_hello(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    role: str,
    transport: str,
    capabilities: list[str] | None = None,
    client_name: str = "flow-hud",
    client_version: str = "0.1.0",
) -> HelloResult:
    req = IpcWireRequest(
        id=uuid4().hex[:8],
        method=METHOD_SESSION_HELLO,
        params=make_hello_params(
            client_name=client_name,
            client_version=client_version,
            role=role,
            transport=transport,
            protocol_min=PROTOCOL_VERSION,
            protocol_max=PROTOCOL_VERSION,
            capabilities=capabilities,
        ),
    )
    req_bytes = codec.encode_message(req)
    writer.write(req_bytes)
    await writer.drain()

    line = await reader.readline()
    if not line:
        raise IpcProtocolError("empty hello response")

    try:
        resp = codec.decode_message(line)
    except Exception as exc:
        raise IpcProtocolError("malformed hello response frame") from exc
    if not isinstance(resp, IpcWireResponse):
        raise IpcProtocolError(f"hello expects response, got {type(resp).__name__}")
    if resp.error is not None:
        raise IpcProtocolError(f"hello failed [{resp.error.code}]: {resp.error.message}")
    try:
        hello = parse_hello_result(resp.result)
    except Exception as exc:
        raise IpcProtocolError(str(exc)) from exc
    if hello.protocol_version != PROTOCOL_VERSION:
        raise IpcProtocolError(
            f"hello protocol_version mismatch: expected {PROTOCOL_VERSION}, got {hello.protocol_version}"
        )
    if hello.role != role:
        raise IpcProtocolError(f"hello role mismatch: expected {role}, got {hello.role}")
    if hello.transport != transport:
        raise IpcProtocolError(f"hello transport mismatch: expected {transport}, got {hello.transport}")
    return hello
