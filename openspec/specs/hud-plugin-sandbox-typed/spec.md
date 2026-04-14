# Typed Plugin Sandbox

## Purpose
Define a strictly typed HUD plugin sandbox that exposes canonical runtime capabilities through constrained Protocol boundaries.

## Requirements

### Requirement: Typed Plugin Sandbox
`HudPluginContext` and `HudAdminContext` MUST remain Protocol-typed and MUST expose canonical runtime APIs for transition/widget operations through typed boundaries rather than ad hoc direct object mutation.

#### Scenario: Typed event and hook boundaries remain enforced
- **WHEN** 插件访问 `ctx.event_bus` 或 `ctx.register_hook(...)`
- **THEN** IDE/type checker can resolve typed signatures
- **AND** plugin cannot mutate host internals through untyped escape hatches.

#### Scenario: Typed admin state access stays constrained
- **WHEN** `HudAdminContext` exposes state metadata
- **THEN** it is read-only/inspection-only data
- **AND** context API MUST NOT expose a direct `state_machine.transition(...)` mutation path that bypasses canonical orchestrator.

### Requirement: Context APIs Integrate Canonical Runtime Pipelines
Context-level state/widget operations MUST bind to host canonical orchestration paths so plugin-facing APIs and service-facing APIs share one runtime truth.

#### Scenario: Plugin widget registration through context
- **WHEN** 插件调用 context widget registration API
- **THEN** request enters the same canonical host widget pipeline used by service/runtime
- **AND** resulting slot and mount behavior matches emitted runtime events.

#### Scenario: Plugin transition request through context
- **WHEN** 插件触发状态迁移请求（如 admin 插件策略控制）
- **THEN** request enters canonical transition orchestrator with veto/event lifecycle
- **AND** result semantics match service boundary behavior.

#### Scenario: Direct transition bypass is rejected
- **WHEN** 插件尝试通过 context 访问并直接调用状态机转移能力
- **THEN** sandbox contract MUST reject or not expose that path
- **AND** transition behavior remains enforceable through canonical orchestrator only.
