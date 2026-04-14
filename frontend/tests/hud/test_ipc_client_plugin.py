from __future__ import annotations

import asyncio
import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

# Mock PySide6 BEFORE importing anything that might use it
with patch.dict("sys.modules", {"PySide6": MagicMock(), "PySide6.QtCore": MagicMock()}):
    from flow_hud.core.events import HudEventType
    from flow_hud.core.events_payload import IpcConnectionStatusPayload
    from flow_hud.plugins.context import HudAdminContext
    from flow_hud.plugins.ipc.protocol import ERR_DAEMON_OFFLINE, ERR_IPC_PROTOCOL_MISMATCH
    from flow_hud.plugins.ipc.plugin import IpcClientPlugin


def _hello_result(role: str, transport: str) -> dict:
    return {
        "session_id": "sess_test",
        "protocol_version": 2,
        "server": {"name": "flow-engine", "version": "0.1.0"},
        "role": role,
        "transport": transport,
        "capabilities": [],
        "limits": {
            "max_frame_bytes": 65536,
            "request_timeout_ms": 10000,
            "heartbeat_interval_ms": 3000,
            "heartbeat_miss_threshold": 2,
        },
    }


class MockDaemon:
    def __init__(
        self,
        socket_path: str,
        *,
        transport: str = "unix",
        host: str = "127.0.0.1",
        port: int = 0,
    ):
        self.socket_path = socket_path
        self.transport = transport
        self.host = host
        self.port = port
        self.bound_port = port
        self.server: asyncio.AbstractServer | None = None
        self.clients: set[asyncio.StreamWriter] = set()
        self.roles: dict[asyncio.StreamWriter, str] = {}
        self.hello_count_by_role: dict[str, int] = {"rpc": 0, "push": 0}
        self.push_hello_times: list[float] = []
        self.request_timeout_ms = 10000
        self.max_frame_bytes = 65536
        self.heartbeat_interval_ms = 3000
        self.heartbeat_miss_threshold = 2
        self.hello_protocol_version_override: int | None = None
        self.hello_role_override: str | None = None
        self.hello_transport_override: str | None = None
        self.respond_to_hello = True
        self.silent_methods: set[str] = set()

    async def start(self) -> MockDaemon:
        if self.transport == "unix":
            self.server = await asyncio.start_unix_server(self.handle_client, path=self.socket_path)
        else:
            self.server = await asyncio.start_server(self.handle_client, host=self.host, port=self.port)
            if self.server.sockets:
                self.bound_port = int(self.server.sockets[0].getsockname()[1])
        return self

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.clients.add(writer)
        hello_done = False
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                req = json.loads(line.decode())
                if req.get("type") != "request":
                    continue
                method = req.get("method")

                if not hello_done:
                    if method != "session.hello":
                        resp = {
                            "v": 2,
                            "type": "response",
                            "id": req.get("id", "unknown"),
                            "result": None,
                            "error": {
                                "code": "ERR_INVALID_FRAME",
                                "message": "hello required",
                                "retryable": False,
                                "data": None,
                            },
                        }
                    else:
                        if not self.respond_to_hello:
                            continue
                        role = req["params"]["role"]
                        self.roles[writer] = role
                        self.hello_count_by_role[role] = self.hello_count_by_role.get(role, 0) + 1
                        if role == "push":
                            self.push_hello_times.append(asyncio.get_running_loop().time())
                        hello_done = True
                        result = _hello_result(role, self.transport)
                        result["capabilities"] = list(req["params"].get("capabilities", []))
                        result["limits"]["request_timeout_ms"] = self.request_timeout_ms
                        result["limits"]["max_frame_bytes"] = self.max_frame_bytes
                        result["limits"]["heartbeat_interval_ms"] = self.heartbeat_interval_ms
                        result["limits"]["heartbeat_miss_threshold"] = self.heartbeat_miss_threshold
                        if self.hello_protocol_version_override is not None:
                            result["protocol_version"] = self.hello_protocol_version_override
                        if self.hello_role_override is not None:
                            result["role"] = self.hello_role_override
                        if self.hello_transport_override is not None:
                            result["transport"] = self.hello_transport_override
                        resp = {
                            "v": 2,
                            "type": "response",
                            "id": req["id"],
                            "result": result,
                            "error": None,
                        }
                    writer.write((json.dumps(resp) + "\n").encode())
                    await writer.drain()
                    continue

                if method in self.silent_methods:
                    continue
                if method == "bad_type":
                    resp = {"v": 2, "type": "push", "event": "unexpected", "data": {}}
                elif method == "bad_id":
                    resp = {"v": 2, "type": "response", "id": "wrong_id", "result": "pong", "error": None}
                elif method == "slow":
                    await asyncio.sleep(0.05)
                    resp = {"v": 2, "type": "response", "id": req["id"], "result": "pong", "error": None}
                elif method == "bad_json":
                    writer.write(b"{bad-json\n")
                    await writer.drain()
                    continue
                else:
                    resp = {"v": 2, "type": "response", "id": req["id"], "result": "pong", "error": None}
                writer.write((json.dumps(resp) + "\n").encode())
                await writer.drain()
        finally:
            self.roles.pop(writer, None)
            if writer in self.clients:
                self.clients.remove(writer)
            writer.close()

    async def broadcast(self, event: str, data: dict) -> None:
        push = {"v": 2, "type": "push", "event": event, "data": data}
        raw = (json.dumps(push) + "\n").encode()
        for c in list(self.clients):
            if self.roles.get(c) != "push":
                continue
            try:
                c.write(raw)
                await c.drain()
            except Exception:
                pass

    async def close_push_clients(self) -> None:
        for c in list(self.clients):
            if self.roles.get(c) != "push":
                continue
            try:
                c.close()
            except Exception:
                pass

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            for c in list(self.clients):
                try:
                    c.close()
                except Exception:
                    pass
            await self.server.wait_closed()


