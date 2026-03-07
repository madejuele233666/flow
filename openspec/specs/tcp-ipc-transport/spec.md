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
Daemon 的 IPC 服务端必须在现有 Unix Domain Socket 之外，额外监听一个 TCP 端口，以便跨操作系统的客户端（如 Windows 上的 HUD）能够通过网络连接。

#### Scenario: Daemon 启动时同时监听 TCP
- **WHEN** Daemon 启动 IPC 服务
- **THEN** 它同时在 Unix Socket 和 TCP 端口（默认 `127.0.0.1:54321`）上接受连接

#### Scenario: TCP 连接兼容性
- **WHEN** HUD 客户端通过 TCP 发送一个 JSON-Lines 格式的 `Request` 消息
- **THEN** Daemon 返回一个格式完全相同的 `Response`，与 Unix Socket 模式下的行为一致

### Requirement: HUD 端 TCP 专用客户端
`flow_hud` 的 IPC 客户端必须使用 `asyncio.open_connection(host, port)` 建立 TCP 连接，而非 Unix Domain Socket。

#### Scenario: 连接到远程 Daemon
- **WHEN** HUD 在 Windows 宿主机启动并尝试连接 Daemon
- **THEN** 它通过 TCP 连接至配置中指定的 `host:port`（默认 `127.0.0.1:54321`）

#### Scenario: 连接地址可配置
- **WHEN** 用户在 `hud_config.toml` 中设置 `[connection] host = "192.168.1.100"` 和 `port = 9999`
- **THEN** HUD 连接至 `192.168.1.100:9999` 而非默认地址

### Requirement: IPC 协议线格式兼容
HUD 端内联的 `protocol.py` 必须与 Daemon 端的 `protocol.py` 保持完全相同的编解码格式，确保双端能够互相解析消息。

#### Scenario: 协议版本校验
- **WHEN** HUD 与 Daemon 的 `protocol.py` 编解码格式不一致
- **THEN** 连接握手阶段应能检测到版本不匹配并给出清晰错误提示
