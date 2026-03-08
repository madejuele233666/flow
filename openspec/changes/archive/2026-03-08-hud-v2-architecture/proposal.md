## Why

第一代 HUD (hud-v1-prototype) 成功验证了在 Windows 侧使用 PySide6 实现全局鼠标穿透、通过 pynput 获取跨屏鼠标事件，以及利用 TCP 连接 WSL 内的 Flow 引擎进行全双工通信的可行性。然而，为了追求快速验证，V1 原型的各个模块（组件 UI、后台线程、网络 IO）形成了强耦合的"大泥球"结构，导致后续功能难以扩展，也使得代码丧失了独立可测试性。

为此，我们将**严格复刻** `flow_engine` 主程序后端经过实战检验的架构模型，对 HUD 进行彻底的 V2 架构重构。**不是"借鉴精神"，而是逐层对齐每一个架构契约**。主引擎的成功解耦模式具体包括：

### 1. 端口契约与防泄漏 (Port Contract & Anti-Leakage)
主引擎通过 `FlowClient Protocol` 定义了绝对纯粹的端口契约。输入参数只允许基础类型 (`str`, `int`)，输出永远是剥离了面向对象特性的 `dict` 或 `list`。这彻底杜绝了领域模型泄漏。

**HUD 对标**：HUD 需要定义自己的 `HudServiceProtocol`。核心引擎对外暴露的操控接口（状态转移、小部件注册）必须以纯数据类型（`str`, `enum`, `dict`）交互，插件和适配器永远拿不到核心对象的原始引用。

### 2. 双层权限沙盒 (Tiered Plugin Context)
主引擎的 `PluginContext` 只暴露安全的注册 API（`register_hook`, `register_notifier` 等），而 `AdminContext` 在此基础上额外开放了底层控制流（`engine`, `event_bus`）。权限分级通过白名单机制实施。

**HUD 对标**：HUD 必须复刻此双层沙盒。普通插件（如第三方统计面板）只能通过 `HudPluginContext` 注册事件订阅和 UI 插槽；受信任插件（如内置 IPC 桥接器）才能通过 `HudAdminContext` 触碰底层状态机和 EventBus。

### 3. 强类型载荷 (Typed Payloads)
主引擎的事件和钩子全部使用 `frozen dataclass` 载荷替代了弱类型 `dict` 传参，提供 IDE 自动补全和 mypy 静态检查。

**HUD 对标**：HUD 的 EventBus 必须同样使用强类型 `@dataclass(frozen=True)` 载荷（如 `MouseMovePayload`, `StateTransitionPayload`），杜绝 `event.data.get("xxx")` 的拼写错误地狱。

### 4. 事件总线的双路径执行 (Dual-Path EventBus)
主引擎区分了前台同步路径 `emit()` 和后台异步路径 `emit_background()`。后者由带重试和死信队列的 `BackgroundEventWorker` 安全消费。

**HUD 对标**：HUD 的 EventBus 基于 Qt Signal/Slot 封装，但同样必须区分关键路径（状态变更广播，必须同步等待完成）和非关键路径（日志、统计上报，投入后台队列即返回）。

### 5. 钩子系统的精密控制 (Hook System with Strategies & Circuit Breaker)
主引擎的 `HookManager` 支持五种执行策略（`PARALLEL`, `WATERFALL`, `BAIL`, `BAIL_VETO`, `COLLECT`），并为每个 handler 绑定独立的 `HookBreaker` 熔断器（含超时控制和失败计数）。

**HUD 对标**：HUD 必须复刻此钩子系统。特别是 `BAIL_VETO` 策略可用于 UI 状态转换的拦截校验（例如，某插件认为网络未连接时否决进入 Command 态）。`HookBreaker` 用于保护 Qt 主事件循环免受劣质插件的超时或崩溃影响。

### 6. 声明式插件元数据与自动发现 (Declarative Manifest & Auto-Discovery)
主引擎要求所有插件携带 `PluginManifest`（name, version, requires 等），并通过 Python `entry_points` 实现 pip install 即注册。

**HUD 对标**：HUD 插件必须携带 `HudPluginManifest`，并支持 `entry_points` 自动发现，使第三方 HUD 扩展能够通过 `pip install` 无缝接入。

### 7. 工厂模式与配置驱动 (Factory Pattern & Config-Driven Assembly)
主引擎的 `FlowApp` 通过配置字符串动态解析存储后端和通知后端，而非硬编码 `import`。

**HUD 对标**：`HudApp` 必须同样支持配置驱动。例如，哪些插件被加载、哪些插件拥有 Admin 权限、EventBus 的超时参数，都应从 `hud_config.toml` 读取而非散落在代码中。

## What Changes

1.  **废弃并移除 V1 代码**：彻底清理当前高度耦合的 HUD 原型代码。
2.  **引入完整的核心微引擎（对标 `flow_engine` 每一层）**：
    *   **端口层**：构建 `HudServiceProtocol`（对标 `FlowClient Protocol`），所有对外交互通过纯数据类型的方法契约。
    *   **事件层**：构建基于 Qt Signal/Slot 的跨线程安全 `EventBus`，包含前台同步 `emit()` 和后台安全 `emit_background()` 双路径。所有事件使用强类型 `frozen dataclass` 载荷。
    *   **钩子层**：构建带多策略执行引擎和 `HookBreaker` 熔断器的 `HookManager`（对标主引擎 `hooks.py` 全能力）。
    *   **状态层**：构建纯数据层驱动的 `HudStateMachine`（Ghost / Pulse / Command 三态），通过白名单 `TRANSITIONS` 守门。
    *   **插件层**：构建双层沙盒 `HudPluginContext` / `HudAdminContext`，声明式 `HudPluginManifest`，以及支持 `entry_points` 自动发现的 `HudPluginRegistry`。
    *   **编排层**：构建 `HudApp` 作为配置驱动的 DI 组装工厂，管理全生命周期。
3.  **实施两步走战略**：
    *   **Step A (本期范围)**：建立完全没有任何视觉界面的空壳框架、全部接口定义及通信协议，骨架测试 100% 通过。
    *   **Step B (下期扩展)**：在测试通过的沙盒架构中，将 V1 业务代码迁移到具体插件实现中。

## Capabilities

### New Capabilities
- `core-engine`: HUD 核心的配置驱动 DI 编排器、双路径 EventBus（跨线程安全 + 后台消费队列）、强类型载荷系统、白名单状态机。
- `hook-system`: 带多策略执行引擎（PARALLEL / WATERFALL / BAIL_VETO / COLLECT）和 HookBreaker 熔断器的钩子系统。
- `plugin-system`: 双层权限沙盒（HudPluginContext / HudAdminContext）、声明式 HudPluginManifest、entry_points 自动发现。
- `port-contract`: HudServiceProtocol 端口契约层，所有对外交互使用纯数据类型，杜绝领域模型泄漏。

### Modified Capabilities
- 

## Impact

本项修改集中在 `flow_hud`（如果在现有分支下则是与 HUD 相关的全套文件）。在 `flow_engine` 侧（即 WSL 后端）不受任何影响，后端的 IPC 和现有 API 将被无缝重用。
对所有的 HUD 测试将产生颠覆性影响，所有的逻辑将不再要求唤起真实的 PySide6 窗体环境即可做全覆盖测试（比如网络数据模拟和状态断言）。
