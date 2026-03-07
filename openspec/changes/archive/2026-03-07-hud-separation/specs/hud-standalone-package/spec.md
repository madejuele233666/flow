## ADDED Requirements

### Requirement: HUD 独立包结构
HUD 必须作为一个完全独立的 Python 包（`flow_hud`）存在，拥有自己的 `pyproject.toml`、入口脚本和依赖声明，不得从 `flow_engine` 中 import 任何模块。

#### Scenario: 独立安装与运行
- **WHEN** 用户在一台干净的 Windows 机器上执行 `pip install .`（在 `flow_hud/` 目录下）
- **THEN** 安装成功，且不需要 `flow_engine` 作为依赖项

#### Scenario: 零 import 隔离
- **WHEN** 静态分析工具扫描 `flow_hud/` 目录下的所有 `.py` 文件
- **THEN** 不存在任何 `from flow_engine` 或 `import flow_engine` 语句

### Requirement: HUD 独立入口
HUD 必须提供一个可直接运行的命令行入口（如 `flow-hud`），启动完整的 PySide6 三态交互窗体。

#### Scenario: 命令行启动
- **WHEN** 用户在终端中执行 `flow-hud` 或 `python -m flow_hud`
- **THEN** PySide6 HUD 窗体启动，连接至配置中指定的 Daemon 地址

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
