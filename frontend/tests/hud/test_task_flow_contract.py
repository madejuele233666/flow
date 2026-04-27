from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from flow_hud.plugins.context import HudAdminContext
from flow_hud.plugins.ipc.plugin import IpcClientPlugin


def _hello_result() -> dict:
    return {
        "session_id": "sess-task-flow",
        "protocol_version": 2,
        "server": {"name": "flow-engine", "version": "0.1.0"},
        "role": "rpc",
        "transport": "unix",
        "capabilities": [],
        "limits": {
            "max_frame_bytes": 65536,
            "request_timeout_ms": 10000,
            "heartbeat_interval_ms": 3000,
            "heartbeat_miss_threshold": 2,
        },
    }


class TaskFlowDaemon:
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self.server: asyncio.AbstractServer | None = None
        self.clients: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        self.server = await asyncio.start_unix_server(self.handle_client, path=self.socket_path)

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            for client in list(self.clients):
                client.close()
            await self.server.wait_closed()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.clients.add(writer)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                req = json.loads(line.decode())
                if req.get("method") == "session.hello":
                    resp = {
                        "v": 2,
                        "type": "response",
                        "id": req["id"],
                        "result": _hello_result(),
                        "error": None,
                    }
                elif req.get("method") == "status":
                    resp = {
                        "v": 2,
                        "type": "response",
                        "id": req["id"],
                        "result": {
                            "active": {
                                "id": 7,
                                "title": "deep work",
                                "priority": 1,
                                "state": "In Progress",
                                "duration_min": 12,
                            },
                            "break_suggested": True,
                        },
                        "error": None,
                    }
                elif req.get("method") == "task.start":
                    resp = {
                        "v": 2,
                        "type": "response",
                        "id": req["id"],
                        "result": {
                            "id": 7,
                            "title": "deep work",
                            "state": "In Progress",
                            "paused": [3],
                            "restore_report": {
                                "version": 2,
                                "task_id": 7,
                                "overall_status": "skipped",
                                "execution_enabled": False,
                                "actions": [
                                    {
                                        "id": "active_url:0",
                                        "type": "open_url",
                                        "field": "active_url",
                                        "role": "active",
                                        "target": "https://example.com",
                                        "status": "skipped",
                                        "reason": "execution_disabled",
                                        "source": "derived_aw_last_browser_segment",
                                        "priority": "best_effort",
                                    }
                                ],
                                "browser_session": {
                                    "active_url": "https://example.com",
                                    "browser_session_source": "derived_aw_last_browser_segment",
                                },
                                "user_message": None,
                            },
                        },
                        "error": None,
                    }
                else:
                    resp = {
                        "v": 2,
                        "type": "response",
                        "id": req["id"],
                        "result": {"pong": True},
                        "error": None,
                    }
                writer.write((json.dumps(resp) + "\n").encode())
                await writer.drain()
        finally:
            self.clients.discard(writer)
            writer.close()
            await writer.wait_closed()


def test_hud_ipc_plugin_preserves_canonical_task_flow_payloads(tmp_path) -> None:
    async def scenario() -> None:
        app = QApplication.instance() or QApplication([])
        assert app is not None

        socket_path = str(tmp_path / "daemon.sock")
        daemon = TaskFlowDaemon(socket_path)
        await daemon.start()

        plugin = IpcClientPlugin()
        ctx = MagicMock(spec=HudAdminContext)
        ctx.get_extension_config.return_value = {"transport": "unix", "socket_path": socket_path}
        ctx.get_connection_config.return_value = {
            "transport": "unix",
            "host": "127.0.0.1",
            "port": 0,
            "socket_path": socket_path,
        }
        plugin.setup(ctx)

        try:
            status = await plugin.request("status")
            assert status["ok"] is True
            assert status["result"]["active"]["duration_min"] == 12
            assert status["result"]["break_suggested"] is True

            start = await plugin.request("task.start", task_id=7)
            assert start["ok"] is True
            assert start["result"]["paused"] == [3]
            assert start["result"]["restore_report"]["version"] == 2
            assert start["result"]["restore_report"]["actions"][0]["target"] == "https://example.com"
            assert start["result"]["state"] == "In Progress"
        finally:
            await daemon.stop()
            plugin.teardown()

    asyncio.run(scenario())
