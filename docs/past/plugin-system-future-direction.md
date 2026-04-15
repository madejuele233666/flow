# Plugin System Future Direction

Date: 2026-04-06

## Purpose

This document reassesses the current backend/frontend plugin systems and turns that assessment into a practical direction for the next stage of the project.

The goal is not to ask whether the plugin abstractions look clean in isolation.
The real question is:

- are plugins already attached to the true product control flow?
- can upcoming features be implemented by extending plugin boundaries instead of rewriting core modules?
- which missing pieces are structural blockers rather than optional polish?

## Executive Summary

Short answer:

- Backend plugin foundation is usable.
- Frontend plugin foundation is only partially usable.
- The repository does not yet have one uniformly strong plugin platform across both sides.

More precise judgment:

- `backend/` already has a real plugin integration surface connected to state transitions, hooks, notifications, exporters, templates, and ranking factors.
- `frontend/` has good plugin-shaped abstractions and one strong production-relevant plugin path (`ipc-client`), but the HUD plugin system is not yet fully connected to actual HUD state flow and widget composition flow.

Therefore:

- for backend-driven feature work, the current foundation is strong enough to continue;
- for HUD-heavy feature work, the current foundation is not yet strong enough;
- the next architectural priority should be to finish the frontend plugin runtime path, not to redesign backend plugins or further abstract IPC.

## Current State Map

```text
Backend
  FlowApp
    -> PluginRegistry
    -> PluginContext / AdminContext
    -> HookManager
    -> TransitionEngine
    -> real state transition lifecycle

Frontend
  HudApp
    -> HudPluginRegistry
    -> HudPluginContext / HudAdminContext
    -> HudHookManager
    -> runtime profiles
    -> IPC plugin works
    -> HUD state/widget lifecycle not fully wired
```

## Assessment By Side

### Backend: strong enough as an extension foundation

What is already in place:

- Manifest-based plugin model exists: `FlowPlugin` + `PluginManifest`.
- Discovery model exists: `entry_points` group `flow_engine.plugins`.
- Sandboxed contexts exist: standard `PluginContext` and privileged `AdminContext`.
- Host extension points are meaningful, not decorative:
  - `register_hook(...)`
  - `register_notifier(...)`
  - `register_exporter(...)`
  - `register_factor(...)`
  - `register_template(...)`
- Plugin hooks are attached to real transition flow through `TransitionEngine`.
- Hook execution has real operational protections:
  - timeout
  - per-handler circuit breaker
  - multiple execution strategies
  - safe mode and dev mode

Why this matters:

- a backend plugin can already influence real system behavior without bypassing core boundaries;
- future backend features can be added by extension instead of by invasive modification.

What is still missing:

- there are no real first-party backend plugins in the repository using this system end to end;
- there is almost no backend test coverage focused on the plugin registry/context lifecycle itself;
- plugin dependency semantics in `manifest.requires` exist as metadata but are not actively enforced;
- teardown order is not reverse-ordered, which may matter once plugins depend on each other.

Judgment:

- backend plugin system is a valid foundation;
- it is not yet a battle-tested plugin ecosystem.

### Frontend: promising structure, incomplete runtime reality

What is already good:

- HUD plugin base, manifest, registry, and dual-context model exist.
- The IPC client is a real plugin, not just a conceptual example.
- Runtime-profile-based composition is a strong move:
  - `desktop` profile
  - `windows` profile
- Frontend hooks and payload-integrity rules are more disciplined than the average prototype.
- The frontend plugin surface is already split between:
  - ordinary plugins
  - admin/runtime plugins

Why this is important:

- the project already has one credible frontend plugin path for transport/session concerns;
- runtime profiles are a good foundation for product assembly by environment.

But the key HUD flows are not fully wired:

1. HUD state transitions do not pass through a real plugin-aware orchestrator.

- `HudLocalService.transition_to(...)` directly calls `state_machine.transition(...)`.
- The hook system defines `before_state_transition`.
- `HudApp` expects `STATE_TRANSITIONED` to drive `on_after_state_transition`.
- But the current flow does not establish one canonical transition pipeline that does all of this.

Result:

- frontend plugins cannot reliably participate in the most important HUD lifecycle event: state change.

2. Widget registration is not yet a true composition pipeline.

- `HudPluginContext.register_widget(...)` stores widgets in an internal dictionary.
- `HudCanvas.mount_widget(...)` currently appends to one `QVBoxLayout`.
- `before_widget_register` exists as a hook concept.
- `WidgetRegisteredPayload` exists as an event payload concept.
- But the current runtime does not operate as a hookable slot-aware widget composition pipeline.

Result:

- the current HUD plugin system supports “mount a demo widget”;
- it does not yet support “compose multiple visual plugins with routing, interception, and layout policy”.

3. The service contract is partially representational instead of operational.

- `HudLocalService.register_widget(...)` returns a success-shaped dict.
- It does not actually participate in a real slot reservation or widget composition path.

Result:

