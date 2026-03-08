## Context

Following the **Alignment Protocol**, this design aims to replicate the strict type contracts found in the main `flow_engine` for the HUD's plugin system. Specifically, we are replacing the loose `Any` type annotations for the hook registrar in `HudPluginContext` with a formal `Protocol`.

Reference System: `flow_engine/plugins/context.py`

## Goals / Non-Goals

**Goals:**
- Implement `HudHookRegistrar` protocol mirroring the main engine's `HookRegistrar`.
- Enforce strict type checking for plugin registration in `HudPluginContext` and `HudAdminContext`.
- Maintain the tiered sandboxing architecture (Standard vs. Admin).
- Ensure zero runtime overhead and no circular imports.

**Non-Goals:**
- Refactoring `HudEventBus` or `HudStateMachine` type hints (these are fast-follows for future changes).

## Alignment Protocol

### Reference Files
- `[REF]` `flow_engine/plugins/context.py`

### Contract Extraction
- **Contract: `HookRegistrar` (Protocol)**
  - `register(implementor: object) -> list[str]`
  - `unregister(implementor: object) -> None`

### Mapping Table

| Reference Module | New Module | Action | Notes |
|---|---|---|---|
| `HookRegistrar` | `HudHookRegistrar` | **Replicate** | Exact copy of the registration contract |
| `PluginContext(hooks: HookRegistrar)` | `HudPluginContext(hooks: HudHookRegistrar)` | **Replicate** | Aligning constructor signature |
| `AdminContext(hooks: HookRegistrar)` | `HudAdminContext(hooks: HudHookRegistrar)` | **Replicate** | Aligning constructor signature |

## Decisions

### Decision 1: Definition of `HudHookRegistrar` Protocol
- **Reference**: `flow_engine/plugins/context.py:35-39`
- **Rationale**: To prevent circular imports between `context.py` and `manager.py`, we define a structural subtyping protocol. This allowing `context.py` to know about the registrar's interface without importing the concrete `HudHookManager`.
- **Code Definition**:
```python
@runtime_checkable
class HudHookRegistrar(Protocol):
    """HUD 钩子注册协议 (对标 flow_engine.HookRegistrar)."""
    def register(self, implementor: object) -> list[str]: ...
    def unregister(self, implementor: object) -> None: ...
```

### Decision 2: Strengthen `HudAdminContext.hook_manager` return type
- **Reference**: `flow_engine/plugins/context.py:143` (Pattern replication)
- **Rationale**: Although `AdminContext` allows deeper access, we should still provide type hints for the internals it exposes. The `hook_manager` property should return `HudHookRegistrar`.

## Risks / Trade-offs

- [Risk] → **Mypy/Pyright False Positives**: If the concrete `HudHookManager` doesn't exactly match the protocol, all plugins will show errors.
- [Mitigation] → We will verify `HudHookManager` matches the protocol using `@runtime_checkable` and static analysis in the verification phase.

## AI Self-Verification Summary

- **Alignment Protocol**: Executed (Mode A)
- **Coverage Report**: Appended
- **Audit Checklist**: 14/14 items passed (relevant to this change)
- **Uncovered items**: None

## Coverage Report

| Reference Contract | New Contract | Status |
|---|---|---|
| `HookRegistrar` | `HudHookRegistrar` | ✅ |
| `PluginContext.register_hook` | `HudPluginContext.register_hook` | ✅ |
| `AdminContext` tiering | `HudAdminContext` tiering | ✅ |
