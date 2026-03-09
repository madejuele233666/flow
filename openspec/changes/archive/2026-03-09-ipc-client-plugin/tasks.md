## 1. [CORE] 领域事件载荷定义

- [x] 1.1 在 `flow_hud/core/events_payload.py` 中，定义 `IpcMessageReceivedPayload`，标注为 `@dataclass(frozen=True)`。当无对应强类型映射时做兜底使用。包含字段：`method: str` 和 `data: dict[str, Any]`。
  【防腐规定】This file MUST NOT import `PySide6` 或主引擎相关的 `flow_engine` 具体依赖模块。
- [x] 1.2 创建 `flow_hud/adapters/ipc_messages.py`，定义一系列具体的事件强类型模型，使用 `@dataclass(frozen=True)` 确保不可变。
- [x] 1.3 在 `flow_hud/adapters/ipc_messages.py` 中实现 `def adapt_ipc_message(method: str, data: dict[str, Any]) -> object` 函数。它是唯一允许硬编码 JSON Field string 提取的地方。如果无法匹配对应方法，则返回 `IpcMessageReceivedPayload` 兜底。
  【防腐规定】This file MUST NOT import `flow_engine`。它是阻止下游对字典由于 key 的变更而大面积重构的防火墙。
- [x] 1.4 【检查点】 Present `events_payload.py` and `ipc_messages.py` definitions to the user for review. MUST obtain explicit user confirmation before proceeding to the next phase.

## 2. [CORE] 领域错误契约、Wire模型与 `IpcClientProtocol`

- [x] 2.1 创建 `flow_hud/plugins/ipc/protocol.py`，定义底层 IPC JSON 消息对应的 Wire 数据类：`IpcWireRequest` / `IpcWireResponse` / `IpcWirePush`，并记录传输与解析的领域错误码常量（例如 `ERR_DAEMON_OFFLINE = "ERR_DAEMON_OFFLINE"`，`ERR_IPC_PROTOCOL = "ERR_IPC_PROTOCOL_MISMATCH"` 等）。
- [x] 2.2 在同一个文件 `flow_hud/plugins/ipc/protocol.py` 中，定义 `IpcClientProtocol(Protocol)` 类。该 Protocol 是 `IpcClientPlugin` 对 HUD 内部其他组件暴露的**唯一外部契约**。
  要求：包含方法 `async def request(self, method: str, **params: Any) -> dict[str, Any]`
  契约标准：其返回的字典格式必须是强规范化：`{"ok": bool, "result": Any | None, "error_code": str | None, "message": str | None}`，禁止直接泄露底层 Python 报错对象。
  【防腐规定】This file MUST NOT import `flow_engine`、`PySide6` 或任何具体插件类。只允许标准库导入。
- [x] 2.3 创建 `flow_hud/plugins/ipc/codec.py`，实现 `encode_message()` 和 `decode_message()` 函数，采用 newline-delimited JSON 格式编解码 wire 模型。
- [x] 2.4 【检查点】 Present domain error constants, wire classes, codec and `IpcClientProtocol` definition to the user for review. MUST obtain explicit user confirmation before proceeding to the next phase.

## 3. [CORE] IpcClientPlugin 插件实现（微服务零依赖级解耦）

- [x] 3.1 创建 `flow_hud/plugins/ipc/__init__.py` 确保目录为合法的包结构。
- [x] 3.2 创建 `flow_hud/plugins/ipc/plugin.py`，实现 `IpcClientPlugin(HudPlugin, IpcClientProtocol)` 类。携带元数据：`HudPluginManifest(name="ipc-client", version="0.1.0", description="Zero dependency IPC connection", config_schema={"socket_path": str})`。
  【防腐规定】本文件决不通过 `import flow_engine` 引入外部传输框架实现。只使用原生 `asyncio` 和 `json`。
- [x] 3.3 在 `IpcClientPlugin.__init__` 中创建停止信号和 loop 引用：
  - `self._stop_event: threading.Event = threading.Event()`
  - `self._loop: asyncio.AbstractEventLoop | None = None`
  - `self._thread: threading.Thread | None = None`
  - `self._socket_path: str = ""`
