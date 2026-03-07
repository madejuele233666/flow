## Context

第一代 HUD (hud-v1-prototype) 成功验证了底层技术栈（PySide6 鼠标穿透、pynput 守护线程监听、WSL TCP 长连接），但在实现过程中，为了快速行进，不同并发模型（Qt 主线程、鼠标后台线程、asyncio 协程）之间的代码耦合严重。`app.py` 内部发生了硬编码组装，`ui.py` 承载了过多的控制逻辑，导致整个系统难以测试和扩展。

为彻底修正这一问题，本设计将**逐层对齐** `flow_engine` 主引擎的已验证架构契约，从零搭建 HUD V2 的基础底座。**对标粒度精确到每一个模块文件**，不允许"精神借鉴"式的模糊落地。

## Goals / Non-Goals

**Goals:**
*   **端口层** — 建立 `HudServiceProtocol` 端口契约（对标主引擎 `client.py` 的 `FlowClient Protocol`），所有对外方法的入参和返回值只允许基础类型 / `dict` / `list`，杜绝领域模型泄漏。
*   **事件层** — 建立基于 Qt Signal/Slot 封装的跨线程安全 `EventBus`（对标主引擎 `events.py`），必须包含前台 `emit()` 同步路径和后台 `emit_background()` 异步路径。后台路径由带重试 + 死信队列的 `BackgroundEventWorker` 消费。所有事件使用强类型 `@dataclass(frozen=True)` 载荷（对标 `events_payload.py`）。
*   **钩子层** — 建立 `HookManager`（对标主引擎 `hooks.py` 全能力），支持五种执行策略（`PARALLEL`, `WATERFALL`, `BAIL`, `BAIL_VETO`, `COLLECT`），并为每个 handler 绑定独立的 `HookBreaker` 熔断器（含超时控制和失败计数）。钩子使用强类型载荷（对标 `hooks_payload.py`）。
*   **状态层** — 建立纯数据层驱动的 `HudStateMachine`（对标主引擎 `state/machine.py`），通过白名单 `TRANSITIONS` 字典守门，非法转换直接抛出 `IllegalTransitionError`。
*   **插件层** — 建立双层权限沙盒（对标 `plugins/context.py`）：`HudPluginContext`（普通插件：只能订阅事件、注册 UI 插槽）和 `HudAdminContext`（受信任插件：额外拥有状态机和 EventBus 的只读引用）。插件基类 `HudPlugin` 携带声明式 `HudPluginManifest`（对标 `PluginManifest`），注册表 `HudPluginRegistry` 支持 `entry_points` 自动发现（对标 `registry.py`）。
*   **编排层** — 建立 `HudApp` 作为配置驱动的 DI 组装工厂（对标 `app.py` 的 `FlowApp`），通过配置文件决定加载哪些插件、授予哪些 Admin 权限。管理 `start()` / `shutdown()` 全生命周期。
*   实现无 GUI 环境下的 100% 测试覆盖率（骨架部分）。

**Non-Goals:**
*   **本设计阶段绝对禁止实现任何具体业务逻辑**：不实现任何具体的 PySide6 动画，不实现在屏幕上绘制具体像素，不拦截特定的网络业务包。
*   不改动 `flow_engine`（WSL 端）现有的任何代码和协议。

## Decisions

### Decision 1: 端口契约防泄漏 — `HudServiceProtocol`
对标主引擎 `FlowClient Protocol`。

HUD 需要定义自己的端口契约：

```python
class HudServiceProtocol(Protocol):
    """HUD 对外暴露的唯一操控契约。

    所有方法返回纯 dict 或 list[dict]，不暴露领域对象。
    """
    def get_hud_state(self) -> dict: ...                      # 返回如 {"state": "ghost", "active_plugins": [...]}
    def transition_to(self, target: str) -> dict: ...          # 入参为状态字符串，而非枚举对象
    def register_widget(self, name: str, slot: str) -> dict: ... # 纯字符串约定插槽位置
    def list_plugins(self) -> list[dict]: ...
```

**设计要点**：
- 入参只允许 `str`, `int`, `dict`，严禁传入 `QWidget` 或 `HudState` 对象。
- 返回值永远是扁平的 `dict`，前端/测试框架可以无依赖地消费。
- 对标主引擎 `FlowClient` 在 `LocalClient` 中将内部对象 "剥皮" 为 `dict` 的做法。

### Decision 2: 强类型事件载荷 — `events_payload.py`
对标主引擎 `events_payload.py` 和 `hooks_payload.py`。

