---
format: design
version: 1.0.0
title: "沉浸式三阶悬浮 HUD 技术设计文档"
status: draft
---

# 沉浸式三阶悬浮 HUD 技术设计文档

## 1. 架构概览

我们将使用 PySide6 作为渲染引擎，pynput 作为外围的鼠标雷达，IPCClient 作为与后台守护进程的通信桥梁。

```text
┌───────────────── UI 进程 ──────────────────┐
│                                              │
│  [ Pynput Listener (Daemon Thread) ]         │
│         │ (实时产出全局 X, Y 坐标)             │
│         ▼                                    │
│  ┌───────────────────────────────────┐       │
│  │   HoverRadar (雷达状态机模块)       │       │
│  │   - 判定 Idle (静止) > HUDConfig.IDLE_TIMEOUT │       │
│  │   - 判定 Pulse (位移)               │       │
│  │   - 判定 Command (悬停包围盒) > HUDConfig.HOVER_TIMEOUT│       │
│  └──────┬────────────────────────────┘       │
│         │ (发射 StateChanged 信号)            │
│         ▼                                    │
│  ┌───────────────────────────────────┐◀──┐   │
│  │   HUDWindow (PySide6 异形无边框)    │   │IPC│ JSON-Lines
│  │   [ 动画管理器 (PropertyAnimation) ]│   │推 │ tcp://127.0.0.1:54321
│  │   [ 穿透热切换 (WindowFlags API)  ] │   │拉 │ (flow_engine.ipc)
│  └───────────────────────────────────┘───┘   │
└──────────────────────────────────────────────┘
```

## 2. 核心模块设计

### 2.1 HoverRadar (雷达状态机)
单独在一个线程中运行，防止阻塞 Qt 主事件循环。
- **职责**：只负责算术题。计算 `当前鼠标(x,y)` 是否在 `HUD_RECT` 几何范围内，统计 `静止时长` 和 `悬停时长`。
- **状态抛出**：通过 Qt 的 `Signal` 机制，将计算出的三个状态（`STATE_VOID`, `STATE_PULSE`, `STATE_COMMAND`）发送给主 UI 线程。

### 2.2 HUDWindow (渲染器)
继承自 `QMainWindow`，但舍弃常规标题栏。
- **Window Flags Hack**: 
  - `Qt.FramelessWindowHint`: 无边框。
  - `Qt.WindowStaysOnTopHint`: 置顶。
  - `Qt.Tool`: 不在任务栏显示图标。
  - `# 关键:` `Qt.WindowTransparentForInput` 是根据接受到的信号**动态增删**的。
- **透明树脂效果 (Acrylic Blur)**: 在 Windows 上调用 `DwmEnableBlurBehindWindow`，在 macOS 尝试 `NSVisualEffectView`。（若兼容性太差，作为 Plan B  fallback 到半透明带 border 的普通 Widget）。

### 2.3 State Animation (状态转换微动效)
- **Void (静默)**: `Opacity = HUDConfig.VOID_OPACITY`, `Width = HUDConfig.VOID_WIDTH`, `Flags += TransparentForInput`
- **Pulse (觉醒)**: `Opacity = HUDConfig.PULSE_OPACITY`, `Width = HUDConfig.PULSE_WIDTH` (只显示基础文本), `Flags += TransparentForInput` (依旧穿透！)
- **Command (实体交互)**: `Opacity = HUDConfig.COMMAND_OPACITY`, `Width = HUDConfig.COMMAND_WIDTH`, `Height = 可变`, `Flags -= TransparentForInput` (解除穿透，接管点击)，并渲染子组件树（按钮、进度条等）。

## 3. 依赖项与环境
新的 `[gui]` 依赖组（可选安装）：
```toml
[project.optional-dependencies]
gui = [
    "PySide6>=6.6",
    "pynput>=1.7",
]
```

## 4. 设计哲学 (Design Philosophy)
1. **零魔法数字与极度客制化 (Zero Magic Numbers & High Customizability)**: 
   - 所有的 UI 常量（宽、高、透明度、颜色 HEX 值）、物理引擎参数（阻尼、弹性系数）以及时间阈值必须硬性抽取至 `HUDConfig` 数据类中，代码主体逻辑中严禁出现任何未经定义的数字常量。
   - `HUDConfig` 必须支持从外部文件（如 `~/.flow/hud_config.toml` 或 `.json`）进行反序列化加载。允许用户像配置 Neovim 一样完全自定义界面的骨架、颜色主题响应和动画曲线。
2. **绝对解耦与可扩展性 (Absolute Decoupling & Extensibility)**: 
   - `HoverRadar` 必须是一个不依赖于 `Qt` 环境的高内聚逻辑模块（通过抽象接口调用 UI），便于编写单元测试。
   - 输入源 (`pynput`) 仅被视为一个受抽象层（如 `InputListenerProtocol`）约束的坐标生成器。
   - UI 渲染层 (`HUDWindow`)、中央通信桥梁 (`IPCClient`) 和状态判断核心 (`HoverRadar`) 直接在最顶端的胶水层中进行组装，互相透明。
3. **基于微前端内核的插件架构 (Micro-Kernel Plugin Architecture)**:
   - **精确的槽位注射 (Slots)**: 放弃粗放的列表注册机制，引入类似于 VSCode `Contribution Points` 的枚举槽位体系（如 `HUDSlot.MAIN_PANEL`, `HUDSlot.ACTION_BAR`），确保所有第三方组件（如番茄钟、AI 对话）都能被宿主布局管理器绝对约束，不破坏核心的极简美学。
   - **依赖注入与控制反转 (DI & IoC)**: 插件严禁私自 `import` 底层组件或全局变量。宿主在挂载时必须向插件传入唯一的上下文 `HUDContext(ipc, config, theme)`，通过 IoC 模式下发网络请求与读取全图样式的核心能力。
   - **防御性沙箱与懒加载 (Sandbox & Lazy Load)**: 所有外接的扩展类只在 HUD 真正拉起为“交互态”时才开始初始化实例渲染，极大程度地降低应用在“静默态”的后台常驻开销。宿主利用包裹型 `try-except` (Error Boundary) 集中捕获任何插件执行时所抛出的异常（渲染降级 UI 占位），保证核心系统进程免受其害（防崩溃）。
4. **优雅抽象与严谨性 (Elegant Abstraction)**: 核心层函数必须全覆盖强类型提示 (`Type Hints`)，所有跨层通信有效载荷使用 `dataclass` 定义以明确意图。遵循六边形架构原则隔离底层 OS API 的干扰。


