---
format: tasks
version: 1.0.0
title: "HUD 独立仓库分离 — 实施任务清单"
status: draft
---

## 1. 创建 flow_hud 独立项目脚手架

- [x] 1.1 创建 `flow_hud/` 顶层目录和 `flow_hud/flow_hud/` Python 包目录。
- [x] 1.2 编写 `flow_hud/pyproject.toml`，声明独立的包名 (`flow-hud`)、独立依赖 (`PySide6>=6.6`, `pynput>=1.7`, `toml>=0.10`) 和脚本入口 (`flow-hud = "flow_hud.app:run_hud"`)。
- [x] 1.3 创建 `flow_hud/flow_hud/__init__.py` 和 `flow_hud/flow_hud/__main__.py` (入口：`python -m flow_hud`)。
- [x] 1.4 创建 `flow_hud/README.md`，说明如何在 Windows 上安装和连接 WSL Daemon。

## 2. IPC 协议内联与 TCP 客户端改造

- [x] 2.1 将 `flow_engine/ipc/protocol.py` 精确复制到 `flow_hud/flow_hud/ipc/protocol.py`，并在文件头添加 `PROTOCOL_VERSION` 常量。
- [x] 2.2 基于 `flow_engine/ipc/client.py` 创建 `flow_hud/flow_hud/ipc/client.py`，将 `asyncio.open_unix_connection` 替换为 `asyncio.open_connection(host, port)` TCP 模式，默认连接 `127.0.0.1:54321`。
- [x] 2.3 创建 `flow_hud/flow_hud/ipc/__init__.py`。

## 3. 迁移 HUD 模块代码

- [x] 3.1 将 `flow_engine/hud/hud_config.py` 迁移至 `flow_hud/flow_hud/hud_config.py`，新增 `ConnectionConfig` dataclass（`host`, `port`），并在 `HUDConfig` 中聚合。
- [x] 3.2 将 `flow_engine/hud/interfaces.py` 迁移至 `flow_hud/flow_hud/interfaces.py`，修正所有 import 路径为 `flow_hud.xxx`。
- [x] 3.3 将 `flow_engine/hud/ui.py` 迁移至 `flow_hud/flow_hud/ui.py`，修正 import 路径。
- [x] 3.4 将 `flow_engine/hud/ipc_bridge.py` 迁移至 `flow_hud/flow_hud/ipc_bridge.py`，将 `from flow_engine.ipc.client import IPCClient` 改为 `from flow_hud.ipc.client import HUDIPCClient`，将 `from flow_engine.ipc.protocol import Push` 改为 `from flow_hud.ipc.protocol import Push`。
- [x] 3.5 将 `flow_engine/hud/app.py` 迁移至 `flow_hud/flow_hud/app.py`，修正所有 import 为 `flow_hud` 内部引用。

## 4. 清理 flow_engine 端

- [x] 4.1 从 `flow_engine/hud/` 中删除已迁移的文件：`hud_config.py`, `interfaces.py`, `ui.py`, `ipc_bridge.py`, `app.py`。仅保留 `__init__.py` 和 `tui.py`。
- [x] 4.2 从 `pyproject.toml` 中移除 `gui` 可选依赖组 (`PySide6`, `pynput`)。

## 5. Daemon 端新增 TCP 监听

- [x] 5.1 在 `flow_engine/ipc/server.py` 中新增 TCP 监听入口（`asyncio.start_server`），与现有 Unix Socket 并行运行，默认端口 `54321`。
- [x] 5.2 在引擎的主配置 (`flow_engine/config.py`) 中新增 `ipc.tcp_port` 和 `ipc.tcp_host` 配置项。

## 6. 验证与整合

- [x] 6.1 在 `flow_hud/` 目录下确认 `pip install -e .` 可以成功安装，且不引入任何 `flow_engine` 依赖。
- [x] 6.2 静态检查：确保 `flow_hud/` 目录下无任何 `from flow_engine` 或 `import flow_engine` 语句。
