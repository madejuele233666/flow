## Why

Currently, internal HUD plugins like `HudPluginContext` use simplified registration protocols, bypassing strict type validation by annotating the registrar as `Any`. This `HookRegistrar Any` simplification undermines type safety and can lead to runtime errors when plugins interact with the registrar unexpectedly. Introducing a strongly-typed `Protocol` for the Registrar checkout constraints will enforce strict, compile-time and IDE type checking, ensuring robust and error-free plugin registration in the HUD ecosystem.

## What Changes

- Replace `Any` type annotations for `HookRegistrar` in HUD plugins with a strictly defined `Protocol`.
- Define a `HookRegistrarProtocol` (or similar) detailing the exact methods and signatures required for plugin registration.
- Update `HudPluginContext` and other internal plugins to strictly adhere to the newly introduced strongly-typed registrar constraint.
- Improve type safety and catch registrar-related registration issues early via static analysis tools.

## Capabilities

### New Capabilities

### Modified Capabilities
- `plugin-system`: Introducing strict type checking and formal `Protocol` definitions for plugin `HookRegistrar` parameters, affecting how plugins declare and use their registrars instead of relying on `Any`.

## Impact

- **HUD Plugins**: All internal HUD plugins such as `HudPluginContext` will need to update their type hints to utilize the new protocol instead of `Any`.
- **Type Safety Tools**: Static analysis tools (like mypy, pyright) and IDEs will benefit from improved autocomplete and type checking during plugin development.
- **Hook Registrar**: Better explicit contract definition of what a HookRegistrar is to the plugins.
