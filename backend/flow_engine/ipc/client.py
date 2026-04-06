"""IPC client with V2 hello-first session negotiation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from flow_engine.ipc.protocol import (
    HelloLimits,
    METHOD_SESSION_HELLO,
    METHOD_SESSION_PING,
    PROTOCOL_VERSION,
    Push,
    Request,
    ROLE_PUSH,
    ROLE_RPC,
    Response,
    TRANSPORT_UNIX,
    decode,
    encode,
    make_hello_params,
    make_request,
    parse_hello_result,
)
from flow_engine.ipc.defaults import IPC_DEFAULT_REQUEST_TIMEOUT_MS, IPC_DEFAULT_SOCKET_PATH

logger = logging.getLogger(__name__)


class IPCClient:
    """Client connector for daemon IPC."""

    def __init__(self, socket_path: Path | None = None) -> None:
        self._socket_path = socket_path or IPC_DEFAULT_SOCKET_PATH
        self._rpc_reader: asyncio.StreamReader | None = None
        self._rpc_writer: asyncio.StreamWriter | None = None
        self._push_reader: asyncio.StreamReader | None = None
        self._push_writer: asyncio.StreamWriter | None = None
        self._limits: HelloLimits | None = None

    async def connect(self) -> None:
        if not self._socket_path.exists():
            raise ConnectionError(
                f"Daemon 未运行: socket 文件不存在 ({self._socket_path})\n"
                "请先运行: flow daemon start"
            )
        self._rpc_reader, self._rpc_writer = await asyncio.open_unix_connection(str(self._socket_path))
        await self._hello(self._rpc_reader, self._rpc_writer, role=ROLE_RPC, transport=TRANSPORT_UNIX)
        logger.debug("connected to daemon at %s", self._socket_path)

    async def close(self) -> None:
        await self._close_writer(self._push_writer)
        await self._close_writer(self._rpc_writer)
        self._push_reader = None
        self._push_writer = None
        self._rpc_reader = None
        self._rpc_writer = None

    async def __aenter__(self) -> IPCClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def call(self, method: str, **params: Any) -> Any:
        if not self._rpc_writer or not self._rpc_reader:
            raise ConnectionError("not connected to daemon")

        timeout_ms = self._limits.request_timeout_ms if self._limits else IPC_DEFAULT_REQUEST_TIMEOUT_MS
        request = make_request(method, params)
        self._rpc_writer.write(encode(request))
        await self._rpc_writer.drain()

        try:
            line = await asyncio.wait_for(self._rpc_reader.readline(), timeout=timeout_ms / 1000.0)
        except TimeoutError as exc:
            raise RuntimeError(f"daemon error: request timeout after {timeout_ms}ms") from exc
        if not line:
            raise ConnectionError("daemon closed connection")

        msg = decode(line)
        if not isinstance(msg, Response):
            raise RuntimeError(f"expected Response, got {type(msg).__name__}")
        if msg.error is not None:
            raise RuntimeError(f"daemon error [{msg.error.code}]: {msg.error.message}")
        return msg.result

    async def ping(self) -> bool:
        result = await self.call(METHOD_SESSION_PING)
        return isinstance(result, dict) and result.get("pong") is True

    async def listen_pushes(self) -> AsyncIterator[Push]:
        await self._ensure_push_channel()
        if not self._push_reader:
            raise ConnectionError("push channel unavailable")

        while True:
            line = await self._push_reader.readline()
            if not line:
                break
            try:
                msg = decode(line)
                if isinstance(msg, Push):
                    yield msg
            except Exception as exc:
                logger.warning("malformed push message: %s", exc)

        await self._close_writer(self._push_writer)
        self._push_reader = None
        self._push_writer = None

    async def _ensure_push_channel(self) -> None:
        if self._push_reader and self._push_writer:
            return
        if not self._socket_path.exists():
            raise ConnectionError(f"daemon socket not found: {self._socket_path}")
        self._push_reader, self._push_writer = await asyncio.open_unix_connection(str(self._socket_path))
        await self._hello(self._push_reader, self._push_writer, role=ROLE_PUSH, transport=TRANSPORT_UNIX)

    async def _hello(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        role: str,
        transport: str,
    ) -> None:
        hello_params = make_hello_params(
            client_name="flow-engine-client",
            client_version="0.1.0",
            role=role,
            transport=transport,
            protocol_min=PROTOCOL_VERSION,
            protocol_max=PROTOCOL_VERSION,
            capabilities=[],
        )
        request = make_request(METHOD_SESSION_HELLO, hello_params)
        writer.write(encode(request))
        await writer.drain()

        line = await reader.readline()
        if not line:
            raise ConnectionError("daemon closed connection during hello")
        msg = decode(line)
        if not isinstance(msg, Response):
            raise ConnectionError(f"hello expects response, got {type(msg).__name__}")
        if msg.error is not None:
            raise ConnectionError(f"hello failed [{msg.error.code}]: {msg.error.message}")
        hello = parse_hello_result(msg.result)
        if hello.protocol_version != PROTOCOL_VERSION:
            raise ConnectionError(
                f"hello protocol_version mismatch: expected {PROTOCOL_VERSION}, got {hello.protocol_version}"
            )
        if hello.role != role:
            raise ConnectionError(f"hello role mismatch: expected {role}, got {hello.role}")
        if hello.transport != transport:
            raise ConnectionError(f"hello transport mismatch: expected {transport}, got {hello.transport}")
        self._limits = hello.limits

    async def _close_writer(self, writer: asyncio.StreamWriter | None) -> None:
        if writer is None:
            return
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