@pytest.fixture
def socket_path(tmp_path):
    return str(tmp_path / "test.sock")


@pytest.fixture
def plugin(socket_path):
    p, mock_ctx = _create_plugin(socket_path)
    yield p, mock_ctx
    p.teardown()


@pytest_asyncio.fixture
async def daemon(socket_path):
    d = MockDaemon(socket_path)
    await d.start()
    yield d
    await d.stop()


def _create_plugin(socket_path: str, **extension_config):
    p = IpcClientPlugin()
    mock_ctx = MagicMock(spec=HudAdminContext)
    mock_ctx.get_extension_config.return_value = {
        "transport": "unix",
        "socket_path": socket_path,
        **extension_config,
    }
    mock_ctx.get_connection_config.return_value = {
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": 54321,
        "socket_path": "",
    }
    p.setup(mock_ctx)
    return p, mock_ctx


@pytest.mark.asyncio
async def test_ipc_request_response(plugin, daemon):
    p, _ = plugin
    res = await p.request("ping")
    assert res["ok"] is True
    assert res["result"] == "pong"


@pytest.mark.asyncio
async def test_ipc_daemon_offline(plugin):
    p, _ = plugin
    res = await p.request("ping")
    assert res["ok"] is False
    assert res["error_code"] == ERR_DAEMON_OFFLINE


@pytest.mark.asyncio
async def test_ipc_push_dispatch(plugin, daemon):
    p, mock_ctx = plugin
    await asyncio.sleep(1.2)
    await daemon.broadcast("timer.tick", {"tick": 999})
    await asyncio.sleep(0.8)
    mock_ctx.event_bus.emit_background.assert_called()
    call_args = mock_ctx.event_bus.emit_background.call_args
    assert call_args[0][0] == HudEventType.IPC_MESSAGE_RECEIVED
    assert call_args[0][1].tick == 999


@pytest.mark.asyncio
async def test_ipc_push_connect_emits_connection_established(plugin, daemon):
    _, mock_ctx = plugin
    await asyncio.sleep(1.2)

    mock_ctx.event_bus.emit_background.assert_any_call(
        HudEventType.IPC_CONNECTION_ESTABLISHED,
        IpcConnectionStatusPayload(connected=True),
    )


@pytest.mark.asyncio
async def test_ipc_push_disconnect_emits_connection_lost(plugin, daemon):
    _, mock_ctx = plugin
    await asyncio.sleep(0.3)
    await daemon.stop()
    await asyncio.sleep(0.4)

    mock_ctx.event_bus.emit_background.assert_any_call(
        HudEventType.IPC_CONNECTION_LOST,
        IpcConnectionStatusPayload(connected=False),
    )


