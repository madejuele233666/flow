---
format: proposal
version: 1.0.0
title: "HUD 独立仓库分离 — 跨平台双端部署"
status: draft
---

## Why

HUD 原型的渲染层（PySide6 + pynput）深度依赖原生操作系统的窗口合成器（毛玻璃、全局鼠标钩子、点击穿透），而这些能力在 WSL 环境中完全失效。用户实际的工作场景是 **Daemon 运行在 WSL (Linux)**、**HUD 运行在 Windows 宿主机上**。当前 HUD 代码嵌套在 `flow_engine/hud/` 内部，与引擎同一个 Python 包和依赖环境，无法独立部署。此外，现有 IPC 基于 Unix Domain Socket，本身就不支持跨操作系统的 TCP 通信。必须将 HUD 完全剥离为一个独立的可移植项目，通过 TCP 网络协议与 Daemon 通信。

## What Changes

- **新建独立项目 `flow_hud/`**：在仓库根目录下创建一个完全独立的 Python 包（含独立的 `pyproject.toml`），包含 HUD 的所有渲染、状态机、配置与插件代码。
- **IPC 协议层提取为共享库**：将 `flow_engine/ipc/protocol.py` 中的消息格式 (`Request`, `Response`, `Push`, `encode`, `decode`) 提取为双端共享的轻量协议包 `flow_ipc/`，或直接在 `flow_hud` 中内联一份精简副本。
- **IPC 传输层升级**：**BREAKING** — HUD 端的 `IPCClient` 必须将底层连接从 `asyncio.open_unix_connection` 改为 `asyncio.open_connection(host, port)` TCP 模式，以支持跨系统通信。Daemon 端的 IPC Server 必须同时增加 TCP 监听口（或将 Unix Socket 改为 TCP Socket）。
- **清理 `flow_engine/hud/`**：将 `hud_config.py`, `interfaces.py`, `ui.py`, `ipc_bridge.py`, `app.py` 从 `flow_engine/hud/` 迁移至 `flow_hud/`。`flow_engine/hud/` 下仅保留 `tui.py`（Textual 终端 UI，它依然是引擎生态的一部分）。
- **入口与脚本**：`flow_hud` 拥有独立的 `__main__.py` 入口与 `pyproject.toml` 中的 `[project.scripts]` 命令（如 `flow-hud`），在 Windows 端可以 `pip install .` 后直接执行。

## Capabilities

### New Capabilities
- `hud-standalone-package`: HUD 作为独立 Python 包运行，拥有自己的依赖管理和入口，与 Flow Engine 零耦合。
- `tcp-ipc-transport`: IPC 通信从 Unix Socket 升级为 TCP Socket，允许跨机器 / 跨操作系统连接。

### Modified Capabilities
_(无现有 spec 层级行为变更)_

## Impact

- **`flow_engine/ipc/server.py`**: Daemon 的 IPC 服务端需要新增 TCP 监听入口。
- **`flow_engine/ipc/client.py`**: 原有客户端保持 Unix Socket 模式（CLI/TUI 仍运行在 WSL 本地），不受影响。
- **`flow_engine/hud/`**: 目录被精简，仅保留 `tui.py` 和 `__init__.py`。
- **`pyproject.toml`**: 主项目移除 `gui` 可选依赖组（PySide6, pynput 不再属于 flow-engine）。
- **新增 `flow_hud/pyproject.toml`**: 独立的依赖声明（PySide6, pynput）。
- **`scripts/hud_hack_demo.py`**: 保留作为独立实验脚本，不受影响。
