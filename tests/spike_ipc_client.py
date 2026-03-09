import sys
from unittest.mock import MagicMock

# Mock PySide6
mock_pyside6 = MagicMock()
sys.modules["PySide6"] = mock_pyside6
sys.modules["PySide6.QtCore"] = mock_pyside6.QtCore

import asyncio
import os
import json
import threading
import time
import logging
from typing import Any

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
from flow_hud.plugins.ipc.plugin import IpcClientPlugin
from flow_hud.core.events import HudEventType
from flow_hud.core.events_payload import IpcMessageReceivedPayload
from flow_hud.adapters.ipc_messages import TimerTickPayload

from flow_hud.plugins.context import HudAdminContext

# 模拟 HudAdminContext
class MockEventBus:
    def __init__(self):
        self.received_events = []
    
    def emit_background(self, event_type, payload):
        print(f"[EventBus] Emit Background: {event_type} -> {payload}")
        self.received_events.append((event_type, payload))

class MockConfig:
    def __init__(self, socket_path):
        self.extensions = {"ipc-client": {"socket_path": socket_path}}
        self.data_dir = "/tmp"
        self.safe_mode = False

class MockAdminContext(HudAdminContext):
    def __init__(self, socket_path):
        self.event_bus_mock = MockEventBus()
        self.config_mock = MockConfig(socket_path)
    
    @property
    def event_bus(self):
        return self.event_bus_mock

    def get_extension_config(self, name):
        return self.config_mock.extensions.get(name, {})

# 模拟 Daemon Server
clients = set()

async def mock_daemon_handler(reader, writer):
    print("[Daemon] New connection")
    clients.add(writer)
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            
            try:
                req = json.loads(line.decode())
                print(f"[Daemon] Received: {req}")
                
                if req.get("type") == "request":
                    # 简单响应
                    resp = {
                        "type": "response",
                        "id": req.get("id"),
                        "result": {"status": "ok", "echo": req.get("method")}
                    }
                    writer.write((json.dumps(resp) + "\n").encode())
                    await writer.drain()
            except Exception as e:
                print(f"[Daemon] Error: {e}")
                break
    finally:
        print("[Daemon] Connection closed")
        clients.remove(writer)
        writer.close()

async def run_mock_daemon(socket_path, stop_event):
    if os.path.exists(socket_path):
        os.remove(socket_path)
    
    server = await asyncio.start_unix_server(mock_daemon_handler, path=socket_path)
    print(f"[Daemon] Listening on {socket_path}")
    
    async with server:
        while not stop_event.is_set():
            await asyncio.sleep(0.5)
            # 广播推送
            if clients:
                push = {
                    "type": "push",
                    "event": "timer.tick",
                    "data": {"tick": int(time.time())}
                }
                data = (json.dumps(push) + "\n").encode()
                for writer in list(clients):
                    try:
                        writer.write(data)
                        await writer.drain()
                    except:
                        pass

    os.remove(socket_path)

def test_plugin():
    socket_path = "/tmp/mock_flow_daemon.sock"
    daemon_stop = threading.Event()
    
    # 启动 Daemon 线程
    def start_daemon():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_mock_daemon(socket_path, daemon_stop))
    
    daemon_thread = threading.Thread(target=start_daemon, daemon=True)
    daemon_thread.start()
    time.sleep(1) # 等待启动
    
    # 初始化插件
    plugin = IpcClientPlugin()
    ctx = MockAdminContext(socket_path)
    
    print("\n--- Testing Setup ---")
    plugin.setup(ctx)
    time.sleep(2) # 等待连接建立和一些推送
    
    print(f"Using socket path: {socket_path}")
    # RPC Test
    time.sleep(1)
    print("\n--- Testing Request ---")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(plugin.request("test.ping", value=42))
        print(f"Request Result: {result}")
    except Exception as e:
        print(f"Request Error: {e}")
        import traceback
        traceback.print_exc()
    
    time.sleep(1)
    
    print("\n--- Summary ---")
    print(f"Total events received: {len(ctx.event_bus.received_events)}")
    for ev_type, payload in ctx.event_bus.received_events:
        print(f" - {ev_type}: {payload}")

    print("\n--- Testing Teardown ---")
    plugin.teardown()
    daemon_stop.set()
    daemon_thread.join(timeout=2)
    print("Done.")

if __name__ == "__main__":
    test_plugin()
