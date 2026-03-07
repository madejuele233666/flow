## 1. 阶段共识与环境准备 (Phase Alignment & Setup)

- [ ] 1.1 **【检查点】** 再次仔细回溯 `docs/hud-v1-postmortem.md` 和 `design.md`。向用户逐层陈述 HUD V2 对标主引擎的 7 个架构契约（端口防泄漏、双路径 EventBus、强类型载荷、多策略钩子+熔断器、双层权限沙盒、声明式 Manifest、配置驱动 DI）。**此任务必须获得用户显式确认"同意"后才能往下进行。**
- [ ] 1.2 物理清理：彻底清理 V1 遗迹。清除现有的旧版快速原型代码（例如包含脏引用的 `ui.py`, `app.py`, `radar.py`），确保工程目录内仅有纯净的状态。
- [ ] 1.3 创建全新骨架结构：建立 `flow_hud/core/`、`flow_hud/adapters/`、`flow_hud/plugins/` 三大目录，并放置空的 `__init__.py`。

## 2. 强类型载荷系统 (Typed Payloads) — 对标 `events_payload.py` + `hooks_payload.py`

- [ ] 2.1 创建 `flow_hud/core/events_payload.py`。定义所有事件的 `@dataclass(frozen=True)` 载荷类型：
    - `MouseMovePayload(x: int, y: int, screen_index: int)`
    - `StateTransitionedPayload(old_state: str, new_state: str)`
    - `IpcMessageReceivedPayload(method: str, data: dict)`
    - `WidgetRegisteredPayload(name: str, slot: str)`
    - 其他需要的基础载荷
  **【防腐规定】该文件内严禁出现任何 PySide6 或外设相关的 import。**
- [ ] 2.2 创建 `flow_hud/core/hooks_payload.py`。定义所有钩子的强类型载荷：
    - `BeforeTransitionPayload(current_state: str, target_state: str)` — Waterfall, 可变 dataclass
    - `VetoTransitionPayload(current_state: str, target_state: str)` — BAIL_VETO, frozen
    - `AfterTransitionPayload(old_state: str, new_state: str)` — Parallel, frozen
    - `BeforeWidgetRegisterPayload(name: str, slot: str)` — Waterfall, 可变
  **【防腐规定】该文件内严禁出现任何 PySide6 或外设相关的 import。**

## 3. 核心底座开发 (Core Engine) — 无界面的纯逻辑层

- [ ] 3.1 实现 `flow_hud/core/state_machine.py`。对标主引擎 `state/machine.py`。
    - 定义 `HudState` 枚举（Ghost, Pulse, Command）。
    - 定义白名单 `TRANSITIONS: dict[HudState, set[HudState]]` 守门。
    - 实现 `HudStateMachine`：持有当前状态，`transition(target)` 方法校验合法性后执行转换并返回 `(old_state, new_state)`，非法转换抛出 `IllegalTransitionError`。
    - **【防腐规定】该文件内严禁出现任何 PySide6 或外设相关的 import。**
- [ ] 3.2 验证状态机：编写 `pytest` 测试。覆盖所有合法路径和非法路径。发送特定 Intent，验证状态流转和异常抛出。**必须在终端跑通并生成正确的断言报告。**
- [ ] 3.3 实现 `flow_hud/core/events.py`。对标主引擎 `events.py` **全能力**。
    - 定义 `HudEventType` 枚举注册表（`MOUSE_GLOBAL_MOVE`, `STATE_TRANSITIONED`, `IPC_MESSAGE_RECEIVED`, `WIDGET_REGISTERED` 等）。
    - 定义 `HudEvent` 不可变容器（`type: HudEventType`, `timestamp: datetime`, `payload: Any`）。
    - 实现 `HudBackgroundEventWorker`（对标 `BackgroundEventWorker`）：拥有独立的 `Queue`，带重试和死信记录功能，非阻塞消费。
    - 实现 `HudEventBus`（继承 `QObject`）：利用 Qt Signal/Slot 底层封装。包含：
      - `subscribe(event_type, handler)` / `unsubscribe(event_type, handler)`
      - `emit(event_type, payload)` — 前台同步路径，等待全部 handler 完成
      - `emit_background(event_type, payload)` — 后台异步路径，投入 Worker 队列后立即返回
    - 底层 Signal 使用 `Qt.QueuedConnection` 确保跨线程安全。
