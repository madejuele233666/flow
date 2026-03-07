---
format: design
version: 1.0.0
title: "HUD 代码清除与经验归档 — 技术设计"
status: draft
---

## Context

第一轮 HUD 原型开发（`hud-prototype` change）完成了以下技术验证：
1. PySide6 `WindowTransparentForInput` 标志位可在运行时热切换，实现穿透/实体对话。
2. pynput `mouse.Listener` 能在独立线程中以极低开销获取全局坐标，不干扰 Qt 事件循环。
3. `asyncio.open_connection` TCP 模式可穿越 WSL ↔ Windows 边界，JSON-Lines 协议完全兼容。
4. 三态（Void → Pulse → Command）的 `QPropertyAnimation` 动效链可行。

但代码在快速迭代中高度耦合——`ui.py` 同时承载了渲染、动画、状态判断和配置读取，`app.py` 把 IPC、雷达、UI 全部 inline 组装，`hud_config.py` 的 dataclass 层级过深但实际覆盖逻辑薄弱。结果是：代码难以单独测试、难以扩展、难以理解。

当前 `flow_engine/` 侧的基础设施（TCP IPC Server、IPCConfig、Daemon 双模监听）已经稳固且独立，不受 HUD 清除影响。

## Goals / Non-Goals

**Goals:**
- 彻底移除 `flow_hud/` 目录及所有 HUD 前端代码，回到一个干净的状态。
- 移除桌面启动脚本和实验性 demo 脚本。
- 撰写 `docs/hud-v1-postmortem.md` 将技术验证结论和架构反思固化为永久知识。
- 归档 `hud-prototype` change。
- 确保引擎端（IPC Server TCP 监听、IPCConfig、Daemon）零回退，为第二轮 HUD 开发保留可用的后端接口。

**Non-Goals:**
- 不修改 `flow_engine/` 中的任何代码。
- 不删除 `openspec/specs/` 中已归档的 `hud-standalone-package` 和 `tcp-ipc-transport` 规格（它们描述的是基础设施能力）。
- 不设计第二轮 HUD 的架构（那是下一个 change 的事）。

## Decisions

### 1. 整目录删除 vs 保留骨架
**决定**：整目录删除 `flow_hud/`，不保留空骨架。
**理由**：保留空的 `pyproject.toml` 或 `__init__.py` 会给人一种"代码还活着"的错觉。彻底删除后，下一轮开发者（包括未来的自己）进入时看到的是一个明确的"这里什么都没有，需要从零构建"的信号。

### 2. 经验文档放置位置
**决定**：放在 `docs/hud-v1-postmortem.md`。
**理由**：`docs/` 是项目级永久文档的标准位置。Postmortem 的受众是未来的开发者，而非 openspec 流程的一部分。

### 3. hud-prototype change 的处理
**决定**：归档到 `openspec/changes/archive/`。
**理由**：它的任务已全部标记完成，artifacts 完整。归档保留了历史记录，同时从活跃 changes 列表中移除。

## Risks / Trade-offs

- **知识遗忘风险** → 通过 `hud-v1-postmortem.md` 文档缓解，将所有关键发现以结构化方式记录。
- **用户暂时失去 HUD** → 可接受的代价。TUI 和 CLI 仍然完全可用。第二轮 HUD 开发时可以更快地产出高质量代码。
- **主规格需要更新** → `hud-standalone-package` spec 中关于"HUD 独立包结构"和"HUD 独立入口"的需求暂时失效，通过 delta spec 标记为 REMOVED。
