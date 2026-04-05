"""IPC Client — CLI/TUI 端的瘦连接器.

设计要点：
- 同一个 Client 类同时服务 CLI（一次性请求）和 TUI（长连接 + 监听推送）。
- connect() → call() → close() 的清晰生命周期。
- listen_pushes() 异步生成器：TUI 用它持续消费 Daemon 的广播推送。
- 与传输层完全解耦：只使用 protocol.py 的 encode/decode。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from flow_engine.ipc.protocol import Push, Request, Response, decode, encode
from flow_engine.ipc.server import DEFAULT_SOCKET_PATH

logger = logging.getLogger(__name__)


class IPCClient:
    """瘦客户端 — 连接 Daemon 的 Unix Domain Socket.

    用法 (CLI 一次性请求):
        async with IPCClient() as client:
            result = await client.call("task.list")

    用法 (TUI 长连接):
        client = IPCClient()
        await client.connect()
        async for push in client.listen_pushes():
            render(push)
    """

    def __init__(self, socket_path: Path | None = None) -> None:
        self._socket_path = socket_path or DEFAULT_SOCKET_PATH
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    # ── 生命周期 ──

    async def connect(self) -> None:
        """建立到 Daemon 的连接."""
        if not self._socket_path.exists():
            raise ConnectionError(
                f"Daemon 未运行: socket 文件不存在 ({self._socket_path})\n"
                "请先运行: flow daemon start"
            )
        self._reader, self._writer = await asyncio.open_unix_connection(
            str(self._socket_path),
        )
        logger.debug("connected to daemon at %s", self._socket_path)

    async def close(self) -> None:
        """断开连接."""
        if self._writer:
            self._writer.close()
            self._writer = None
            self._reader = None

    async def __aenter__(self) -> IPCClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ── 请求/响应 (CLI 用) ──

    async def call(self, method: str, **params: Any) -> Any:
        """发送 RPC 请求并等待回复.

        Args:
            method: 远程方法名。
            **params: 方法参数。

        Returns:
            Daemon 返回的 result 值。

        Raises:
            ConnectionError: 未连接。
            RuntimeError: Daemon 返回了错误。
        """
        if not self._writer or not self._reader:
            raise ConnectionError("not connected to daemon")

        request = Request(method=method, params=params)
        self._writer.write(encode(request))
        await self._writer.drain()

        line = await self._reader.readline()
        if not line:
            raise ConnectionError("daemon closed connection")

        msg = decode(line)
        if not isinstance(msg, Response):
            raise RuntimeError(f"expected Response, got {type(msg).__name__}")

        if not msg.ok:
            raise RuntimeError(f"daemon error: {msg.error}")

        return msg.result

    # ── 推送监听 (TUI 用) ──

    async def listen_pushes(self) -> AsyncIterator[Push]:
        """持续监听 Daemon 的推送消息 — 异步生成器.

        TUI 使用此方法在事件循环中持续接收 TimerTick 等广播：
            async for push in client.listen_pushes():
                if push.event == "timer.tick":
                    update_timer_display(push.data)
        """
        if not self._reader:
            raise ConnectionError("not connected to daemon")

        while True:
            line = await self._reader.readline()
            if not line:
                break  # Daemon 断开

            try:
                msg = decode(line)
                if isinstance(msg, Push):
                    yield msg
                elif isinstance(msg, Response):
                    # 在 listen 模式下收到 Response 是不期望的，忽略
                    logger.debug("unexpected Response during listen: %s", msg.id)
            except Exception as exc:
                logger.warning("malformed push message: %s", exc)
