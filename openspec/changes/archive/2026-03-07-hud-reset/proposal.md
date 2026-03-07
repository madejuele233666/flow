---
format: proposal
version: 1.0.0
title: "HUD 代码清除与经验归档"
status: draft
---

## Why

第一轮 HUD 原型开发暴露了严重的架构问题：代码在快速迭代中堆叠为一个缺乏清晰边界的"泥球"，UI 渲染、状态机、IPC 桥接、鼠标雷达等模块之间耦合过紧，无法独立测试和迭代。继续在此基础上修补不如彻底清除，为第二轮高质量重写创造一个干净的起点。

同时，需要将第一轮积累的核心技术验证结论（PySide6 穿透切换、pynput 全局坐标、TCP IPC 桥接等）以经验文档的形式固化下来，防止知识丢失。

## What Changes

- **移除** `flow_hud/` 目录下的全部 HUD Python 源代码（`ui.py`, `app.py`, `ipc_bridge.py`, `hud_config.py`, `interfaces.py`, `input_listener.py`, `radar.py`, `ipc/` 子包, `__init__.py`, `__main__.py`）。
- **移除** `flow_hud/pyproject.toml` 和 `flow_hud/README.md`，彻底清除该独立包。
- **移除** Windows 桌面启动脚本 `Flow-HUD.vbs` 和 `Flow-Start.bat`。
- **移除** 实验脚本 `scripts/hud_hack_demo.py`。
- **保留** `flow_engine/` 中的所有代码不动，包括：
  - `flow_engine/ipc/server.py`（含 TCP 双监听能力）
  - `flow_engine/config.py`（含 `IPCConfig`）
  - `flow_engine/daemon.py`（含 TCP 配置透传）
  - `flow_engine/hud/tui.py`（Textual TUI 不受影响）
- **保留** `openspec/specs/` 下已归档的 `hud-standalone-package` 和 `tcp-ipc-transport` 规格（这些描述的是基础设施能力，与 HUD UI 代码无关）。
- **新增** 经验教训总结文档 `docs/hud-v1-postmortem.md`，归纳技术验证结论、架构失败原因和下一轮设计建议。
- **归档** `openspec/changes/hud-prototype` change。

## Capabilities

### New Capabilities
- `hud-v1-postmortem`: 第一轮 HUD 开发的经验教训归档文档，涵盖技术验证结论、架构反思与下一轮设计建议。

### Modified Capabilities
- `hud-standalone-package`: 移除"HUD 独立入口"和"HUD 独立包结构"两项需求（因为 HUD 代码被清除），但保留"引擎端清理"和"主项目依赖清理"的需求不变（这些已完成且保持有效）。

## Impact

- **文件系统**：删除 `flow_hud/` 整个目录树、桌面启动脚本、实验脚本。
- **依赖**：无变化（PySide6/pynput 已在上一轮从 `flow_engine` 的 pyproject.toml 中移除）。
- **引擎端**：零影响。TCP IPC 监听、配置体系、Daemon 均保持原样，随时可供下一轮 HUD 使用。
- **用户**：Windows 端暂时无法运行 HUD，直到第二轮重写完成。
