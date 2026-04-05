"""IPC Server — Daemon 端的 asyncio stream 服务.

设计要点：
- 同时监听 Unix Domain Socket（CLI/TUI 本地使用）和 TCP 端口（HUD 跨系统使用）。
- 每个客户端连接对应一个独立的 asyncio Task，互不阻塞。
- 通过注入 handler_registry（方法名→处理函数映射表），实现请求路由。
- 支持 Push 广播：Daemon 的事件总线可通过 broadcast() 向所有活跃客户端（含 TCP）推送。
- 与 protocol.py 完全解耦：只负责传输，不关心消息语义。

     ┌──────────┐   Unix Socket   ┌──────────┐   TCP :54321   ┌─────────┐
     │ CLI/TUI  │ ◄─────────────► │  Server  │ ◄────────────► │   HUD   │
     │ (WSL)    │  ndjson lines   │ (Daemon) │  ndjson lines  │ (Win)   │
     └──────────┘                 └──────────┘                └─────────┘
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

from flow_engine.ipc.protocol import Push, Request, Response, decode, encode

logger = logging.getLogger(__name__)

# 默认 Socket 路径 — 放在用户数据目录下
DEFAULT_SOCKET_PATH = Path.home() / ".flow_engine" / "daemon.sock"

# 方法处理器类型：接收 params 字典，返回 result 或抛异常
MethodHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]


class IPCServer:
    """Daemon 端的 IPC 服务 — 管理连接、路由请求、广播推送.

    用法:
        server = IPCServer()
        server.register("task.start", handle_task_start)
        server.register("task.list", handle_task_list)
        await server.start()
        # ... 运行中 ...
        await server.stop()
    """

    DEFAULT_TCP_HOST = "127.0.0.1"
    DEFAULT_TCP_PORT = 54321

    def __init__(
        self,
        socket_path: Path | None = None,
        tcp_host: str = DEFAULT_TCP_HOST,
        tcp_port: int = DEFAULT_TCP_PORT,
    ) -> None:
        self._socket_path = socket_path or DEFAULT_SOCKET_PATH
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._handlers: dict[str, MethodHandler] = {}
        self._clients: set[asyncio.StreamWriter] = set()
        self._server: asyncio.AbstractServer | None = None
        self._tcp_server: asyncio.AbstractServer | None = None

    # ── 公共 API ──

    def register(self, method: str, handler: MethodHandler) -> None:
        """注册一个 RPC 方法处理器."""
        self._handlers[method] = handler
        logger.debug("IPC method registered: %s", method)

    async def start(self) -> None:
        """启动 Unix Domain Socket 和 TCP 双服务."""
        # ── Unix Domain Socket (CLI/TUI 本地使用) ──
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            self._socket_path.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_connection,
            path=str(self._socket_path),
        )
        logger.info("IPC server listening on %s", self._socket_path)

        # ── TCP (跨系统客户端，如 Windows HUD) ──
        self._tcp_server = await asyncio.start_server(
            self._handle_connection,
            host=self._tcp_host,
            port=self._tcp_port,
        )
        logger.info("IPC TCP server listening on %s:%d", self._tcp_host, self._tcp_port)

    async def stop(self) -> None:
        """优雅关闭服务（Unix Socket + TCP）."""
        if self._tcp_server:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        # 关闭所有客户端连接
        for writer in list(self._clients):
            writer.close()
        self._clients.clear()
        # 清理 Socket 文件
        if self._socket_path.exists():
            self._socket_path.unlink()
        logger.info("IPC server stopped")

    async def broadcast(self, push: Push) -> None:
        """向所有活跃客户端广播推送消息.

        用于 Daemon 事件总线将 TimerTick/StateChanged 推给 TUI。
        单个客户端写入失败不影响其余。
        """
        data = encode(push)
        dead: list[asyncio.StreamWriter] = []
        for writer in self._clients:
            try:
                writer.write(data)
                await writer.drain()
            except Exception:
                dead.append(writer)
        # 清理断开的连接
        for w in dead:
            self._clients.discard(w)

    # ── 内部实现 ──

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """处理单个客户端连接 — 逐行读取请求并回复."""
        self._clients.add(writer)
        peer = writer.get_extra_info("peername") or "unknown"
        logger.info("IPC client connected: %s", peer)

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break  # 客户端断开

                try:
                    msg = decode(line)
                except Exception as exc:
                    logger.warning("malformed IPC message: %s", exc)
                    continue

                if not isinstance(msg, Request):
                    logger.warning("expected Request, got %s", type(msg).__name__)
                    continue

                # 路由到注册的处理器
                response = await self._dispatch(msg)
                writer.write(encode(response))
                await writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("IPC connection error")
        finally:
            self._clients.discard(writer)
            writer.close()
            logger.info("IPC client disconnected: %s", peer)

    async def _dispatch(self, request: Request) -> Response:
        """路由请求到对应的 handler，返回 Response."""
        handler = self._handlers.get(request.method)
        if handler is None:
            return Response(
                id=request.id,
                error=f"unknown method: {request.method}",
            )
        try:
            result = await handler(request.params)
            return Response(id=request.id, result=result)
        except Exception as exc:
            logger.exception("handler %s failed", request.method)
            return Response(id=request.id, error=str(exc))
