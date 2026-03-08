# Typed Plugin Sandbox

## Purpose
The HUD Plugin Sandbox should be strictly typed using Protocols to ensure IDE assistance, static analysis compatibility, and clear boundaries between plugin logic and core HUD components.

## Requirements

### Requirement: Typed Plugin Sandbox
插件上下文（`HudPluginContext` 和 `HudAdminContext`）必须通过强类型 Protocol 暴露组件（EventBus, StateMachine），替代原有的 `Any` 类型。

#### Scenario: IDE Completion for EventBus
- **WHEN** 在插件中访问 `ctx.event_bus.subscribe`
- **THEN** 理想情况下应提供方法签名 and 类型提示，且禁止直接修改 `event_bus` 的属性。

#### Scenario: Administrative Access via Protocol
- **WHEN** `HudAdminContext` 的 `state_machine` 被访问
- **THEN** 它必须返回一个符合 `HudStateMachineProtocol` 的对象，提供有限且安全的交互能力。
