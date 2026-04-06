from __future__ import annotations

import asyncio
import logging
import os
import random
import threading
import uuid
from typing import Any

from flow_hud.adapters.ipc_messages import adapt_ipc_message
from flow_hud.core.events import HudEventType
from flow_hud.ipc_settings import (
    DEFAULT_CONNECTION_HOST,
    DEFAULT_CONNECTION_PORT,
    IpcClientTuning,
    parse_ipc_client_tuning,
)
from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.context import HudAdminContext
from flow_hud.plugins.ipc import codec
from flow_hud.plugins.ipc.protocol import (
    EVENT_SESSION_KEEPALIVE,
    ERR_CONFIG_INVALID,
    ERR_DAEMON_OFFLINE,
    ERR_INTERNAL,
    ERR_IPC_PROTOCOL_MISMATCH,
    HelloLimits,
    IpcClientProtocol,
    IpcWirePush,
    IpcWireRequest,
    IpcWireResponse,
    ROLE_PUSH,
    ROLE_RPC,
    TRANSPORT_TCP,
    TRANSPORT_UNIX,
)
from flow_hud.plugins.ipc.session import IpcProtocolError, negotiate_hello
from flow_hud.plugins.ipc.transport import IpcEndpoint, SocketTransportAdapter
from flow_hud.plugins.manifest import HudPluginManifest

logger = logging.getLogger(__name__)

_DAEMON_SOCKET_ENV = "FLOW_DAEMON_SOCKET"
_DAEMON_HOST_ENV = "FLOW_DAEMON_HOST"
_DAEMON_PORT_ENV = "FLOW_DAEMON_PORT"
_DAEMON_TRANSPORT_ENV = "FLOW_DAEMON_TRANSPORT"


