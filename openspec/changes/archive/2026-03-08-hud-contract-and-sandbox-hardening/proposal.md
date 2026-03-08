## Why

HUD 目前虽然建立了初步的架构，但在类型安全、沙盒隔离和数据一致性方面仍存在显著隐患：
1. **领域对象泄露**：缺乏一个像 `flow_engine` 那样的 `FlowClient` 强一致性契约。外部调用者或表现层（Qt）直接触碰 `HudApp` 或内部领域对象，增加了耦合风险，且不利于后续可能的 RPC/跨进程拆分。
2. **插件沙盒漏洞**：`HudPluginContext` 和 `HudAdminContext` 中关键组件（EventBus, StateMachine）使用 `Any` 类型，导致插件可以随意访问和修改内部属性，违背了低耦合和属性隔离的初衷，且缺乏 IDE 补全。
3. **数据载荷不安全**：虽然建立了载荷框架，但缺乏全局性的 `frozen=True` 强制约束和强类型检查，容易在插件流水线中出现意外的状态篡改。

## What Changes

1. **引入全能力 HudServiceProtocol**：
   - 完善并强化 `HudServiceProtocol`，确立其作为 HUD 对外交互的唯一 Port。
   - 确保所有方法只接受基础类型参数，只返回纯 dict 数据。
   - 实现 `HudLocalService` 作为适配器。
2. **沙盒上下文强类型化**：
   - 引入 `HudEventBusRegistrar` 和 `HudStateMachineProtocol`。
   - 将 `HudPluginContext` 和 `HudAdminContext` 中的 `Any` 替换为这些 Protocol，实现安全且受限的访问。
3. **载荷规范化与安全性加固**：
   - 严查并确保所有非 Waterfall 载荷（Event 和 Parallel/Bail Hook）全部标记为 `@dataclass(frozen=True)`。
   - 在 EventBus 和 HookManager 中引入基本的类型检查逻辑，确保不传递裸 dict。

## Capabilities

### New Capabilities
- `hud-service-contract`: 定义并实现 HUD 系统的标准 RPC/服务契约，确立抗泄漏边界。
- `hud-plugin-sandbox-typed`: 为插件提供强类型的沙盒接口，提升代码质量与隔离安全性。
- `hud-payload-integrity`: 建立并实施全局载荷不变性约束。

### Modified Capabilities
- `plugin-system`: 强化插件上下文的类型定义与访问权限控制。

## Impact
- `flow_hud.core.service`: 重构并强化。
- `flow_hud.plugins.context`: 将 `Any` 替换为专用 Protocol。
- `flow_hud.core.events_payload`: 全面审计并加固。
- `flow_hud.core.hooks_payload`: 全面审计并加固。
- `flow_hud.core.app`: 更新 DI 注入方式。