@pytest.mark.asyncio
async def test_ipc_protocol_mismatch(plugin, daemon):
    p, _ = plugin
    res = await p.request("bad_type")
    assert res["ok"] is False
    assert res["error_code"] == ERR_IPC_PROTOCOL_MISMATCH


@pytest.mark.asyncio
async def test_ipc_request_id_mismatch(plugin, daemon):
    p, _ = plugin
    res = await p.request("bad_id")
    assert res["ok"] is False
    assert res["error_code"] == ERR_IPC_PROTOCOL_MISMATCH
    assert "mismatch" in res["message"].lower()


@pytest.mark.asyncio
async def test_request_timeout_uses_negotiated_limit(plugin, daemon):
    p, _ = plugin
    daemon.request_timeout_ms = 10
    res = await p.request("slow")
    assert res["ok"] is False
    assert "timeout" in res["message"].lower()


@pytest.mark.asyncio
async def test_hello_timeout_returns_without_hanging(socket_path):
    daemon = MockDaemon(socket_path)
    daemon.respond_to_hello = False
    await daemon.start()

    plugin, _ = _create_plugin(socket_path, hello_timeout_s=0.05, request_timeout_cap_s=0.2)
    try:
        start = time.monotonic()
        res = await plugin.request("status")
        elapsed = time.monotonic() - start
        assert res["ok"] is False
        assert "timeout" in res["message"].lower()
        assert "hello" in res["message"].lower()
        assert elapsed < 0.5
    finally:
        plugin.teardown()
        await daemon.stop()


@pytest.mark.asyncio
async def test_request_timeout_cap_limits_silent_status_response(socket_path):
    daemon = MockDaemon(socket_path)
    daemon.request_timeout_ms = 10000
    daemon.silent_methods.add("status")
    await daemon.start()

    plugin, _ = _create_plugin(socket_path, hello_timeout_s=0.05, request_timeout_cap_s=0.05)
    try:
        start = time.monotonic()
        res = await plugin.request("status")
        elapsed = time.monotonic() - start
        assert res["ok"] is False
        assert "timeout" in res["message"].lower()
        assert elapsed < 0.5
    finally:
        plugin.teardown()
        await daemon.stop()


@pytest.mark.asyncio
async def test_malformed_response_maps_to_protocol_mismatch(plugin, daemon):
    p, _ = plugin
    res = await p.request("bad_json")
    assert res["ok"] is False
    assert res["error_code"] == ERR_IPC_PROTOCOL_MISMATCH
    assert res["message"] == "Malformed IPC response frame"


@pytest.mark.asyncio
async def test_hello_success_payload_mismatch_maps_to_protocol_mismatch(plugin, daemon):
    p, _ = plugin
    daemon.hello_protocol_version_override = 999
    res = await p.request("ping")
    assert res["ok"] is False
    assert res["error_code"] == ERR_IPC_PROTOCOL_MISMATCH
    assert "protocol_version mismatch" in res["message"]


@pytest.mark.asyncio
async def test_max_frame_bytes_uses_negotiated_limit(plugin, daemon):
    p, _ = plugin
    daemon.max_frame_bytes = 120
    res = await p.request("ping", payload=("x" * 300))
    assert res["ok"] is False
    assert res["error_code"] == ERR_IPC_PROTOCOL_MISMATCH
    assert "max_frame_bytes" in res["message"]


@pytest.mark.asyncio
async def test_push_heartbeat_timeout_triggers_rehello(socket_path):
    daemon = MockDaemon(socket_path)
    daemon.heartbeat_interval_ms = 50
    daemon.heartbeat_miss_threshold = 1
    await daemon.start()

    plugin = IpcClientPlugin()
    mock_ctx = MagicMock(spec=HudAdminContext)
    mock_ctx.get_extension_config.return_value = {"transport": "unix", "socket_path": socket_path}
    mock_ctx.get_connection_config.return_value = {
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": 54321,
        "socket_path": "",
    }
    plugin.setup(mock_ctx)
    try:
        await asyncio.sleep(0.7)
        assert daemon.hello_count_by_role.get("push", 0) >= 2
    finally:
        plugin.teardown()
        await daemon.stop()


