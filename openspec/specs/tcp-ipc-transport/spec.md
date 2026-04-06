---
format: spec
version: 1.0.0
title: "跨端 TCP IPC 传输"
status: active
---

## Purpose
本规格定义了 Flow Engine 的跨网络 IPC 通信能力。通过允许 Daemon 并行监听 TCP 端口，支持像 Windows 原生 HUD 这样的客户端跨越操作系统边界（WSL ↔ Windows）与核心引擎交互，同时保持已有协议的兼容性。

## Requirements

### Requirement: TCP IPC 传输
Daemon 的 IPC 服务端 MUST 在 Unix Domain Socket 之外并行监听 TCP 端口，并且 TCP 连接 MUST 与 Unix 连接遵循同一套 IPC V2 协议握手与错误语义。

#### Scenario: Daemon 启动时同时监听 TCP
- **WHEN** Daemon 启动 IPC 服务
- **THEN** 它同时在 Unix Socket 和 TCP 端口（默认 `127.0.0.1:54321`）上接受连接

#### Scenario: TCP 连接先握手后通信
- **WHEN** HUD 通过 TCP 建立连接
- **THEN** 双端先完成 `session.hello` 协商，再允许 `task.*` 等业务请求
- **AND** 握手失败时返回结构化错误而不是自由文本

### Requirement: HUD 端 TCP 专用客户端
`flow_hud` 的 IPC 客户端 MUST 通过传输适配层支持 TCP 连接，并在跨系统场景优先使用 `asyncio.open_connection(host, port)`；客户端配置 MUST 保持可覆盖默认地址并具有确定性优先级。

#### Scenario: 连接到远程 Daemon
- **WHEN** HUD 在 Windows 宿主机启动并尝试连接 Daemon
- **THEN** 它通过 TCP 连接至配置中指定的 `host:port`（默认 `127.0.0.1:54321`）

#### Scenario: 连接地址可配置
- **WHEN** 用户在 `hud_config.toml` 中设置 `[connection] host = "192.168.1.100"` 和 `port = 9999`
- **THEN** HUD 连接至 `192.168.1.100:9999` 而非默认地址

#### Scenario: 配置优先级确定
- **WHEN** 同时存在默认值、配置文件值与运行时覆盖值
- **THEN** HUD 按固定优先级解析目标端点（运行时显式配置 > 环境变量 > 配置文件 > 默认值）

### Requirement: IPC 协议线格式兼容
TCP 与 Unix 两种传输 MUST 使用同一个共享 IPC 契约包完成编解码；HUD 端不得继续维护与 backend 独立演化的内联协议模型。

#### Scenario: 双传输一致解析
- **WHEN** 同一 V2 `Request` 帧分别通过 Unix 与 TCP 发送
- **THEN** Daemon 返回语义一致的 V2 `Response`，并保持相同错误码规则

#### Scenario: 协议版本不匹配
- **WHEN** HUD 与 Daemon 的 V2 版本协商失败
- **THEN** 握手阶段明确返回 `ERR_UNSUPPORTED_PROTOCOL` 或 `ERR_INVALID_FRAME` 并拒绝业务流量
