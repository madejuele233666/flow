"""IPC server with Flow IPC V2 handshake, roles, and structured errors."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine
from uuid import uuid4

from flow_engine.ipc.protocol import (
    ERR_DAEMON_SHUTTING_DOWN,
    ERR_INTERNAL,
    ERR_INVALID_FRAME,
    ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
    ERR_REQUEST_TIMEOUT,
    ERR_ROLE_MISMATCH,
    ERR_UNSUPPORTED_PROTOCOL,
    EVENT_SESSION_CLOSING,
    EVENT_SESSION_KEEPALIVE,
    METHOD_SESSION_BYE,
    METHOD_SESSION_HELLO,
    METHOD_SESSION_PING,
    PROTOCOL_VERSION,
    Push,
    Request,
    ROLE_PUSH,
    ROLE_RPC,
    Response,
    TRANSPORT_TCP,
    TRANSPORT_UNIX,
    encode,
    frame_from_dict,
    make_hello_result,
    make_error,
    make_request,
    make_response,
    parse_hello_params,
)
from flow_engine.ipc.defaults import (
    IPC_DEFAULT_SOCKET_PATH,
    IPC_DEFAULT_HEARTBEAT_INTERVAL_MS,
    IPC_DEFAULT_HEARTBEAT_MISS_THRESHOLD,
    IPC_DEFAULT_MAX_FRAME_BYTES,
    IPC_DEFAULT_REQUEST_TIMEOUT_MS,
    IPC_DEFAULT_TCP_HOST,
    IPC_DEFAULT_TCP_PORT,
)

logger = logging.getLogger(__name__)

DEFAULT_SOCKET_PATH = IPC_DEFAULT_SOCKET_PATH

MethodHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]

_BASE_CAPABILITIES_BY_ROLE: dict[str, tuple[str, ...]] = {
    ROLE_RPC: ("rpc.task", "rpc.templates"),
    ROLE_PUSH: ("push.task_state",),
}

_OPTIONAL_CAPABILITIES_BY_ROLE: dict[str, tuple[str, ...]] = {
    ROLE_RPC: (),
    ROLE_PUSH: ("push.timer",),
}


@dataclass
class _ConnectionState:
    transport: str
    negotiated: bool = False
    role: str | None = None
    session_id: str | None = None
    seq: int = 0
    capabilities: list[str] = field(default_factory=list)


class IPCServer:
    """Daemon-side IPC server."""

    DEFAULT_TCP_HOST = IPC_DEFAULT_TCP_HOST
    DEFAULT_TCP_PORT = IPC_DEFAULT_TCP_PORT
    DEFAULT_MAX_FRAME_BYTES = IPC_DEFAULT_MAX_FRAME_BYTES
    DEFAULT_REQUEST_TIMEOUT_MS = IPC_DEFAULT_REQUEST_TIMEOUT_MS
    DEFAULT_HEARTBEAT_INTERVAL_MS = IPC_DEFAULT_HEARTBEAT_INTERVAL_MS
    DEFAULT_HEARTBEAT_MISS_THRESHOLD = IPC_DEFAULT_HEARTBEAT_MISS_THRESHOLD

    def __init__(
        self,
        socket_path: Path | None = None,
        tcp_host: str = DEFAULT_TCP_HOST,
        tcp_port: int = DEFAULT_TCP_PORT,
        *,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        request_timeout_ms: int = DEFAULT_REQUEST_TIMEOUT_MS,
        heartbeat_interval_ms: int = DEFAULT_HEARTBEAT_INTERVAL_MS,
        heartbeat_miss_threshold: int = DEFAULT_HEARTBEAT_MISS_THRESHOLD,
    ) -> None:
        self._socket_path = socket_path or DEFAULT_SOCKET_PATH
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._max_frame_bytes = max_frame_bytes
        self._request_timeout_ms = request_timeout_ms
        self._heartbeat_interval_ms = heartbeat_interval_ms
        self._heartbeat_miss_threshold = heartbeat_miss_threshold

        self._handlers: dict[str, MethodHandler] = {}
        self._states: dict[asyncio.StreamWriter, _ConnectionState] = {}
        self._server: asyncio.AbstractServer | None = None
        self._tcp_server: asyncio.AbstractServer | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        self._shutting_down = False

    @property
    def bound_tcp_port(self) -> int:
        """Actual bound TCP port (useful when initialized with port=0)."""
        if not self._tcp_server or not self._tcp_server.sockets:
            return self._tcp_port
        return int(self._tcp_server.sockets[0].getsockname()[1])

    def register(self, method: str, handler: MethodHandler) -> None:
        self._handlers[method] = handler
        logger.debug("IPC method registered: %s", method)

    async def start(self) -> None:
        self._shutting_down = False
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            self._socket_path.unlink()

        async def _handle_unix(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await self._handle_connection(reader, writer, TRANSPORT_UNIX)

        async def _handle_tcp(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await self._handle_connection(reader, writer, TRANSPORT_TCP)

        self._server = await asyncio.start_unix_server(_handle_unix, path=str(self._socket_path))
        self._tcp_server = await asyncio.start_server(
            _handle_tcp,
            host=self._tcp_host,
            port=self._tcp_port,
        )
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        logger.info("IPC server listening on %s and %s:%d", self._socket_path, self._tcp_host, self.bound_tcp_port)

    async def stop(self) -> None:
        self._shutting_down = True
        await self.broadcast(Push(event=EVENT_SESSION_CLOSING, data={"reason": "daemon_shutdown"}))
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            finally:
                self._keepalive_task = None

        if self._tcp_server:
            self._tcp_server.close()
            try:
                await asyncio.wait_for(self._tcp_server.wait_closed(), timeout=1.0)
            except TimeoutError:
                logger.warning("timeout while waiting tcp server close")
        if self._server:
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=1.0)
            except TimeoutError:
                logger.warning("timeout while waiting unix server close")

        for writer in list(self._states):
            writer.close()
        self._states.clear()

        if self._socket_path.exists():
            self._socket_path.unlink()
        logger.info("IPC server stopped")

    async def _keepalive_loop(self) -> None:
        if self._heartbeat_interval_ms <= 0:
            return
        interval_s = self._heartbeat_interval_ms / 1000.0
        try:
            while not self._shutting_down:
                await asyncio.sleep(interval_s)
                if self._shutting_down:
                    break
                await self.broadcast(Push(event=EVENT_SESSION_KEEPALIVE, data={}))
        except asyncio.CancelledError:
            return

    async def broadcast(self, push: Push, *, required_capability: str | None = None) -> None:
        dead: list[asyncio.StreamWriter] = []
        for writer, state in list(self._states.items()):
            if not state.negotiated or state.role != ROLE_PUSH:
                continue
            if required_capability and required_capability not in state.capabilities:
                continue
            try:
                state.seq += 1
                meta = dict(push.meta or {})
                meta["session_id"] = state.session_id
                meta["seq"] = state.seq
                enriched = Push(event=push.event, data=push.data, meta=meta)
                writer.write(encode(enriched))
                await writer.drain()
            except Exception:
                dead.append(writer)
        for writer in dead:
            self._states.pop(writer, None)

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        transport: str,
    ) -> None:
        state = _ConnectionState(transport=transport)
        self._states[writer] = state
        peer = writer.get_extra_info("peername") or "unknown"
        logger.info("IPC client connected: %s (%s)", peer, transport)

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                if len(line) > self._max_frame_bytes:
                    await self._send_error(writer, None, ERR_INVALID_FRAME, "frame too large", retryable=False)
                    break

                parsed = self._parse_line(line)
                if parsed is None:
                    break
                raw, frame = parsed

                if not isinstance(frame, Request):
                    await self._send_error(
                        writer,
                        raw.get("id") if isinstance(raw, dict) else None,
                        ERR_INVALID_FRAME,
                        "incoming client frame must be request",
                        retryable=False,
                    )
                    break
                if frame.method == "invalid.frame":
                    await self._send_error(
                        writer,
                        frame.id,
                        ERR_INVALID_FRAME,
                        "invalid frame payload",
                        retryable=False,
                    )
                    break

                if not state.negotiated:
                    response, should_close = self._handle_pre_handshake(frame, state)
                    writer.write(encode(response))
                    await writer.drain()
                    if should_close:
                        break
                    continue

                response, should_close = await self._handle_request(frame, state)
                writer.write(encode(response))
                await writer.drain()
                if should_close:
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("IPC connection error")
        finally:
            self._states.pop(writer, None)
            writer.close()
            logger.info("IPC client disconnected: %s", peer)

    def _parse_line(self, line: bytes) -> tuple[dict[str, Any], Request | Response | Push] | None:
        try:
            raw = json.loads(line.decode("utf-8").strip())
        except Exception:
            logger.warning("invalid json frame, closing connection")
            return None
        if not isinstance(raw, dict):
            logger.warning("frame must be object, closing connection")
            return None
        try:
            frame = frame_from_dict(raw)
        except Exception as exc:
            logger.warning("invalid frame: %s", exc)
            req_id = raw.get("id")
            if isinstance(req_id, str) and req_id:
                return raw, make_request("invalid.frame", {}, req_id=req_id)
            return None
        return raw, frame

    def _handle_pre_handshake(self, request: Request, state: _ConnectionState) -> tuple[Response, bool]:
        if request.method != METHOD_SESSION_HELLO:
            return (
                make_response(
                    request.id,
                    error=make_error(
                        ERR_INVALID_FRAME,
                        "session.hello must be the first request",
                        retryable=False,
                    ),
                ),
                True,
            )
        return self._negotiate_hello(request, state)

    def _negotiate_hello(self, request: Request, state: _ConnectionState) -> tuple[Response, bool]:
        try:
            hello = parse_hello_params(request.params)
        except Exception as exc:
            return make_response(
                request.id,
                error=make_error(ERR_INVALID_FRAME, str(exc), retryable=False),
            ), True
        if hello.role not in {ROLE_RPC, ROLE_PUSH}:
            return make_response(
                request.id,
                error=make_error(ERR_ROLE_MISMATCH, f"unsupported role: {hello.role}", retryable=False),
            ), True
        if hello.transport not in {TRANSPORT_UNIX, TRANSPORT_TCP} or hello.transport != state.transport:
            return make_response(
                request.id,
                error=make_error(ERR_ROLE_MISMATCH, f"transport mismatch: {hello.transport}", retryable=False),
            ), True
        if hello.protocol_min > hello.protocol_max or not (hello.protocol_min <= PROTOCOL_VERSION <= hello.protocol_max):
            return make_response(
                request.id,
                error=make_error(
                    ERR_UNSUPPORTED_PROTOCOL,
                    f"requested protocol range {hello.protocol_min}..{hello.protocol_max} not supported",
                    retryable=False,
                    data={"supported_min": PROTOCOL_VERSION, "supported_max": PROTOCOL_VERSION},
                ),
            ), True

        accepted_capabilities = self._resolve_session_capabilities(hello.role, hello.capabilities)
        state.negotiated = True
        state.role = hello.role
        state.session_id = f"sess_{uuid4().hex[:12]}"
        state.capabilities = accepted_capabilities

        result = make_hello_result(
            session_id=state.session_id,
            protocol_version=PROTOCOL_VERSION,
            server_name="flow-engine",
            server_version="0.1.0",
            role=hello.role,
            transport=state.transport,
            max_frame_bytes=self._max_frame_bytes,
            request_timeout_ms=self._request_timeout_ms,
            heartbeat_interval_ms=self._heartbeat_interval_ms,
            heartbeat_miss_threshold=self._heartbeat_miss_threshold,
            capabilities=accepted_capabilities,
        )
        return make_response(request.id, result=result), False

    def _resolve_session_capabilities(self, role: str, requested: list[str]) -> list[str]:
        accepted = list(_BASE_CAPABILITIES_BY_ROLE.get(role, ()))
        optional = set(_OPTIONAL_CAPABILITIES_BY_ROLE.get(role, ()))
        for capability in requested:
            if capability in optional and capability not in accepted:
                accepted.append(capability)
        return accepted

    async def _handle_request(self, request: Request, state: _ConnectionState) -> tuple[Response, bool]:
        if request.method == METHOD_SESSION_PING:
            return make_response(request.id, result={"pong": True}), False
        if request.method == METHOD_SESSION_BYE:
            return make_response(request.id, result={"bye": True}), True

        if state.role == ROLE_PUSH:
            return (
                make_response(
                    request.id,
                    error=make_error(
                        ERR_ROLE_MISMATCH,
                        "business methods are not allowed on push role",
                        retryable=False,
                    ),
                ),
                False,
            )

        if self._shutting_down:
            return (
                make_response(
                    request.id,
                    error=make_error(
                        ERR_DAEMON_SHUTTING_DOWN,
                        "daemon is shutting down",
                        retryable=True,
                    ),
                ),
                False,
            )

        handler = self._handlers.get(request.method)
        if handler is None:
            return (
                make_response(
                    request.id,
                    error=make_error(
                        ERR_METHOD_NOT_FOUND,
                        f"unknown method: {request.method}",
                        retryable=False,
                    ),
                ),
                False,
            )

        try:
            timeout = self._request_timeout_ms / 1000.0
            result = await asyncio.wait_for(handler(request.params), timeout=timeout)
            return make_response(request.id, result=result), False
        except TimeoutError:
            return (
                make_response(
                    request.id,
                    error=make_error(
                        ERR_REQUEST_TIMEOUT,
                        f"request timeout after {self._request_timeout_ms}ms",
                        retryable=True,
                    ),
                ),
                False,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return (
                make_response(
                    request.id,
                    error=make_error(
                        ERR_INVALID_PARAMS,
                        str(exc),
                        retryable=False,
                    ),
                ),
                False,
            )
        except Exception as exc:
            logger.exception("handler %s failed", request.method)
            return (
                make_response(
                    request.id,
                    error=make_error(
                        ERR_INTERNAL,
                        "internal handler error",
                        retryable=False,
                        data={"detail": str(exc)},
                    ),
                ),
                False,
            )

    async def _send_error(
        self,
        writer: asyncio.StreamWriter,
        req_id: str | None,
        code: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        if not req_id:
            return
        response = make_response(req_id, error=make_error(code, message, retryable=retryable))
        writer.write(encode(response))
        await writer.drain()
