---
format: tasks
version: 1.0.0
title: "沉浸式三阶悬浮 HUD 任务清单"
status: draft
---

# HUD 原型开发任务清单

## 阶段 1: 架构基建与优雅解耦 (Architecture & Core Decoupling)
- [x] 构建全局配置中心 `hud_config.py`：使用 `dataclass` 或 `Pydantic` 抽取并定义所有的魔法数字（如阈值时长、组件尺寸、材质透明度、动画阻尼系数、HEX 颜色值），确保核心逻辑和 UI 代码中出现 0 个 magic number。
- [x] 实现配置的反序列化加载器，支持从用户的本地配置文件（例如 `toml`）动态覆盖默认的 `HUDConfig`，实现完全的个性化可配置。
- [x] 定义核心通信接口契约 (`Protocols` / `ABCs`)：明确输入监听器 (`InputListener`)、雷达状态机 (`HoverRadar`)、UI 渲染器 (`HUDWindow`) 和引擎通信 (`IPCClient`) 之间的依赖边界，确保所有模块完全依赖抽象而非具体实现。
- [x] 构建微前端插件协议中枢 (Micro-Kernel Extensibility API):
  - 设定枚举槽位体系 `HUDSlot`，界定宿主中允许插入外部组件的具体座标区 (如 `ACTION_BAR`)。
  - 创建严格的插件依赖注入上下文 `HUDContext(ipc, config, theme)`，实现控制反转机制 (IoC)。
  - 编写基础扩展父类 `BaseHUDPlugin`，实装懒加载（Lazy Rendering）和沙箱级（Error Boundary / Try-Except）崩溃防御保护策略。

## 阶段 2: 物理层核心破解 (The Physical Hacking)
- [x] 申请新的分支或创建一个独立的实验脚本 `scrtip/hud_hack_demo.py` 以在隔离环境下验证解耦的各组件。
- [x] 编写独立的 `pynput.mouse.Listener` 服务，它仅作为生产者，只负责依照 `HUDConfig.POLL_RATE_MS` 每隔固定的时间返回全局坐标至队列中，不包含任何状态判断与其它的业务理解。
- [x] 创建基础的 `PySide6` 无标题栏置顶方块窗体。
- [x] 重点验证穿透标志位的热切换机制：
  - 发信号让窗体增加 `QtCore.Qt.WindowTransparentForInput`，尝试点透后面的 IDE。
  - 延时后发信号移除标志，尝试点击窗体自身捕获事件。
- [x] 拼装状态机模块 `HoverRadar`: 给定屏幕上一个悬浮窗区域，输出三维时长的事件 (Void, Pulse, Command)。

## 阶段 3: 视觉交互与微动效编排 (The UI & UX Polish)
- [x] 构建底层渲染材质：尝试利用平台特性调用毛玻璃模糊 (Windows DwmEnableBlurBehindWindow / Mac NSVisualEffectView)，失败则提供有高级感的回退样式（如带微粒噪点的半透底漆）。
- [x] 设定字体排布层级体系：导入等宽字体（如 JetBrains Mono）专用于计时器和分数显示，消除跳动。导入极简无衬线体（如 Inter）用于主题任务。
- [x] 刻画具有“阻尼交互”感的三态物理渐变 (`QPropertyAnimation` + `QEasingCurve`):
  - 静默退回边缘时的磁吸弹回感 (`InBack` or `Elastic`)。
  - 展开时的平滑扩张感，以及透明度的收放。
- [x] 为暴露的交互键（暂停按钮、结项按钮）附加迟滞与 Hover 触发下的缩放 (`Scale`) 和高亮反馈。
- [x] 撰写色彩映射逻辑引擎，使得边缘线或者小色块能够依据任务进展时间及 DDL 显示“冷暖色温”以暗示紧迫感，并确保不打扰视线。

## 阶段 4: 中枢神经接驳 (The IPC Binding)
- [x] 将 TUI 中的 `IPCClient` 实例完整复制迁入 HUD 架构，通过 `asyncio` 结合 `QThread` 运转监听。
- [x] 监听远端的 `task.state_changed` 与 `timer.tick` 消息号，绑定更新至对应的 Qt `QLabel` 文本。
- [x] 接线 HUD 面板上的 UI 交互事件 (如按钮被点击)。将其转译发送 `task.done(task_id)` 等方法至服务端，并闭环验证后端收到回馈。

## 阶段 5: 核心集成与收尾 (Integration & Finalization)
- [x] 将 `scripts/hud_hack_demo.py` 中的 `MouseListener` 和 `HoverRadar` 迁移到 `flow_hud` 正规包下 (例如 `flow_hud/input_listener.py` 或 `flow_hud/radar.py`)。
- [x] 在 `flow_hud/app.py` 中实例化 `MouseListener` 和 `HoverRadar`，并将它们与 `HUDWindow` 的 `apply_state` 串联，实现生产环境的真实三态感知响应。
- [x] 从 `timer.tick` 提取任务进度值 (`ratio`)，在 `update_timer` 同步函数中调用 `ColorTemperatureEngine` 动态更新 HUD 的颜色或背景色，完成“色温上下文提示”需求。
