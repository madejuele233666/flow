# Payload Integrity

## Purpose
Ensure all communication payloads (Events, Hooks) within the HUD system are type-safe and adhere to immutability rules to prevent accidental state mutation and domain object leakage.

## Requirements

### Requirement: Immutable Notification Payloads
所有用于事件（Events）和 Parallel/Bail 钩子的载荷必须强制标记为 `frozen=True`。

#### Scenario: Enforcing Frozen Dataclasses
- **WHEN** 定义一个 `AfterTransitionPayload`
- **THEN** 它必须使用 `@dataclass(frozen=True)`，尝试在插件中修改其属性应抛出 `FrozenInstanceError`。

#### Scenario: Payload Integrity Check
- **WHEN** 发送一个事件并传递载荷
- **THEN** 载荷必须通过 dataclass 验证，严禁直接传递裸 `dict` 或 `None`。