```python
# flow_hud/core/events_payload.py
@dataclass(frozen=True)
class MouseMovePayload:
    """全局鼠标坐标更新。"""
    x: int
    y: int
    screen_index: int = 0

@dataclass(frozen=True)
class StateTransitionedPayload:
    """HUD 状态完成转换后的广播。"""
    old_state: str
    new_state: str

@dataclass(frozen=True)
class IpcMessageReceivedPayload:
    """从 Flow Engine 后端接收到的 IPC 消息。"""
    method: str
    data: dict
```

**设计要点**：
- `frozen=True` 保证事件容器不可变。
- 杜绝 `event.data["x"]` 式弱类型传参。
- 每新增一种事件，必须同步新增载荷 dataclass。

### Decision 3: 双路径 EventBus — 基于 Qt Signal/Slot 封装
对标主引擎 `EventBus` + `BackgroundEventWorker`。

```python
class HudEventBus(QObject):
    """跨线程安全的事件总线。

    基于 Qt Signal/Slot 保证线程安全投递。
    """
    _signal = Signal(str, object)  # (event_type_str, payload)

    def emit(self, event_type: HudEventType, payload: Any = None) -> None:
        """前台同步路径 — 等待全部处理器完成。"""
        ...

    def emit_background(self, event_type: HudEventType, payload: Any = None) -> None:
        """后台异步路径 — 投入 Worker 队列后立即返回。"""
        ...

    def subscribe(self, event_type: HudEventType, handler: Callable) -> None: ...
    def unsubscribe(self, event_type: HudEventType, handler: Callable) -> None: ...
```

**关键技术决策**：
- 底层通信必须使用 Qt 原生的 `Signal/Slot` 机制（`Qt.QueuedConnection`）。这是解决"子线程 pynput → Qt 主线程 UI 更新"导致崩溃的**唯一标准手段**。
- `emit_background()` 投入一个带重试和死信记录的 `BackgroundEventWorker`（对标主引擎），非关键路径（统计上报、日志调试）走此通道，绝不阻塞 Qt 事件循环。

### Decision 4: 带多策略和熔断器的钩子系统 — `HookManager`
对标主引擎 `hooks.py`（含 `HookSpec`, `HookStrategy`, `HookBreaker`, `HookManager`）**全能力复刻**。

```python
class HudHookStrategy(str, Enum):
    PARALLEL = "parallel"       # 同步并发，全部执行
    WATERFALL = "waterfall"     # 瀑布传导，原地修改 payload
    BAIL = "bail"               # 第一个非 None 返回值立即短路
    BAIL_VETO = "bail_veto"     # 一票否决式投票
    COLLECT = "collect"         # 收集所有返回值

@dataclass(frozen=True)
class HudHookSpec:
    name: str
    strategy: HudHookStrategy = HudHookStrategy.PARALLEL
    description: str = ""
```

**关键应用场景**：
- `before_state_transition` (BAIL_VETO): 插件否决 Ghost→Command 转换（如"网络未连接，禁止进入主控态"）。
- `on_after_state_transition` (PARALLEL): 状态变更后的通知广播。
- `on_widget_register` (WATERFALL): 允许插件修改即将被挂载的小部件属性。

**HookBreaker 熔断器（每个 handler 独立绑定）**：
- 失败次数达阈值后自动断路保护，防止劣质插件拖垮 Qt 主事件循环。
- 超时控制：handler 执行超时自动中断并记录。
- 恢复窗口：断路一段时间后自动尝试半开放状态。

### Decision 5: 双层权限沙盒 — `HudPluginContext` / `HudAdminContext`
对标主引擎 `plugins/context.py` 的 `PluginContext` / `AdminContext`。

```python
class HudPluginContext:
    """普通插件的安全沙盒 — 只暴露注册型 API。"""
    def subscribe_event(self, event_type, handler) -> None: ...
    def register_widget(self, name: str, widget: Any) -> None: ...
    def register_hook(self, implementor: object) -> list[str]: ...
    def get_extension_config(self, plugin_name: str) -> dict: ...

class HudAdminContext(HudPluginContext):
    """受信任插件的高权限沙盒 — PluginContext 的超集。

    额外开放底层引用（只读 @property）。
    """
    @property
    def state_machine(self) -> Any: ...
    @property
    def event_bus(self) -> Any: ...
    @property
    def hook_manager(self) -> Any: ...
```

**设计要点**：
- 普通插件（第三方统计面板、自定义主题等）只拿到 `HudPluginContext`，无法触碰底层引擎。
- 受信任插件（内置 IPC 桥接器、内置 Radar 等）通过白名单机制拿到 `HudAdminContext`。
- `AdminContext` 暴露的底层引用一律为只读 `@property`，防止被覆写。

