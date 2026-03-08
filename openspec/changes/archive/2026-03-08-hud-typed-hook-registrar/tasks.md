## 1. Protocol Definition [CORE]

- [x] 1.1 In `flow_hud/plugins/context.py`, implement `HudHookRegistrar` Protocol.
  【防腐规定】This file MUST NOT import `HudHookManager` class to avoid circular dependency.
- [x] 1.2 Add `@runtime_checkable` decorator to the protocol for runtime validation support.
- [x] 1.3 【检查点】Verify that `HudHookRegistrar` definition is visible and correctly typed in the active editor.

## 2. Context Integration [CORE]

- [x] 2.1 Update `HudPluginContext.__init__` signature: change `hooks: Any` to `hooks: HudHookRegistrar`.
- [x] 2.2 Update `HudAdminContext.__init__` signature: change `hooks: Any` to `hooks: HudHookRegistrar`.
- [x] 2.3 Update `HudAdminContext.hook_manager` property return type from `Any` to `HudHookRegistrar`.
- [x] 2.4 【检查点】Run `pyright` or `mypy` on `flow_hud/plugins/context.py` to ensure zero internal type errors.

## 3. System Verification [CORE]

- [x] 3.1 Verify `HudHookManager` (in `flow_hud/core/hook_manager.py` or similar) correctly implements the Protocol.
- [x] 3.2 Ensure `HudApp` correctly instantiates and passes the HookManager to the Contexts.
- [x] 3.3 【检查点】Present `pytest` output or a simple startup log showing HUD initializes without Circular Import errors.
  MUST obtain explicit user confirmation before finalizing.
