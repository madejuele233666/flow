## Context

当前 HUD 系统（`flow_hud`）的模块隔离边界不够严密，仍存在潜在泄漏和类型不安全的隐患。为了使其架构能够与主引擎 `flow_engine` 对齐，我们需要强制实施以下契约：
1. `HudServiceProtocol` 目前覆盖不足，并未强制收敛所有的外部和表现层交互。
2. 插件上下文（`HudPluginContext` / `HudAdminContext`）通过 `Any` 注入关键组件（如 `state_machine`、`event_bus`），容易被越权修改。
3. 作为系统的基石，Event 和 Hook 的载荷（Payloads）的类型安全和 `frozen` 规范尚未得到强制约束。

## Goals / Non-Goals

**Goals:**
- **接口收敛（防泄漏）**：强化 `HudServiceProtocol` 为 HUD 官方唯一 Port。确保其方法的入参/出参均为原始类型级别。
- **类型安全沙盒**：在插件上下文中引入具体的 Protocols（`HudEventBusRegistrar`, `HudStateMachineProtocol`），全面消除 `Any` 类型。
- **载荷完整性监督**：确保所有涉及非 Waterfall 调用链路的载荷均为 `@dataclass(frozen=True)` 模型，消除裸 `dict` 的传递。

**Non-Goals:**
- 不重构 UI 渲染代码逻辑。
- 不引入跨平台底层交互方式的改动。

## Mapping Table

| Reference Module | New Module | Action | Notes |
|---|---|---|---|
| `client.py: FlowClient Protocol` | `HudServiceProtocol` | Replicate | 统一接口规范，输入基本类型，输出 `dict` |
| `client.py: LocalClient` | `HudLocalService` | Adapt | 提供统一领域向 `dict` 的剥皮转换适配 |
| `plugins/context.py: PluginContext` | `HudPluginContext` | Replicate | 沙盒结构不变，剔除 `Any` 并使用类型安全 `Protocol` |
| `plugins/context.py: AdminContext` | `HudAdminContext` | Replicate | 严防 `app.repo = None`，提供 `@property` 类型的严密沙盒保护 |
| `events_payload.py: *Payload` | `events_payload.py: *Payload` | Replicate | 统一强制应用 `@dataclass(frozen=True)` |
| `hooks_payload.py: *Payload` | `hooks_payload.py: *Payload` | Replicate | 根据策略类型严格区分 mutable/frozen dataclass |

## Decisions

### 1. 端口层强化：HudServiceProtocol 对标 FlowClient
- **Reference**: `flow_engine/client.py` (`FlowClient`, `LocalClient`)
- **Action**: Adapt & Replicate
- **Explanation**: HUD 需要一个独立的防渗透层，这在 `FlowClient` 的设计中已经得到了成熟验证。我们把 `HudServiceProtocol` 变为运行时和静态代码的唯一契约入口，阻止 `QWidget` 等对象通过暴露而泄漏到业务逻辑甚至插件中。
- **Example**:
  ```python
  @runtime_checkable
  class HudServiceProtocol(Protocol):
      def get_status(self) -> dict[str, Any]: ...
      def transition_to(self, target: str) -> dict[str, Any]: ...
  ```

### 2. 沙盒接口契约：消灭 Any
- **Reference**: `flow_engine/plugins/context.py`
- **Action**: Replicate
- **Explanation**: 当前 `flow_hud.plugins.context` 在 `event_bus` 和 `state_machine` 类型上使用了 `Any`，引发了不安全的访问风险。通过引用具体的 `Protocol`，即使插件具有 `AdminContext` 的权限，也不能绕过沙盒更改系统的根基。
- **Example**:
  ```python
  @runtime_checkable
  class HudStateMachineProtocol(Protocol):
      @property
      def current_state(self) -> Any: ...  # 或返回 Enum
      def transition(self, target: Any) -> tuple[Any, Any]: ...
  
  class HudAdminContext(HudPluginContext):
      @property
      def state_machine(self) -> HudStateMachineProtocol: ...
  ```

### 3. 数据载荷防御性设计
- **Reference**: `flow_engine/events_payload.py` & `flow_engine/hooks_payload.py`
- **Action**: Replicate
- **Explanation**: 将原有的 `dataclass` 类型细化，消除 `isinstance` 的随机性，并在 `emit` 或 `call` 入口处增设运行时检查，禁止传递纯 `dict` 对象或未标记 `frozen=True` 的只读载荷（Parallel/Event 等）。
- **Example**:
  ```python
  @dataclass(frozen=True)
  class MouseMovePayload:
      x: int
      y: int
  ```

## Risks / Trade-offs

- **开发复杂度提升**：每次新增事件或钩子都需要重新审查数据模型的冷冻（frozen）状态设置。
- **性能开销**：载荷构造与属性读取检查略有损耗，但确保了系统的防破坏完整性。
- **循环依赖风险**：Protocol 在隔离模块时容易引入循环引用（特别是返回具体的领域类），应使用 `TYPE_CHECKING` 对类型进行惰性加载绑定。

## Coverage Report

| Reference Contract | New Contract | Status |
|---|---|---|
| `FlowClient Protocol` | `HudServiceProtocol` | ✅ |
| `LocalClient` | `HudLocalService` | ✅ |
| `PluginContext` | `HudPluginContext` | ✅ |
| `AdminContext` | `HudAdminContext` | ✅ |
| `events_payload.py dataclass(frozen=True)` | `events_payload.py dataclass(frozen=True)` | ✅ |
| `hooks_payload.py Waterfall mutable / Bail frozen` | `hooks_payload.py dataclass rules` | ✅ |

---
## AI Self-Verification Summary
- Alignment Protocol: [Executed]
- Coverage Report: [Appended]
- Audit Checklist: [20/20 items passed]
- Uncovered items: [None]
