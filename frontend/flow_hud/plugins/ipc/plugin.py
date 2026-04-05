from __future__ import annotations

import asyncio
import logging
import os
import random
import threading
import time
import uuid
from typing import Any

from flow_hud.adapters.ipc_messages import adapt_ipc_message
from flow_hud.core.events import HudEventType
from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.context import HudAdminContext
from flow_hud.plugins.ipc import codec
from flow_hud.plugins.ipc.protocol import (
    ERR_DAEMON_OFFLINE,
    ERR_INTERNAL,
    ERR_IPC_PROTOCOL_MISMATCH,
    IpcClientProtocol,
    IpcWirePush,
    IpcWireRequest,
    IpcWireResponse,
)
from flow_hud.plugins.manifest import HudPluginManifest

logger = logging.getLogger(__name__)


class IpcClientPlugin(HudPlugin, IpcClientProtocol):
    """IPC 客户端插件.
    
    负责与 Flow Engine Daemon 建立长连接，监听推送并转发到 HUD 事件总线。
    同时提供 request 接口供业务插件调用。
    """

    manifest = HudPluginManifest(
        name="ipc-client",
        version="0.1.0",
        description="Zero dependency IPC connection",
        config_schema={"socket_path": str},
    )

    def __init__(self) -> None:
        self._ctx: HudAdminContext | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._socket_path = ""

    def setup(self, ctx: HudAdminContext) -> None:
        """插件初始化."""
        # 安全检查是否具有特权属性
        if not isinstance(ctx, HudAdminContext):
            logger.error("IPC Client Plugin requires HudAdminContext")
            return

        self._ctx = ctx
        
        # 获取配置
        cfg = ctx.get_extension_config("ipc-client")
        self._socket_path = os.path.expanduser(
            cfg.get("socket_path", "~/.flow_engine/daemon.sock")
        )

        # 启动后台线程
        self._thread = threading.Thread(
            target=self._thread_entry,
            name="IpcClientTransport",
            daemon=True
        )
        self._thread.start()
        logger.info("IPC Client Plugin started (socket: %s)", self._socket_path)

    def teardown(self) -> None:
        """释放资源，确定性停止后台循环."""
        logger.info("Stopping IPC Client Plugin...")
        self._stop_event.set()
        
        if self._loop and self._loop.is_running():
            # 不要直接调用 self._loop.stop()，会引发 Event loop stopped before Future completed
            # 正确的做法是向循环发送任务取消信号
            if hasattr(self, '_main_task') and not getattr(self, '_main_task').done():
                self._loop.call_soon_threadsafe(getattr(self, '_main_task').cancel)
            
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            
        logger.info("IPC Client Plugin stopped.")

    async def request(self, method: str, **params: Any) -> dict[str, Any]:
        """发起 IPC 请求并返回标准化字典.
        
        采用瞬时连接，避免干扰长连接监听。
        """
        try:
            reader, writer = await asyncio.open_unix_connection(self._socket_path)
        except OSError as exc:
            return {
                "ok": False,
                "result": None,
                "error_code": ERR_DAEMON_OFFLINE,
                "message": f"Cannot connect to daemon: {exc}"
            }

        try:
            # 组装请求
            req_id = uuid.uuid4().hex[:8]
            req = IpcWireRequest(method=method, params=params, id=req_id)
            
            writer.write(codec.encode_message(req))
            await writer.drain()

            # 读取响应
            line = await reader.readline()
            if not line:
                return {
                    "ok": False,
                    "result": None,
                    "error_code": ERR_IPC_PROTOCOL_MISMATCH,
                    "message": "Empty response from daemon"
                }

            try:
                resp = codec.decode_message(line)
            except Exception as e:
                return {
                    "ok": False,
                    "result": None,
                    "error_code": ERR_IPC_PROTOCOL_MISMATCH,
                    "message": f"Failed to parse IPC message: {e}"
                }

            if not isinstance(resp, IpcWireResponse):
                return {
                    "ok": False,
                    "result": None,
                    "error_code": ERR_IPC_PROTOCOL_MISMATCH,
                    "message": f"Unexpected message type: {type(resp)}"
                }

            if resp.id != req_id:
                return {
                    "ok": False,
                    "result": None,
                    "error_code": ERR_IPC_PROTOCOL_MISMATCH,
                    "message": "Request ID mismatch"
                }

            return {
                "ok": resp.error is None,
                "result": resp.result,
                "error_code": resp.error,
                "message": None if resp.error is None else "Daemon returned error"
            }

        except Exception as exc:
            logger.exception("IPC request failed")
            return {
                "ok": False,
                "result": None,
                "error_code": ERR_INTERNAL,
                "message": str(exc)
            }
        finally:
            writer.close()
            await writer.wait_closed()

    # ── 内部实现 ──

    def _thread_entry(self) -> None:
        """子线程入口，维护 asyncio 循环."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._main_task = self._loop.create_task(self._listen_loop())
            self._loop.run_until_complete(self._main_task)
        except asyncio.CancelledError:
            pass # 正常取消
        except Exception:
            logger.exception("Unexpected error in IPC listen loop")
        finally:
            # 清理所有挂起的任务，确保 writer.close() 底层回调执行完
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
        """主监听循环（带 Exponential Backoff）."""
        backoff = 0.5
        max_backoff = 10.0

        while not self._stop_event.is_set():
            try:
                reader, writer = await asyncio.open_unix_connection(self._socket_path)
                backoff = 0.5  # 连接成功，重置退避
                logger.debug("IPC connected to %s", self._socket_path)

                try:
                    while not self._stop_event.is_set():
                        line = await reader.readline()
                        if not line:
                            break  # 连接断开
                        
                        try:
                            msg = codec.decode_message(line)
                            if isinstance(msg, IpcWirePush):
                                # 核心翻译逻辑
                                payload = adapt_ipc_message(msg.event, msg.data)
                                if self._ctx:
                                    self._ctx.event_bus.emit_background(
                                        HudEventType.IPC_MESSAGE_RECEIVED, 
                                        payload
                                    )
                        except Exception as exc:
                            logger.error("Failed to decode or dispatch IPC push: %s", exc)

                finally:
                    writer.close()
                    # 这里不用 wait_closed 因为可能已经在 stop 了

            except asyncio.CancelledError:
                break
            except OSError:
                if not self._stop_event.is_set():
                    logger.warning("Daemon offline, retrying in %.1fs...", backoff)
                    try:
                        await asyncio.wait_for(self._wait_for_stop_async(), timeout=backoff)
                    except asyncio.TimeoutError:
                        # 加入小幅随机抖动，防止多客户端同时重连引发惊群效应
                        jitter = random.uniform(0.0, 0.1 * backoff)
                        backoff = min(backoff * 1.5 + jitter, max_backoff)
            except Exception:
                if self._stop_event.is_set():
                    break
                logger.exception("Error in listen loop, retrying...")
                await asyncio.sleep(1)

    async def _wait_for_stop_async(self) -> None:
        """让异步循环能响应线程停止信号."""
        while not self._stop_event.is_set():
            await asyncio.sleep(0.1)