- [ ] 3.4 实现 `flow_hud/core/hooks.py`。对标主引擎 `hooks.py` **全能力**。
    - 定义 `HudHookStrategy` 枚举（`PARALLEL`, `WATERFALL`, `BAIL`, `BAIL_VETO`, `COLLECT`）。
    - 定义 `HudHookSpec(name, strategy, description)` 数据类声明所有 HUD 钩子规格。
    - 实现 `HookBreaker` 熔断器（对标主引擎）：失败阈值、恢复窗口、三态（CLOSED/OPEN/HALF_OPEN）。
    - 实现 `HudHookManager`：
      - `register(implementor)` — 扫描 implementor 上与 HOOK_SPECS 同名的方法并注册。
      - `call(hook_name, payload)` — 按策略执行（PARALLEL 并发 / WATERFALL 传导 / BAIL 短路 / BAIL_VETO 投票 / COLLECT 收集），每个 handler 经过 HookBreaker 和超时保护。
      - `safe_mode` — 安全模式下跳过全部第三方钩子。
      - 所有超时/阈值参数从外部配置注入，无硬编码。
- [ ] 3.5 验证 EventBus + HookManager：编写 `pytest` 测试。验证事件订阅/发布、钩子各策略执行结果、熔断器触发保护行为。

## 4. 标准化插件机制 (Plugin Protocol) — 对标 `plugins/` 全套

- [ ] 4.1 创建 `flow_hud/plugins/manifest.py`。定义 `HudPluginManifest`（对标 `PluginManifest`）：
    - `@dataclass(frozen=True)` 声明：`name`, `version`, `description`, `author`, `requires`, `config_schema`。
- [ ] 4.2 创建 `flow_hud/plugins/base.py`。定义 `HudPlugin` 抽象基类（对标 `FlowPlugin`）：
    - 类属性 `manifest: HudPluginManifest`
    - 虚拟方法 `setup(ctx: HudPluginContext)` / `teardown()`
    - 只读属性 `name` → 返回 `manifest.name`
- [ ] 4.3 创建 `flow_hud/plugins/context.py`。对标主引擎 `plugins/context.py` **双层结构**：
    - **`HudPluginContext`（普通沙盒）**：
      - `subscribe_event(event_type, handler)` — 事件订阅（委托 EventBus）
      - `register_widget(name, widget)` — UI 插槽注册
      - `register_hook(implementor)` — 钩子注册
      - `get_extension_config(plugin_name)` → `dict` — 插件专属配置
      - `data_dir` (只读) / `safe_mode` (只读)
    - **`HudAdminContext(HudPluginContext)` 高权限超集**：
      - `@property state_machine` (只读) — 底层状态机引用
      - `@property event_bus` (只读) — 底层 EventBus 引用
      - `@property hook_manager` (只读) — 底层 HookManager 引用
    - 所有底层引用使用 `Any` 类型注释 + 只读 `@property`，防止覆写，避免强运行时依赖。
- [ ] 4.4 创建 `flow_hud/plugins/registry.py`。对标主引擎 `PluginRegistry`：
    - `register(plugin)` — 编程式注册
    - `discover()` → `list[str]` — 扫描 `entry_points(group="flow_hud.plugins")` 自动发现
    - `setup_all(ctx, admin_ctx, admin_names)` — 按白名单分级下发 Context 并调用 `plugin.setup()`
    - `teardown_all()` — 逆序清理
    - `get(name)` / `all()` / `names()`

## 5. 端口契约层 (Port Contract) — 对标 `client.py`

- [ ] 5.1 创建 `flow_hud/core/service.py`。定义 `HudServiceProtocol`（对标 `FlowClient Protocol`）：
    - 所有方法的入参只允许 `str`, `int`, `dict` 基础类型
    - 所有方法的返回值只允许 `dict` 或 `list[dict]`
    - 方法列表：`get_hud_state()`, `transition_to(target: str)`, `register_widget(name: str, slot: str)`, `list_plugins()`
