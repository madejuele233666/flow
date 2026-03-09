import asyncio
import os
import json
import threading
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

# Mock PySide6 BEFORE importing anything that might use it
with patch.dict("sys.modules", {"PySide6": MagicMock(), "PySide6.QtCore": MagicMock()}):
    from flow_hud.plugins.ipc.plugin import IpcClientPlugin
    from flow_hud.plugins.context import HudAdminContext
    from flow_hud.core.events import HudEventType
    from flow_hud.plugins.ipc.protocol import ERR_DAEMON_OFFLINE, ERR_IPC_PROTOCOL_MISMATCH

class MockDaemon:
    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.server = None
        self.clients = set()

    async def start(self):
        self.server = await asyncio.start_unix_server(self.handle_client, path=self.socket_path)
        return self

    async def handle_client(self, reader, writer):
        self.clients.add(writer)
        try:
            while True:
                line = await reader.readline()
                if not line: break
                try:
                    req = json.loads(line.decode())
                    if req.get("type") == "request":
                        method = req.get("method")
                        if method == "bad_type":
                            resp = {"type": "not_a_response"}
                        elif method == "bad_id":
                            resp = {"type": "response", "id": "wrong_id", "result": "pong"}
                        else:
                            resp = {"type": "response", "id": req["id"], "result": "pong"}
                        writer.write((json.dumps(resp) + "\n").encode())
                        await writer.drain()
                except: break
        finally:
            if writer in self.clients:
                self.clients.remove(writer)
            writer.close()

    async def broadcast(self, event, data):
        push = {"type": "push", "event": event, "data": data}
        raw = (json.dumps(push) + "\n").encode()
        for c in list(self.clients):
            try:
                c.write(raw)
                await c.drain()
            except: pass

    async def stop(self):
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
    """Fixture providing a temporary Unix socket path."""
    return str(tmp_path / "test.sock")


@pytest.fixture
def plugin(socket_path):
    """Fixture to set up and tear down IpcClientPlugin."""
    p = IpcClientPlugin()
    mock_ctx = MagicMock(spec=HudAdminContext)
    mock_ctx.get_extension_config.return_value = {"socket_path": socket_path}
    p.setup(mock_ctx)
    yield p, mock_ctx
    p.teardown()


@pytest_asyncio.fixture
async def daemon(socket_path):
    """Fixture to set up and tear down MockDaemon."""
    d = MockDaemon(socket_path)
    await d.start()
    yield d
    await d.stop()


@pytest.mark.asyncio
async def test_ipc_request_response(plugin, daemon):
    p, mock_ctx = plugin
    res = await p.request("ping")
    assert res["ok"] is True
    assert res["result"] == "pong"


@pytest.mark.asyncio
async def test_ipc_daemon_offline(plugin):
    p, mock_ctx = plugin
    res = await p.request("ping")
    assert res["ok"] is False
    assert res["error_code"] == ERR_DAEMON_OFFLINE


@pytest.mark.asyncio
async def test_ipc_push_dispatch(plugin, daemon):
    p, mock_ctx = plugin
    await asyncio.sleep(1) # wait for connect
    await daemon.broadcast("timer.tick", {"tick": 999})
    await asyncio.sleep(1) # wait for dispatch
    mock_ctx.event_bus.emit_background.assert_called()
    call_args = mock_ctx.event_bus.emit_background.call_args
    assert call_args[0][0] == HudEventType.IPC_MESSAGE_RECEIVED
    assert call_args[0][1].tick == 999


@pytest.mark.asyncio
async def test_ipc_protocol_mismatch(plugin, daemon):
    p, mock_ctx = plugin
    res = await p.request("bad_type")
    assert res["ok"] is False
    assert res["error_code"] == ERR_IPC_PROTOCOL_MISMATCH


@pytest.mark.asyncio
async def test_ipc_request_id_mismatch(plugin, daemon):
    p, mock_ctx = plugin
    res = await p.request("bad_id")
    assert res["ok"] is False
    assert res["error_code"] == ERR_IPC_PROTOCOL_MISMATCH
    assert "mismatch" in res["message"].lower()