class IpcClientPlugin(HudPlugin, IpcClientProtocol):
    manifest = HudPluginManifest(
        name="ipc-client",
        version="0.2.0",
        description="V2 IPC client with transport/session/message boundaries",
        config_schema={
            "transport": str,
            "host": str,
            "port": int,
            "socket_path": str,
            "thread_join_timeout_s": float,
            "retry_initial_backoff_s": float,
            "retry_max_backoff_s": float,
            "retry_backoff_multiplier": float,
            "retry_backoff_jitter_ratio": float,
            "retry_error_sleep_s": float,
            "stop_poll_interval_s": float,
            "rpc_capabilities": list,
            "push_capabilities": list,
        },
    )

    def __init__(self) -> None:
        self._ctx: HudAdminContext | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._main_task: asyncio.Task | None = None
        self._endpoint: IpcEndpoint | None = None
        self._adapter = SocketTransportAdapter()
        self._limits: HelloLimits | None = None
        self._push_capabilities: set[str] = set()
        self._runtime_endpoint_override: dict[str, Any] = {}
        self._tuning = IpcClientTuning()

    def setup(self, ctx: HudAdminContext) -> None:
        if not isinstance(ctx, HudAdminContext):
            logger.error("IPC Client Plugin requires HudAdminContext")
            return
        self._ctx = ctx
        self._tuning = self._resolve_tuning(ctx)
        self._endpoint = self._resolve_endpoint(ctx)
        if self._endpoint is None:
            return

        self._thread = threading.Thread(target=self._thread_entry, name="IpcClientTransport", daemon=True)
        self._thread.start()
        logger.info(
            "IPC Client Plugin started (transport=%s host=%s port=%s socket=%s)",
            self._endpoint.transport,
            self._endpoint.host,
            self._endpoint.port,
            self._endpoint.socket_path,
        )

    def teardown(self) -> None:
        self._stop_event.set()
        if self._loop and self._loop.is_running() and self._main_task and not self._main_task.done():
            self._loop.call_soon_threadsafe(self._main_task.cancel)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._tuning.thread_join_timeout_s)
        logger.info("IPC Client Plugin stopped")

    def set_runtime_endpoint_override(self, **overrides: Any) -> None:
        """Set runtime-explicit endpoint overrides (highest precedence)."""
        self._runtime_endpoint_override = dict(overrides)

    async def request(self, method: str, **params: Any) -> dict[str, Any]:
        endpoint = self._endpoint
        if endpoint is None:
            return self._error(ERR_CONFIG_INVALID, "IPC endpoint is not configured")

        try:
            reader, writer = await self._adapter.open_connection(endpoint)
        except OSError as exc:
            return self._error(ERR_DAEMON_OFFLINE, f"Cannot connect to daemon: {exc}")

        try:
            hello = await negotiate_hello(
                reader,
                writer,
                role=ROLE_RPC,
                transport=endpoint.transport,
                capabilities=list(self._tuning.rpc_capabilities),
            )
            self._limits = hello.limits
            limits = hello.limits

            req_id = uuid.uuid4().hex[:8]
            req = IpcWireRequest(method=method, params=params, id=req_id)
            raw_request = codec.encode_message(req)
            self._enforce_outgoing_frame(raw_request, limits.max_frame_bytes)
            writer.write(raw_request)
            await writer.drain()

            timeout_ms = limits.request_timeout_ms
            line = await asyncio.wait_for(reader.readline(), timeout=timeout_ms / 1000.0)
            if not line:
                return self._error(ERR_IPC_PROTOCOL_MISMATCH, "Empty response from daemon")
            self._enforce_incoming_frame(line, limits.max_frame_bytes)

            resp = codec.decode_message(line)
            if not isinstance(resp, IpcWireResponse):
                return self._error(ERR_IPC_PROTOCOL_MISMATCH, f"Unexpected message type: {type(resp).__name__}")
            if resp.id != req_id:
                return self._error(ERR_IPC_PROTOCOL_MISMATCH, "Request ID mismatch")
            if resp.error is not None:
                return {
                    "ok": False,
                    "result": None,
                    "error_code": resp.error.code,
                    "message": resp.error.message,
                }
            return {"ok": True, "result": resp.result, "error_code": None, "message": None}
        except TimeoutError:
            return self._error(ERR_INTERNAL, "Request timeout waiting daemon response")
        except ValueError:
            return self._error(ERR_IPC_PROTOCOL_MISMATCH, "Malformed IPC response frame")
        except IpcProtocolError as exc:
            return self._error(ERR_IPC_PROTOCOL_MISMATCH, str(exc))
        except Exception as exc:
            logger.exception("IPC request failed")
            return self._error(ERR_INTERNAL, str(exc))
        finally:
            writer.close()
            await writer.wait_closed()

    def _thread_entry(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._main_task = self._loop.create_task(self._listen_loop())
            self._loop.run_until_complete(self._main_task)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Unexpected error in IPC listen loop")
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self._loop.close()

    async def _listen_loop(self) -> None:
        endpoint = self._endpoint
        if endpoint is None:
            return

        backoff = self._tuning.retry_initial_backoff_s
        max_backoff = self._tuning.retry_max_backoff_s

        while not self._stop_event.is_set():
            try:
                reader, writer = await self._adapter.open_connection(endpoint)
                hello = await negotiate_hello(
                    reader,
                    writer,
                    role=ROLE_PUSH,
                    transport=endpoint.transport,
                    capabilities=list(self._tuning.push_capabilities),
                )
                self._limits = hello.limits
                self._push_capabilities = set(hello.capabilities)
                limits = hello.limits
                missed_heartbeats = 0
                backoff = self._tuning.retry_initial_backoff_s

                try:
                    while not self._stop_event.is_set():
                        try:
                            line = await asyncio.wait_for(reader.readline(), timeout=limits.heartbeat_interval_ms / 1000.0)
                        except asyncio.TimeoutError:
                            missed_heartbeats += 1
                            if missed_heartbeats >= limits.heartbeat_miss_threshold:
                                raise IpcProtocolError(
                                    "push channel heartbeat timeout: reached heartbeat_miss_threshold"
                                )
                            continue
                        if not line:
                            raise IpcProtocolError("push channel closed by daemon")
                        self._enforce_incoming_frame(line, limits.max_frame_bytes)
                        msg = codec.decode_message(line)
                        if isinstance(msg, IpcWirePush):
                            missed_heartbeats = 0
                            if msg.event == EVENT_SESSION_KEEPALIVE:
                                continue
                            if msg.event == "timer.tick" and "push.timer" not in self._push_capabilities:
                                continue
                            payload = adapt_ipc_message(msg.event, msg.data)
                            if self._ctx:
                                self._ctx.event_bus.emit_background(HudEventType.IPC_MESSAGE_RECEIVED, payload)
                finally:
                    self._push_capabilities.clear()
                    writer.close()
                    await writer.wait_closed()
            except asyncio.CancelledError:
                break
            except (IpcProtocolError, ValueError) as exc:
                if self._stop_event.is_set():
                    break
                logger.warning("IPC protocol mismatch: %s", exc)
                await self._sleep_with_backoff(backoff)
                backoff = min(
                    backoff * self._tuning.retry_backoff_multiplier
                    + random.uniform(0.0, self._tuning.retry_backoff_jitter_ratio * backoff),
                    max_backoff,
                )
            except OSError:
                if not self._stop_event.is_set():
                    logger.warning("Daemon offline, retrying in %.1fs...", backoff)
                    await self._sleep_with_backoff(backoff)
                    backoff = min(
                        backoff * self._tuning.retry_backoff_multiplier
                        + random.uniform(0.0, self._tuning.retry_backoff_jitter_ratio * backoff),
                        max_backoff,
                    )
            except Exception:
                if self._stop_event.is_set():
                    break
                logger.exception("Error in listen loop, retrying...")
                await asyncio.sleep(self._tuning.retry_error_sleep_s)

    async def _sleep_with_backoff(self, backoff: float) -> None:
        try:
            await asyncio.wait_for(self._wait_for_stop_async(), timeout=backoff)
        except asyncio.TimeoutError:
            pass

    async def _wait_for_stop_async(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self._tuning.stop_poll_interval_s)

    def _resolve_endpoint(self, ctx: HudAdminContext) -> IpcEndpoint | None:
        cfg = ctx.get_extension_config("ipc-client")
        if not isinstance(cfg, dict):
            cfg = {}
        defaults = ctx.get_connection_config()
        if not isinstance(defaults, dict):
            defaults = {}
        runtime = self._runtime_endpoint_override

        transport = str(
            runtime.get("transport")
            or os.environ.get(_DAEMON_TRANSPORT_ENV)
            or cfg.get("transport")
            or defaults.get("transport")
            or TRANSPORT_TCP
        ).lower()

        host = str(
            runtime.get("host")
            or os.environ.get(_DAEMON_HOST_ENV)
            or cfg.get("host")
            or defaults.get("host")
            or DEFAULT_CONNECTION_HOST
        )
        port_raw = (
            runtime.get("port")
            or os.environ.get(_DAEMON_PORT_ENV)
            or cfg.get("port")
            or defaults.get("port")
            or DEFAULT_CONNECTION_PORT
        )
        socket_path = str(
            runtime.get("socket_path")
            or os.environ.get(_DAEMON_SOCKET_ENV)
            or cfg.get("socket_path")
            or defaults.get("socket_path")
            or ""
        )

        try:
            port = int(port_raw)
        except Exception:
            logger.error("Invalid IPC port: %r", port_raw)
            return None

        if transport == TRANSPORT_UNIX:
            if not socket_path:
                logger.error("IPC unix transport requires socket_path")
                return None
            return IpcEndpoint(transport=transport, host="", port=0, socket_path=os.path.expanduser(socket_path))

        if transport == TRANSPORT_TCP:
            return IpcEndpoint(transport=transport, host=host, port=port, socket_path="")

        logger.error("Unsupported IPC transport: %s", transport)
        return None

    def _resolve_tuning(self, ctx: HudAdminContext) -> IpcClientTuning:
        plugin_cfg = ctx.get_extension_config("ipc-client")
        defaults_getter = getattr(ctx, "get_ipc_client_config", None)
        defaults = defaults_getter() if callable(defaults_getter) else {}
        if not isinstance(plugin_cfg, dict):
            plugin_cfg = {}
        if not isinstance(defaults, dict):
            defaults = {}
        return parse_ipc_client_tuning(defaults=defaults, overrides=plugin_cfg)

    def _error(self, code: str, message: str) -> dict[str, Any]:
        return {"ok": False, "result": None, "error_code": code, "message": message}

    def _enforce_outgoing_frame(self, data: bytes, max_frame_bytes: int) -> None:
        if len(data) > max_frame_bytes:
            raise IpcProtocolError(
                f"outgoing frame exceeds negotiated max_frame_bytes ({len(data)} > {max_frame_bytes})"
            )

    def _enforce_incoming_frame(self, data: bytes, max_frame_bytes: int) -> None:
        if len(data) > max_frame_bytes:
            raise IpcProtocolError(
                f"incoming frame exceeds negotiated max_frame_bytes ({len(data)} > {max_frame_bytes})"
            )