@pytest.mark.asyncio
async def test_push_eof_disconnect_uses_backoff_rehello(socket_path):
    daemon = MockDaemon(socket_path)
    await daemon.start()

    plugin = IpcClientPlugin()
    mock_ctx = MagicMock(spec=HudAdminContext)
    mock_ctx.get_extension_config.return_value = {"transport": "unix", "socket_path": socket_path}
    mock_ctx.get_connection_config.return_value = {
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": 54321,
        "socket_path": "",
    }
    plugin.setup(mock_ctx)
    try:
        await asyncio.sleep(0.25)
        await daemon.close_push_clients()
        await asyncio.sleep(0.9)
        assert len(daemon.push_hello_times) >= 2
        assert daemon.push_hello_times[1] - daemon.push_hello_times[0] >= 0.18
    finally:
        plugin.teardown()
        await daemon.stop()


def test_endpoint_resolution_env_overrides_plugin_and_defaults():
    p = IpcClientPlugin()
    ctx = MagicMock(spec=HudAdminContext)
    ctx.get_extension_config.return_value = {
        "transport": "unix",
        "socket_path": "/tmp/plugin.sock",
        "host": "8.8.8.8",
        "port": 9999,
    }
    ctx.get_connection_config.return_value = {
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": 54321,
        "socket_path": "/tmp/default.sock",
    }
    with patch.dict(
        os.environ,
        {
            "FLOW_DAEMON_TRANSPORT": "tcp",
            "FLOW_DAEMON_HOST": "10.0.0.1",
            "FLOW_DAEMON_PORT": "7777",
            "FLOW_DAEMON_SOCKET": "/tmp/env.sock",
        },
        clear=False,
    ):
        endpoint = p._resolve_endpoint(ctx)
    assert endpoint is not None
    assert endpoint.transport == "tcp"
    assert endpoint.host == "10.0.0.1"
    assert endpoint.port == 7777


def test_endpoint_resolution_env_overrides_defaults():
    p = IpcClientPlugin()
    ctx = MagicMock(spec=HudAdminContext)
    ctx.get_extension_config.return_value = {}
    ctx.get_connection_config.return_value = {
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": 54321,
        "socket_path": "",
    }
    with patch.dict(
        os.environ,
        {
            "FLOW_DAEMON_TRANSPORT": "tcp",
            "FLOW_DAEMON_HOST": "10.1.1.9",
            "FLOW_DAEMON_PORT": "7001",
        },
        clear=False,
    ):
        endpoint = p._resolve_endpoint(ctx)
    assert endpoint is not None
    assert endpoint.transport == "tcp"
    assert endpoint.host == "10.1.1.9"
    assert endpoint.port == 7001


def test_endpoint_resolution_runtime_override_has_highest_priority():
    p = IpcClientPlugin()
    p.set_runtime_endpoint_override(transport="unix", socket_path="/tmp/runtime.sock")
    ctx = MagicMock(spec=HudAdminContext)
    ctx.get_extension_config.return_value = {
        "transport": "tcp",
        "host": "8.8.8.8",
        "port": 9999,
        "socket_path": "/tmp/plugin.sock",
    }
    ctx.get_connection_config.return_value = {
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": 54321,
        "socket_path": "/tmp/default.sock",
    }
    with patch.dict(
        os.environ,
        {
            "FLOW_DAEMON_TRANSPORT": "tcp",
            "FLOW_DAEMON_HOST": "10.1.1.9",
            "FLOW_DAEMON_PORT": "7001",
            "FLOW_DAEMON_SOCKET": "/tmp/env.sock",
        },
        clear=False,
    ):
        endpoint = p._resolve_endpoint(ctx)
    assert endpoint is not None
    assert endpoint.transport == "unix"
    assert endpoint.socket_path == "/tmp/runtime.sock"


@pytest.mark.asyncio
async def test_ipc_request_response_over_tcp():
    daemon = MockDaemon("", transport="tcp", host="127.0.0.1", port=0)
    await daemon.start()
    plugin = IpcClientPlugin()
    mock_ctx = MagicMock(spec=HudAdminContext)
    mock_ctx.get_extension_config.return_value = {
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": daemon.bound_port,
    }
    mock_ctx.get_connection_config.return_value = {
        "transport": "tcp",
        "host": "127.0.0.1",
        "port": daemon.bound_port,
        "socket_path": "",
    }
    plugin.setup(mock_ctx)
    try:
        res = await plugin.request("ping")
        assert res["ok"] is True
        assert res["result"] == "pong"
    finally:
        plugin.teardown()
        await daemon.stop()
