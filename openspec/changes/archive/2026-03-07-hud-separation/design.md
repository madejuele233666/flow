---
format: design
version: 1.0.0
title: "HUD 独立仓库分离 — 技术设计文档"
status: draft
---

## Context

Flow Engine 当前的 HUD 渲染代码（`flow_engine/hud/`）与引擎核心 (`flow_engine/`) 共享同一个 Python 包。HUD 的运行依赖 PySide6 和 pynput，这两个库需要原生操作系统的图形栈支持。用户的常态工作流是在 WSL (Linux) 中运行 Daemon 后台，而 WSL 不具备原生窗口合成器（`WindowTransparentForInput`、DWM 毛玻璃、全局鼠标钩子在 WSLg 中全部失效）。因此需要将 HUD 剥离为独立的可部署单元，在 Windows 宿主机上原生运行，通过 TCP IPC 与 WSL 中的 Daemon 通信。

当前 IPCClient 基于 `asyncio.open_unix_connection` (Unix Domain Socket)，只能在同一台 Linux 机器内部工作，无法跨越 WSL/Windows 边界。

## Goals / Non-Goals

**Goals:**
- HUD 作为完全独立的 Python 包（`flow_hud/`），可在 Windows 原生 Python 环境中 `pip install .` 并直接运行。
- HUD 与 Flow Engine 之间**零 import 依赖**：不允许出现 `from flow_engine.xxx import ...`。
- IPC 通信支持 TCP 模式，允许跨操作系统连接（WSL Daemon ↔ Windows HUD）。
- 保持当前 CLI/TUI 在 WSL 内的原有体验完全不受影响。
- IPC 协议格式 (JSON-Lines) 保持完全的线格式兼容，不破坏现有的消息编解码。

**Non-Goals:**
- 不重写 IPC 协议格式（仍使用 newline-delimited JSON）。
- 不实施安全认证/加密（局域网内暂不需要 TLS），这是后续迭代目标。
- 不改动 TUI (`tui.py`) 的运行方式——它继续留在 `flow_engine/hud/` 内部通过 Unix Socket 工作。
- 不做自动化的跨平台服务发现（用户手动配置 IP:Port 即可）。

## Decisions

### 1. 项目结构：Monorepo 并列目录

```
flow/                         # 仓库根目录
├── flow_engine/              # 核心引擎 (WSL/Linux 端)
│   ├── ipc/
│   │   ├── server.py         # 新增: TCP listener
│   │   ├── client.py         # 保持 Unix Socket (CLI/TUI 本地使用)
│   │   └── protocol.py       # 共享协议 (来源)
│   ├── hud/
│   │   ├── __init__.py
│   │   └── tui.py            # 保留 Textual TUI
│   └── ...
├── flow_hud/                 # 独立 HUD 项目 (Windows 端)
│   ├── pyproject.toml        # 独立的包声明与依赖
│   ├── flow_hud/             # Python 包
│   │   ├── __init__.py
│   │   ├── __main__.py       # 入口 (python -m flow_hud)
│   │   ├── hud_config.py     # 从 flow_engine/hud/hud_config.py 迁移
│   │   ├── interfaces.py     # 从 flow_engine/hud/interfaces.py 迁移
│   │   ├── ui.py             # 从 flow_engine/hud/ui.py 迁移
│   │   ├── ipc_bridge.py     # 从 flow_engine/hud/ipc_bridge.py 迁移
│   │   ├── app.py            # 从 flow_engine/hud/app.py 迁移
│   │   └── ipc/              # IPC 协议副本 (轻量内联)
│   │       ├── __init__.py
│   │       ├── protocol.py   # 精确复制 flow_engine/ipc/protocol.py
│   │       └── client.py     # 改造: TCP 模式专用客户端
│   └── README.md
└── scripts/
    └── hud_hack_demo.py      # 保留不受影响
```

**理由**：采用 Monorepo 并列而非 Git submodule，降低维护复杂度。用户可以直接将 `flow_hud/` 目录拷贝到 Windows 端，无需完整克隆整个仓库。

### 2. IPC 协议共享策略：精确副本内联

将 `flow_engine/ipc/protocol.py` 精确复制至 `flow_hud/flow_hud/ipc/protocol.py`。

**理由**：
- `protocol.py` 是一个极其稳定的微模块（~140 行），几乎不会变更。
- 引入 pypi 共享包（如 `flow-ipc-protocol`）对只有两个消费者的场景来说过度设计。
- 内联副本使得 `flow_hud` 做到了真正的零外部 flow 依赖。

### 3. HUD 端 IPCClient：TCP 专用改造

`flow_hud/flow_hud/ipc/client.py` 将使用 `asyncio.open_connection(host, port)` 替代 `asyncio.open_unix_connection`。

```python
# flow_hud 的 TCP Client
async def connect(self) -> None:
    self._reader, self._writer = await asyncio.open_connection(
        self.host, self.port
    )
```

默认连接 `127.0.0.1:54321`，可通过配置文件或环境变量覆盖。

### 4. Daemon 端 IPC Server：新增 TCP 监听

在 `flow_engine/ipc/server.py` 中**额外**新增一个 TCP 监听入口，与现有 Unix Socket 并行。

**理由**：不移除 Unix Socket，CLI/TUI 在本地 WSL 内继续使用它（零延迟、无需网络配置）。TCP 监听供 HUD 远程连接使用。

### 5. HUD 配置：支持网络地址

`flow_hud` 的 `hud_config.py` 新增连接配置段：

```python
@dataclass
class ConnectionConfig:
    host: str = "127.0.0.1"
    port: int = 54321
```

用户可在 `~/.flow/hud_config.toml` 中覆盖。

## Risks / Trade-offs

- **[协议版本漂移]** → 两份 `protocol.py` 副本可能随时间失同步。缓解：在 `protocol.py` 中维护一个 `PROTOCOL_VERSION` 常量，握手时双端校验。
- **[TCP 安全性]** → TCP 监听在 `0.0.0.0` 上暴露了未经认证的 RPC 入口。缓解：默认只监听 `127.0.0.1`（仅本机）；WSL 和 Windows 宿主机之间 `localhost` 互通。长期引入 Token 认证。
- **[端口冲突]** → 54321 端口可能被占用。缓解：可在配置中覆盖端口。
