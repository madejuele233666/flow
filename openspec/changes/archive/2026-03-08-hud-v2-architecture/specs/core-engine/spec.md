## ADDED Requirements

### Requirement: 纯数据驱动状态机 (Pure Data-Driven State Machine)
核心引擎必须包含一个状态机模块，该模块负责管理 HUD 整体的三态变化（如 Ghost, Pulse, Command）。状态机必须做到：1. 完全分离任何对 PySide6 等视窗框架的引入，成为纯粹的 Python 数据类或逻辑器；2. 通过接收结构化的意图 (Intent) 触发状态转变。

#### Scenario: 状态的无外设转移验证
- **WHEN** 状态机接收到代表“长期静止”的 `RadarIdleIntent` 或者 `Intent.ENTER_GHOST` 指令。
- **THEN** 状态机的内部状态变为 `HudState.GHOST`，并将此转移记录下来，而不是去调用 UI API。

### Requirement: 基于 Qt Signal 的跨线程安全事件总线 (Thread-Safe EventBus)
由于硬件监控（Mouse Radar，后台 pynput 线程）与主 UI（Qt 主循环线程）并存，直接的方法调用会引发线程冲突和死锁。所以我们需要一个继承自 `QObject` 的核心 `EventBus`。通过发射动态 Signal 并以 `Qt.QueuedConnection` 模式路由请求到订阅者。

#### Scenario: 后台线程投递消息至主线程
- **WHEN** 一个处在隐式后台子线程中的函数通过 `EventBus.emit()` 发射了坐标信息事件。
- **THEN** 系统底层的 Qt C++ 层捕捉此发射，安全地将其投放入了主线程的事件队列中，等主线程有空缺时调用该事件的所有注册的 Slot 函数，确保线程绝对安全。

### Requirement: 极简编排器容器 (Minimalist DI Orchestrator)
提供 `HudApp` 作为唯一的依赖注入容器。该类不对外部通讯或 UI 直接负责，它只负责组装 `EventBus`、`StateMachine` 以及初始化 `HookManager` 并下发 `PluginContext` 给各个外挂模块。

#### Scenario: 引擎离线安全启动
- **WHEN** `HudApp.start()` 被调用且传入了仅包含 Mock 类型的插件集合列表。
- **THEN** 系统能够瞬间联通所有的 Mock 组件，跑通控制台事件流，且无任何 UI 显示。
