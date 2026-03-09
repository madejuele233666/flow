## Why

在完成了 HUD V2 架构的防腐层与沙盒体系（`hud-v2-architecture` 及相关 hardening 变更）后，HUD 目前是一个线程安全但完全孤立的系统，缺乏“耳朵”。我们需要让 HUD 重新连接到主引擎 (`flow_engine`)，使其能够感知主引擎的状态变化，接收指令，并向主引擎发送请求。为了保持架构的纯净度与解耦性，HUD 需要通过一个独立的插件（`IpcClientPlugin`）来管理与主引擎的 IPC（Unix Domain Socket）长连接。

参考主引擎的解耦模式并追求**极致解耦（Ultimate Decoupling）**，我们应当将传输层的细节（Socket、连接重试、JSON-RPC 的序列化/反序列化）完全封装在插件内部。并且，为了达到微服务级别的物理防腐，我们**彻底摒弃对 `flow_engine` 代码库的导入依赖（Share Nothing）**。

## What Changes

- 开发 `flow_hud/plugins/ipc/` 模块，作为与主引擎通信的专属插件。
- 采用微服务级别的**零代码依赖隔离**，不在 HUD 中引入 `flow_engine.ipc.protocol.py` 或 `IPCClient`，而是以原生 Python 标准库（`asyncio`, `json`）实现一个约 50 行的极简 JSON-RPC 客户端。
- **配置驱动的通道**：不硬编码通讯地址，通过插件机制的 `config_schema` 属性从配置中注入 `socket_path`。
- 实现支持长连接的异步通信循环，监听注入的 socket 地址，处理推送流（Push 类型的消息）。
- 接收到推送后，将其转化为强类型数据（例如实例化 `IpcMessageReceivedPayload`），并通过 `ctx.admin_ctx.event_bus.emit_background()` 分发到后台事件总线。
- 在服务断开时具备自动重连机制（Exponential Backoff）。
- **制定领域自治错误码**，确保内部错误字典格式一致，不会导致外部组件依赖底层 `ConnectionError` 等 Python 原生异常。

## Capabilities

### New Capabilities
- `ipc-client`: 定义 HUD 侧对主引擎 IPC 连接的建立、维持、解析与后台事件的分发逻辑，提供纯净的控制请求通道。

### Modified Capabilities
- 

## Impact

- 核心架构保持不变，依然遵循防腐层与双权沙盒规则。
- HUD 能够作为一个真正自治的应用独立运行和启动，即便没有安装 `flow_engine` 的 Python 环境亦可部署。
- 其他视觉或业务插件现在可以订阅 `IPC_MESSAGE_RECEIVED` 事件，从而根据主引擎的状态做出响应，并通过错误码规避对传输故障原因的直接耦合。
- 通过在后台线程建立异步事件循环，将不阻塞 Qt 主事件循环。
