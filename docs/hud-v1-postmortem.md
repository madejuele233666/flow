# HUD V1 (Prototype) Postmortem

## 第一轮 HUD 架构失败分析

第一轮 HUD 原型（基于 PySide6 构建）在快速迭代验证技术可行性的过程中，逐渐演变成了一个高度耦合的"大泥球"（Big Ball of Mud），导致后续难以维护、测试和扩展。

### 主要架构问题

1. **职责边界不清与模块过度耦合**:
   - `ui.py` 同时承载了极其繁重的职责：UI 组件渲染、动画逻辑（通过 QPropertyAnimation 切换状态）、UI 状态判断（幽灵态、呼吸态、主控态），甚至还混合了部分业务配置读取（调用 `hud_config.py`）。
   - `app.py` 作为入口文件，在内部通过 inline 方式硬编码组装了 IPC 桥接、雷达（鼠标监听）、UI 等核心模块，完全没有依赖注入（DI）的概念。
2. **缺乏独立可测试性**:
   - 由于 UI 强依赖于底层的 IPC 状态机、鼠标雷达，以及缺少 Mock 机制，导致几乎无法对单一组件（如动画过渡逻辑）进行单独测试。每次测试都需要在 Windows 桌面真实启动整个套件。
3. **配置管理的薄弱**:
   - `hud_config.py` 虽然使用 dataclass 定义了较深的层级结构，但对实际配置逻辑覆盖有限，许多组件的配置值（如窗口尺寸、动画时长）可能被硬编码散落在各处，未能通过统一途径进行透传。

结论：快速原型的代价是代码完全丧失了可维护性。与其在这一版基础上不断重构，不如在验证完核心技术可行性后彻底抛弃这套代码架构，从零开始第二次高质量的设计。

## 核心技术验证结论沉淀

虽然第一轮架构失败，但成功验证了在 Windows 侧实现复杂 HUD 的必要基石技术节点。

### 1. PySide6 全局鼠标穿透
- **结论**: `WindowTransparentForInput` 标志位可在运行时动态热切换。
- **经验**: 通过控制该属性和设置无边框窗体（`FramelessWindowHint`）及背景透明（`WA_TranslucentBackground`），可以完美实现类似于“幽灵态（不可点击，纯展示）”与“主控态（可拦截点击，实体交互）”之间的无缝转换。这证明了使用 Qt(PySide6) 做高定全局 Overlay 的完全可行性。

### 2. pynput 事件获取与 Qt 隔离
- **结论**: pynput 的 `mouse.Listener` 能在独立线程中以极低开销获取全局坐标，且不会干扰 Qt 的主事件循环。
- **经验**: 由于雷达逻辑需要捕捉全局（在主监控器任何位置）的鼠标事件，而 Qt 自身的鼠标事件只能在其 widget 层级生效。利用 pynput 开设后台守护线程监听，结合事件队列或者是信号机制抛给 Qt 主线程处理，是解耦全局硬件输入与 UI 层状态机的最佳实战手段。

### 3. 基于 WSL - Windows 边界的 TCP IPC 连接
- **结论**: `asyncio.open_connection` TCP 模式可完美穿越 WSL 与 Windows 宿主机的网络边界。
- **经验**: 使用 JSON-Lines (\n 分割) 协议进行双向全双工通信极大地简化了封包解包逻辑。Flow Engine 守护进程在 WSL 内暴露 TCP 端口（如 12345），Windows 桌面的 HUD 可以像访问本机应用一样稳定连通。双模监听机制（Unix Socket 给同 Linux 的客户端，TCP 给跨 OS 客户端）非常成功，需完整保留。

### 4. 三态动效切换
- **结论**: 基于 `QPropertyAnimation` 的三态（Ghost(空), Pulse(呼吸), Command(主控)）微交互动效链是切实可行的。

## 第二轮 HUD 重写的设计建议

吸取 V1 教训，基于上述技术积淀，对下一轮 HUD 的设计和开发提出以下强制性原则：

1. **极度切分组件 (Extreme Decoupling)**:
   - UI 必须是纯粹的 View 层：状态由单独的 StateMachine 模块控制；动画有单独的 AnimationManager 系统；数据依赖独立的数据层投递。
   - IPC 通讯模块、雷达（Radar）监听模块必须与 UI 层彻底解耦。使用事件总线（Event Bus）或纯粹的信号槽（Signal/Slot）桥接，做到“雷达不用知道 UI 存在，UI 也不需要知道坐标是怎么来的”。
2. **测试驱动开发 (TDD 导向)**:
   - 核心的状态机转换和核心通讯桥接协议必须有 Unittest 覆盖。
   - 在开发任何 UI 之前，确保其状态转换逻辑可以在没有界面的情况下一把梭跑通测试用例。
3. **引入依赖注入 (Dependency Injection)**:
   - 避免在 `app.py` 以及核心类中出现深度的硬编码组装。所有的组件在启动阶段进行集中注入，确保测试可以轻松替换 Mock 注入（如 Mock IPC Client，Mock Mouse Radar）。
4. **规范配置树流转**:
   - 去掉散落各处的各类 hardcodes。让组件强约束为 `Component(config: ComponentConfig)`，仅响应于外部注入的配置源。