- part of the frontend plugin contract is still placeholder-level.

4. Frontend plugin maturity is uneven.

- `ipc-client` is exercised with meaningful tests.
- general HUD plugin lifecycle is not exercised at the same depth.

Judgment:

- frontend plugin system is structurally promising;
- as a full HUD feature foundation, it is not complete.

## What The Current Foundation Can Support

### Safe To Build Now

These are reasonable to continue with current foundations:

- backend task lifecycle extensions
- backend notifier/exporter/template/ranker extensions
- backend rule plugins that veto or redirect transitions
- frontend IPC evolution that stays inside `flow_hud/plugins/ipc/`
- runtime-profile-based startup assembly

### Risky To Build Now

These should not be treated as “just write plugins” yet:

- rich state-driven HUD behavior plugins
- multiple visual HUD widgets with slot/layout composition
- frontend plugins that rely on authoritative before/after state transition hooks
- a broad third-party HUD plugin story

### Not Ready To Claim Yet

These would overstate current reality:

- “frontend and backend plugin systems are both complete”
- “HUD behavior is fully plugin-driven”
- “the project already has a stable plugin platform for arbitrary future UI features”

## Core Direction

The next plugin-system milestone should be:

**finish the HUD plugin runtime so frontend plugins participate in real product flow the way backend plugins already do.**

That means the priority is not:

- more abstract plugin interfaces
- more docs about plugin philosophy
- extracting a separate plugin framework

The priority is:

- connect frontend state transitions to hooks and events;
- connect widget registration to a real slot/layout pipeline;
- prove the model with a few first-party plugins.

## Recommended Work Sequence

### Phase 1: Frontend Flow Closure

Objective:
make HUD plugins first-class participants in state and widget lifecycles.

Required outcomes:

- introduce one canonical HUD transition path;
- run `before_state_transition` before state changes;
- emit `STATE_TRANSITIONED` after successful state changes;
- trigger `on_after_state_transition` from actual emitted events rather than expectation alone;
- route widget registration through a real composition path rather than passive dict storage.

Concrete completion bar:

- a stateful HUD plugin can veto a transition;
- a stateful HUD plugin can react after a transition;
- a visual plugin can register a widget to a named slot;
- the runtime mounts that widget according to slot policy.

### Phase 2: Frontend Composition Contract Hardening

Objective:
turn the current HUD plugin API from “usable by repo insiders” into “stable internal platform”.

Required outcomes:

- define explicit slot/layout contract for HUD widgets;
- decide whether widget registration is event-driven, direct-call-driven, or hybrid;
- remove placeholder behavior from service-layer contracts;
- make runtime profile composition and plugin discovery rules explicit.

Concrete completion bar:

- no fake-success widget registration path remains;
- widget placement semantics are documented and testable;
- runtime profile behavior and admin-plugin rules are deterministic.

### Phase 3: Reference Plugins

Objective:
prove the platform through real first-party plugins instead of framework-only confidence.

Recommended reference set:

- one backend policy plugin
- one backend notifier/exporter/template plugin
- one HUD state-behavior plugin
- one HUD visual widget plugin beyond `debug-text`

Why this phase matters:

- a plugin system with no real plugins is still theoretical;
- reference plugins force missing lifecycle semantics to become explicit.

### Phase 4: Plugin Test Matrix

Objective:
validate the plugin platform as infrastructure, not just through incidental feature tests.

Minimum areas:

- registry duplicate handling
- discovery behavior
- setup/teardown order
- admin-vs-standard context routing
- hook invocation on real lifecycle paths
- widget composition path
- failure isolation and breaker behavior under plugin errors

## Suggested Strategic Position

If the project needs a short statement to guide future decisions, it should be this:

> Backend plugins are ready for real extension work. Frontend plugins are not yet ready to carry the next generation of HUD features until state flow and widget flow are fully wired.

That position is strong enough to guide scope decisions:

- keep building backend features on the plugin foundation;
- do not assume frontend HUD features can be safely “pluginized later” without first closing the runtime path;
- treat frontend plugin closure as enabling infrastructure, not optional cleanup.

## Recommended Next Change

If this assessment is turned into an OpenSpec change, the most natural next change is something like:

- `harden-hud-plugin-runtime`

Scope should include:

- canonical HUD transition orchestration
- hook/event wiring for HUD state changes
- real widget registration pipeline
- slot-aware canvas composition
- tests that prove the lifecycle end to end

A later follow-up change can target:

- `backend-plugin-reference-pack`

That change should add real backend plugins and plugin-platform tests, not redesign the existing backend foundation.

## Final Judgment

The repository does have a meaningful plugin architecture.

But it is asymmetric:

- backend plugin architecture is functionally integrated;
- frontend plugin architecture is only partially integrated.

So the right future direction is not “continue equally on both sides”.

The right future direction is:

1. keep trusting the backend plugin model as a working extension base;
2. finish the frontend plugin runtime path;
3. then use real reference plugins to validate both sides as a coherent long-term platform.