- [x] 3.4 在 `IpcClientPlugin` 中实现 `setup(self, ctx: HudAdminContext)`。该方法需要安全检查 ctx 是否具有 `event_bus` 等特权属性。并动态获取套接字绑定 `self._socket_path = os.path.expanduser(ctx.get_extension_config("ipc-client").get("socket_path", "~/.flow_engine/daemon.sock"))`。
- [x] 3.5 在 `setup` 内部创建并启动 `threading.Thread(target=self._thread_entry, daemon=True)` 以容纳网络通信所在的子线程。
- [x] 3.6 实现 `_thread_entry(self)` 方法：
  ```python
  def _thread_entry(self) -> None:
      self._loop = asyncio.new_event_loop()
      asyncio.set_event_loop(self._loop)
      try:
          self._loop.run_until_complete(self._listen_loop())
      finally:
          self._loop.close()
  ```
- [x] 3.7 实现无依赖的底层异步方法 `_listen_loop(self)`：
  1. 采用 Exponential Backoff 重试机制。在每次 sleep 前及循环入口检查 `self._stop_event.is_set()`。
  2. 使用 `reader, _ = await asyncio.open_unix_connection(self._socket_path)` 手写建立流通道。如果连接异常触发 Backoff。
  3. 执行 `while True: line = await reader.readline()` 读取裸协议数据流。
  4. 使用 `codec.decode_message` 解析得到 `IpcWirePush` 实例，若解析失败则丢弃或打日志。
  5. 调用 `payload = adapt_ipc_message(push.event, push.data)`，将其转化为对应的强数据类。
  6. 调用 `self._ctx.event_bus.emit_background(HudEventType.IPC_MESSAGE_RECEIVED, payload)` 分发到后台处理。
- [x] 3.8 实现 `teardown()` 确定性停止逻辑：
  ```python
  def teardown(self) -> None:
      self._stop_event.set()                                        # (1) 设置跨线程停止信号
      if self._loop and not self._loop.is_closed():                  # (2) 安全中断 asyncio loop
          self._loop.call_soon_threadsafe(self._loop.stop)
      if self._thread and self._thread.is_alive():                   # (3) 等待线程完全退出
          self._thread.join(timeout=5.0)
  ```
- [x] 3.9 实现 `request(self, method: str, **params: Any) -> dict[str, Any]` 方法：
  1. 契约符合 `IpcClientProtocol` 字典返回标准。
  2. 实现隔离式网络交互：“双客户端组装” —— 发出请求时手书极简瞬时连接： `asyncio.open_unix_connection(self._socket_path)`。
  3. 创建 `IpcWireRequest` 实例，转换为字典后使用 `codec.encode_message()` 获取 bytes 直接传入 `writer.write()`，并 `await writer.drain()`。
  4. 获取一行反馈 `await reader.readline()`，使用 `codec.decode_message()` 解析出 `IpcWireResponse`，将其转换并返回强规范字典 `{"ok": True, "result": ...}` 等。
  5. **错误精准转译**：针对 `ConnectionError` 转译为 `ERR_DAEMON_OFFLINE`字典输出；解析错误映射为字典 `ERR_IPC_PROTOCOL_MISMATCH`；其余错误兜底。从而阻绝 Python 底层栈污染业务插件决策层。
- [x] 3.10 【检查点】 结合写好的纯 Python 桩，Present `tests/spike_ipc_client.py` run output（测试无外部依赖的推送消费与方法响应转译）。 MUST obtain explicit user confirmation before proceeding to the next phase.

## 4. [EDGE] CLI/Registry 验证

- [x] 4.1 修改/创建对应的 `tests/test_ipc_client_plugin.py` 集成验证：
  - 不需要前置导入 `flow_engine` 包。使用一个假冒的简易 `asyncio.start_unix_server` 扮演引擎即可。
  - 测试套接字重置、`ERR_DAEMON_OFFLINE` 断线转译。
  - 获取 `teardown()` 可在预期 timeout 时间内结束（即停止信号安全传递阻断异步流）。
- [x] 4.2 确认主配置文件存在相应示例：`admin_plugins = ["ipc-client"]`。
