---
format: spec
version: 1.0.0
title: "HUD 独立分发架构"
status: active
---

## Purpose
本规格描述了 Flow Engine 中 Heads-Up Display (HUD) 组件的独立部署架构。为了解决 WSLg 环境下 GUI 能力失效的问题，HUD 被完全剥离为一个独立的 Python 包，以实现在 Windows 原生宿主机的部署和跨系统的连接。
## Requirements
### Requirement: HUD SHALL live inside the frontend workspace
The HUD project MUST be housed under the `frontend/` workspace while remaining an independently installable package for frontend-specific development.

#### Scenario: Frontend workspace contains the HUD package
- **WHEN** a contributor inspects the `frontend/` directory after migration
- **THEN** the HUD project metadata and package source are both located under `frontend/`
- **AND** the HUD runtime no longer requires a top-level `flow_hud/` directory at the repository root

### Requirement: 引擎端清理
从 `backend/flow_engine/hud/` 中迁出所有 GUI 相关代码后，该目录 MUST 仅保留 Textual TUI 相关文件。

#### Scenario: 迁移后目录结构
- **WHEN** 分离完成后检查 `backend/flow_engine/hud/` 目录
- **THEN** 目录中仅包含 `__init__.py` 和 `tui.py`，不包含 `ui.py`, `ipc_bridge.py`, `app.py`, `hud_config.py`, `interfaces.py`

### Requirement: 主项目依赖清理
HUD 所需的 GUI 依赖 MUST 仅在 `frontend/` 工作区中声明；`backend/` 工作区 MUST NOT 声明 PySide6、pynput 等 GUI 依赖。

#### Scenario: backend 工作区不携带 GUI 依赖
- **WHEN** 检查 `backend/` 工作区的项目依赖声明
- **THEN** 其中不存在 PySide6 或 pynput 等 HUD GUI 依赖

#### Scenario: frontend 工作区承载 HUD GUI 依赖
- **WHEN** 检查 `frontend/` 工作区的项目依赖声明
- **THEN** HUD 运行所需的 GUI 依赖仅在 `frontend/` 工作区中声明

### Requirement: Windows-targeted HUD entry SHALL boot the product runtime while launcher scripts remain orchestration-only
The Windows-targeted HUD entrypoint MUST start a product runtime that renders the MVP task-status surface by default, and desktop launcher scripts MUST remain limited to sync/bootstrap/start-stop orchestration rather than owning task-status product behavior.

#### Scenario: Windows desktop entry delegates to repo-owned product runtime
- **WHEN** a contributor inspects the Windows desktop control path and repo entrypoint
- **THEN** the desktop entry delegates into `python -m flow_hud.windows_main`
- **AND** the repo-owned Windows runtime profile is responsible for loading the MVP task-status surface

#### Scenario: Launcher does not own task-status business logic
- **WHEN** backend daemon is offline, no task is active, or task state changes during runtime
- **THEN** those product semantics are handled inside the HUD runtime/profile/plugin code
- **AND** the launcher script does not embed task-status rendering, daemon business interpretation, or widget composition logic
