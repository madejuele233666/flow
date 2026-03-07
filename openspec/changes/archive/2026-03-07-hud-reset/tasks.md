---
format: tasks
version: 1.0.0
title: "HUD 代码清除与经验归档任务清单"
status: draft
---

## 1. 撰写历史经验文稿

- [x] 1.1 创建 `docs/hud-v1-postmortem.md`。
- [x] 1.2 在该文档中，沉淀 PySide6 全局鼠标穿透、pynput 事件获取、TCP IPC 连接等技术点。
- [x] 1.3 在该文档中，分析第一轮 HUD 的架构问题（`app.py` 耦合、职责边界不清等）。
- [x] 1.4 在该文档中，提出第二轮 HUD 重写的设计建议（极度切分组件，测试驱动开发等）。

## 2. 代码及文件清理

- [x] 2.1 递归删除整个 `flow_hud/` 目录及其下的所有内容。
- [x] 2.2 删除位于 Windows 桌面的 `Flow-HUD.vbs` 与 `Flow-Start.bat`。
- [x] 2.3 删除实验脚本 `scripts/hud_hack_demo.py`。

## 3. 验收与归档

- [x] 3.1 确认 `flow_engine/` 中保留了之前的 TCP IPC 双模服务端配置，不做任何改动。
- [x] 3.2 归档早期废弃的 `hud-prototype` change （如果仍处于活跃状态）。
