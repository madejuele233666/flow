## ADDED Requirements

### Requirement: HUD SHALL live inside the frontend workspace
The HUD project MUST be housed under the `frontend/` workspace while remaining an independently installable package for frontend-specific development.

#### Scenario: Frontend workspace contains the HUD package
- **WHEN** a contributor inspects the `frontend/` directory after migration
- **THEN** the HUD project metadata and package source are both located under `frontend/`
- **AND** the HUD runtime no longer requires a top-level `flow_hud/` directory at the repository root

## MODIFIED Requirements

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