### Decision 6: 声明式插件元数据与自动发现
对标主引擎 `PluginManifest` + `PluginRegistry.discover()`。

```python
@dataclass(frozen=True)
class HudPluginManifest:
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    requires: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)

class HudPlugin(ABC):
    manifest: HudPluginManifest = HudPluginManifest(name="unnamed")
    def setup(self, ctx: HudPluginContext) -> None: ...
    def teardown(self) -> None: ...

ENTRY_POINT_GROUP = "flow_hud.plugins"

class HudPluginRegistry:
    def register(self, plugin: HudPlugin) -> None: ...
    def discover(self) -> list[str]: ...    # 扫描 entry_points
    def setup_all(self, ctx, admin_ctx=None, admin_names=None) -> None: ...
    def teardown_all(self) -> None: ...
```

### Decision 7: 配置驱动的 DI 编排器 — `HudApp`
对标主引擎 `FlowApp`。

```python
class HudApp:
    """HUD 的顶层编排器。

    职责：
    1. 加载配置 (hud_config.toml)
    2. 实例化全部核心模块（EventBus, HookManager, StateMachine）
    3. 构造 PluginContext / AdminContext 并注入
    4. 驱动 PluginRegistry.setup_all()
    5. 管理 start() / shutdown() 全生命周期
    """
    def __init__(self, config: HudConfig | None = None): ...
    def start(self) -> None: ...
    def shutdown(self) -> None: ...
```

**设计要点**：
- 所有模块由 `HudApp.__init__` 统一创建和注入，各模块零自身实例化。
- 通过 `hud_config.toml` 驱动：加载哪些插件、admin 白名单、HookBreaker 阈值、EventBus 超时参数。
- `shutdown()` 必须优雅关闭：调用 `registry.teardown_all()`，等待 `BackgroundEventWorker` 队列排空。

### Decision 8: MVP 防腐层与 UI 画布隔离
借鉴主引擎的 `防腐层 (Anti-corruption Layer)` 思想，结合 Model-View-Presenter (MVP) 模式彻底分离：
*   **网络 IO (IPC Client)**: 作为独立插件实现（接收 `HudAdminContext`）。接收到的网络包通过 `EventBus.emit()` 发送 `IPC_MESSAGE_RECEIVED` 事件。严禁直接调用 UI 函数。
*   **硬件输入 (Mouse Radar)**: 作为独立插件实现。pynput 获取到坐标后，仅通过 `EventBus.emit()` 抛出 `MOUSE_GLOBAL_MOVE` 事件。
*   **视图层 (View) 与 UI 插件化**: 主控 UI 只能是一个极简的"透明画布"和"事件监听器"。HUD 的真正内容（如环形状态、通知面板）亦被解构为提供 `QWidget` 的图形插件，这些图形插件在运行时由其关联逻辑插件通过 `HudPluginContext.register_widget()` 动态注册到画布中。视图通过监听 `EventBus` 上的 `STATE_TRANSITIONED` 事件进行单纯的重绘。

### Decision 9: 两段式开发路径保障
*   **Step A (本期范围)**: 只编写 Core Engine 和所有 Interface。编写 Mock 插件（纯控制台打桩）验证事件能否在多线程间正确流转。100% 测试通过后才能进入 Step B。
*   **Step B (下期拓展)**: 将 V1 的业务代码迁移到特定的插件实现中。

## Risks / Trade-offs

*   **Risk**: HUD 强依赖 PySide6 (Qt) 的事件循环机制。如果我们用标准的 `asyncio` 协程处理 IPC，并且用纯 Python 线程处理 pynput，三者如何安全地融合在同一个 EventBus 中是一个挑战。
    **Mitigation**: EventBus 底层强制使用 `QObject.Signal` + `Qt.QueuedConnection`，确保所有跨线程事件被安全压入 Qt 主事件循环。结合 `qasync` 或 `QMetaObject.invokeMethod` 作为辅助手段。
*   **Risk**: 完全复刻主引擎架构导致初始代码量急剧膨胀（HookManager 含熔断器、双层 Context、强类型载荷等均需独立实现）。
    **Mitigation**: 这是消除"大泥球"必须付出的前期成本。主引擎的实战已证明此投入的长期收益远超初期代码量。
*   **Risk**: `entry_points` 自动发现机制在开发阶段可能过于复杂。
    **Mitigation**: 初期优先使用编程式 `registry.register()` 注册方式，`discover()` 作为可选增强。
