## Why

当前仓库仍以单根 Python 项目组织 `flow_engine` 和 `flow_hud`，代码边界已经逻辑分离，但目录、依赖、安装入口和开发流程仍然混在同一个根目录下。现在需要把仓库升级为明确的前后端双工作区结构，降低迁移成本，并为后续独立构建、独立发布和分团队协作打下基础。

## What Changes

- 在仓库根目录新增 `frontend/` 和 `backend/` 两个一级目录，分别承载 HUD 前端工程和 Flow Engine 后端工程。
- **BREAKING** 将现有顶层后端 Python 项目迁移到 `backend/`，包括包目录、入口脚本、依赖声明和运行说明。
- **BREAKING** 将现有顶层 HUD 项目迁移到 `frontend/`，包括包目录、插件代码、依赖声明和运行说明。
- 调整仓库级文档、测试路径和开发说明，使开发者能够从新的前后端目录结构下完成安装、运行和验证。
- 保持前后端现有 IPC 契约与功能边界不变，目录迁移不应重新耦合 `flow_hud` 与 `flow_engine`。

## Capabilities

### New Capabilities
- `repo-frontend-backend-layout`: 定义仓库根目录必须提供明确的 `frontend/` 与 `backend/` 工作区，以及迁移后的边界与开发入口。
- `backend-standalone-package`: 定义 Flow Engine 后端在 `backend/` 目录下作为独立工程运行、安装和验证的要求。

### Modified Capabilities
- `hud-standalone-package`: 将 HUD 独立包的宿主路径从仓库根目录调整为 `frontend/` 工作区，同时保持其独立部署属性。

## Impact

- Affected code: 顶层 `pyproject.toml`、`flow_engine/`、`flow_hud/`、测试目录、README 与架构文档。
- Affected tooling: 安装命令、运行入口、测试命令、可能的导入路径与 CI 工作目录。
- Affected systems: HUD 前端分发方式、后端 CLI/Daemon 启动方式、仓库贡献者的本地开发流程。
