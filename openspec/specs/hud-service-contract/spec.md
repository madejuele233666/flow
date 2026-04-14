# HUD Service Contract

## Purpose
Define a strict boundary and communication protocol for the HUD service that returns truthful canonical-runtime outcomes without leaking domain objects.

## Requirements

### Requirement: Standardize HUD Communication Port (RPC-ready)
HUD MUST keep `HudServiceProtocol` as the external control boundary, and service methods MUST return operationally truthful results from canonical runtime pipelines instead of placeholder acknowledgments.

#### Scenario: Querying HUD State via Service
- **WHEN** 调用 `service.get_status()`
- **THEN** 返回一个 `dict`，包含 `state` (str) 和 `active_plugins` (list[str])，不含任何领域对象。

#### Scenario: State transition via service uses canonical orchestration
- **WHEN** caller executes `service.transition_to("pulse")`
- **THEN** service delegates to canonical app transition orchestration
- **AND** response reflects actual transition lifecycle result (`old_state`, `new_state`).

#### Scenario: Widget reservation reports real runtime outcome
- **WHEN** caller executes `service.register_widget(name, slot)` through service boundary
- **THEN** response MUST reflect real reservation/validation success or failure from runtime pipeline
- **AND** response MUST explicitly indicate this path is reservation metadata and not live widget mount (for example `mounted=false`)
- **AND** service MUST NOT return unconditional success for invalid slot or rejected reservation.

#### Scenario: No domain object leakage
- **WHEN** any service method returns data
- **THEN** payload contains only primitive-safe structures (`dict`, `list`, scalar values)
- **AND** does not leak `HudState`, widget objects, or internal manager instances.
