---
format: spec
version: 1.0.0
title: "HUD 独立分发架构"
status: active
---

## Purpose
本规格描述了 Flow Engine 中 Heads-Up Display (HUD) 组件的独立部署架构。为了解决 WSLg 环境下 GUI 能力失效的问题，HUD 被完全剥离为一个独立的 Python 包，以实现在 Windows 原生宿主机的部署和跨系统的连接。
## Requirements
### Requirement: 引擎端清理
从 `flow_engine/hud/` 中迁出所有 GUI 相关代码后，该目录仅保留 Textual TUI 相关文件。

#### Scenario: 迁移后目录结构
- **WHEN** 分离完成后检查 `flow_engine/hud/` 目录
- **THEN** 目录中仅包含 `__init__.py` 和 `tui.py`，不包含 `ui.py`, `ipc_bridge.py`, `app.py`, `hud_config.py`, `interfaces.py`

### Requirement: 主项目依赖清理
Flow Engine 的 `pyproject.toml` 必须移除 `gui` 可选依赖组（PySide6, pynput），这些依赖仅属于 `flow_hud`。

#### Scenario: pyproject.toml 中无 GUI 依赖
- **WHEN** 检查 `flow_engine` 根目录的 `pyproject.toml`
- **THEN** `[project.optional-dependencies]` 中不存在 `gui` 条目