- [ ] 5.2 实现 `HudLocalService`（对标 `LocalClient`），内部包装 `HudApp` 的操作，将领域对象 "剥皮" 为纯 `dict` 输出。

## 6. 配置驱动的 DI 编排器 (App Orchestrator) — 对标 `app.py`

- [ ] 6.1 创建 `flow_hud/core/config.py`。定义 `HudConfig` 数据类：
    - 插件加载列表、admin 白名单
    - HookBreaker 阈值（failure_threshold, recovery_timeout）
    - EventBus 超时参数
    - 路径配置（data_dir 等）
    - 支持从 `hud_config.toml` 文件加载
- [ ] 6.2 实现 `flow_hud/core/app.py`。创建 `HudApp`（对标 `FlowApp`）：
    - `__init__(config)`: 统一创建 EventBus、HookManager、StateMachine、PluginRegistry。构造 `HudPluginContext` 和 `HudAdminContext`。调用 `registry.discover()` + `registry.setup_all()`。连接事件处理器（`_wire_events`）。
    - `start()`: 启动 BackgroundEventWorker、初始化状态机。
    - `shutdown()`: 调用 `registry.teardown_all()`，停止 BackgroundEventWorker 并等待队列排空。
    - `register_storage_backend()` / `register_notifier_backend()` 等扩展注册点（按需保留）。

## 7. 多线程跨域安全测试 (Thread-Safety Spike Test)

- [ ] 7.1 编写 `tests/spike_event_threading.py` 打桩环境脚本。**全程不引入物理 GUI 窗体。**
- [ ] 7.2 创建 `DummyRadarPlugin`（对标 V1 的 pynput 雷达）：
    - 携带 `HudPluginManifest(name="dummy-radar")`
    - 在 `setup()` 中接收 `HudAdminContext`（因需直接 emit 事件）
    - 内部启动一个 `threading.Thread`，模拟每 100ms 在子线程中通过 `EventBus.emit()` 抛出一个 `MouseMovePayload`
- [ ] 7.3 创建 `DummyVisualPlugin`（对标 V1 的 UI 消费者）：
    - 携带 `HudPluginManifest(name="dummy-visual")`
    - 在 `setup()` 中接收 `HudPluginContext`（普通权限）
    - 通过 `ctx.subscribe_event(MOUSE_GLOBAL_MOVE, handler)` 订阅坐标事件，handler 中仅 `print` 回显
- [ ] 7.4 验证子线程产生的信号能安全无死锁地被主线程 Qt 队列调度并被 Listener 消化。
- [ ] 7.5 验证 HookBreaker 熔断保护：注入一个故意抛出异常的 `BadPlugin` 钩子实现，确认经过 N 次失败后被自动断路，且不影响其他正常插件。
- [ ] 7.6 **【检查点】** 将测试运行输出展示给用户。**必须和用户确认线程安全性和熔断行为符合预期，否则不得推进。**

## 8. UI 画布与"按组件插入"框架 (MVP Assembly)

- [ ] 8.1 实现 `flow_hud/adapters/ui_canvas.py`。建立一个完全透明、无边框、无系统焦点的底板 `QMainWindow` / `QWidget`。它只负责容纳插件通过 `HudPluginContext.register_widget()` 动态插入的小部件。
- [ ] 8.2 以插件形式验证显示：开发 `DebugTextPlugin`（携带 `HudPluginManifest(name="debug-text")`），在 `setup()` 阶段创建一个写着 "HUD V2 System Base initialized" 的 Qt 标签控件，并通过 `ctx.register_widget("debug", widget)` 注册到画布中央。
- [ ] 8.3 最终集装：在主控文件（如 `flow_hud/main.py`）中组装 `QApplication`、`HudApp`（加载 `DebugTextPlugin`）。运行，确保透明悬浮窗和文本能够在屏幕上安稳出现。
- [ ] 8.4 验证端口契约：通过 `HudLocalService` 的 `get_hud_state()` 方法从外部查询 HUD 状态，确认返回纯 `dict` 且不含任何 Qt 或领域对象引用。

> *任务组 8 完成后，整个 V2 空壳骨架落成。后续通过单独的变更将 pynput 鼠标逻辑、TCP 通信逻辑填入到该沙盒架构中。本任务集止步于架构的绝对安全落成。*
