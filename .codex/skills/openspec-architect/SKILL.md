---
name: openspec-architect
description: |
  Architecture design assistant with built-in anti-pattern guardrails.
  Use when designing new modules, refactoring core systems, or when the user
  asks to "reference", "align with", or "replicate" an existing system's
  architecture. Automatically enforces the Alignment Protocol and Architecture
  Audit Checklist from docs/ai_architecture_guidelines.md.
license: MIT
compatibility: Works with any openspec change. Most effective on [CORE] infrastructure changes.
metadata:
  author: project
  version: "1.0"
---

# OpenSpec Architect — Architecture Design Assistant

Produce engineering-grade architecture documents with automatic self-verification.

**When to use this skill:**
- User wants to design a new core module or system
- User says "reference", "align with", "replicate", or "based on" an existing codebase
- The change involves plugin systems, event buses, state machines, or cross-module communication
- The change is labelled `[CORE]` (system-critical infrastructure)

**Input**: A description of what needs to be designed (new module, refactor goal, system reference).

---

## Steps

### 1. Load Project Context

Read `openspec/project.md` to load the project's AI collaboration principles.
Read `docs/ai_architecture_guidelines.md` for the full Architecture Audit Checklist
and Alignment Protocol SOP.

If either file is missing, note it and proceed using the embedded rules below.

### 2. Detect Design Mode

**Mode A — Reference Alignment** (triggered when user says "reference X", "align with Y", "replicate Z"):
- Go to Step 3 (Alignment Protocol)

**Mode B — Fresh Architecture Design** (no explicit reference system):
- Skip to Step 4 (Architecture Audit)

### 3. Execute Alignment Protocol (Mode A only)

Follow these 5 steps exactly. Do NOT proceed to design until step 3c produces a mapping table.

**Step 3a: Lock Reference Files**
List every source file in the reference system that contains relevant contracts.
Do NOT use concept docs (e.g., architecture.md) as primary references.
Example: `events.py`, `hooks.py`, `client.py`, `plugins/context.py`, `plugins/registry.py`, `app.py`

**Step 3b: Extract Contracts**
For each file, extract and document:
- Core class names
- Key method signatures (name, parameter types, return type)
- Data structure definitions (dataclasses, TypedDicts, Protocols)
- Key design decisions (e.g., "frozen=True because payload must be immutable")

**Step 3c: Build Mapping Table**
Produce a table before writing any design:

| Reference Module | New Module | Action | Notes |
|---|---|---|---|
| `EventBus.emit()` | `HudEventBus.emit()` | Replicate | Same synchronous contract |
| `EventBus (asyncio)` | `HudEventBus (Qt Signal)` | Adapt | Different threading model |

Mark each row as **Replicate** (exact copy of contract) or **Adapt** (contract preserved, implementation changed).

**Step 3d: Design with Attribution**
Every Decision in design.md MUST include:
- The reference file it maps from
- The specific class/method being aligned

**Step 3e: Append Coverage Report**
At the end of design.md, add a `## Coverage Report` section:

| Reference Contract | New Contract | Status |
|---|---|---|
| `FlowClient Protocol` | `HudServiceProtocol` | ✅ |
| `BackgroundEventWorker` | `HudBackgroundEventWorker` | ✅ |
| `PluginManifest` | `HudPluginManifest` | ❌ Missing |

Any ❌ MUST be addressed before the artifact is finalized.

### 4. Architecture Audit (ALL modes)

Before finalizing any design.md, run through this checklist.
For `[CORE]` components, every failing item MUST be fixed before proceeding.

**A. Data Contract Checks**
- [ ] Every event type has a `@dataclass(frozen=True)` payload defined?
- [ ] Every hook has a typed payload (frozen for read-only, mutable for waterfall)?
- [ ] Port layer methods accept only primitive types (`str`, `int`, `dict`, `list`)?
- [ ] Port layer methods return only `dict` or `list[dict]`?

**B. Boundary Isolation Checks**
- [ ] A `Protocol` class exists to isolate internals from external consumers?
- [ ] Plugin Context is tiered (standard registration-only + admin with whitelist)?
- [ ] Internal references exposed only via read-only `@property` typed as `Any`?
- [ ] No cross-layer imports (e.g., pure logic layer importing UI framework)?

**C. Defense Mechanism Checks**
- [ ] EventBus has both synchronous `emit()` and asynchronous `emit_background()` paths?
- [ ] Background path has retry mechanism and dead-letter recording?
- [ ] Hook system supports PARALLEL, WATERFALL, BAIL_VETO strategies?
- [ ] Each hook handler has an independent circuit breaker (threshold + timeout + recovery)?

**D. Plugin Ecosystem Checks**
- [ ] `[CORE]` Plugins carry declarative Manifest (name, version, requires, config_schema)?
- [ ] `[EDGE]` `entry_points` auto-discovery supported?
- [ ] `[CORE]` Orchestrator is config-driven for plugin loading and permission assignment?
- [ ] `[CORE]` Full lifecycle management (setup / teardown / graceful shutdown)?

**E. Task List Checks** (when also producing tasks.md)
- [ ] Every `[CORE]` task group ends with a `【检查点】` checkpoint task?
- [ ] Every pure-logic file task includes a `【防腐规定】` anti-corruption rule?
- [ ] Every task is anchored to a named deliverable (class/method/file), not an abstract process?

### 5. Generate Design Artifact

Produce design.md following the standard spec-driven schema format:
- Context, Goals/Non-Goals, Decisions, Risks/Trade-offs

Each Decision MUST:
- State the reference source (if Mode A)
- Include a concrete code example (class definition or method signature)
- Explain WHY this design was chosen over alternatives

After writing, re-run the audit checklist mentally and append:
```
## AI Self-Verification Summary
- Alignment Protocol: [Executed / Not applicable]
- Coverage Report: [Appended / N/A]
- Audit Checklist: [X/16 items passed]
- Uncovered items: [List or "None"]
```

### 6. Generate Tasks Artifact

When producing tasks.md, apply the following mandatory rules:

**Checkpoint Blocks**: End every `[CORE]` task group with:
```
- [ ] X.Y 【检查点】 Present [test log / run output / coverage] to user.
  MUST obtain explicit user confirmation before proceeding to next phase.
```

**Anti-Corruption Rules**: For each pure-logic file task, add inline:
```
【防腐规定】This file MUST NOT import [specific forbidden dependency].
```

**Output Anchoring**: Every task must name a specific deliverable:
```
✅ "Implement MouseMovePayload @dataclass(frozen=True)"
❌ "Set up the event mechanism"
```

### 7. Stop and Present

After generating artifacts:
- Present the Coverage Report (if Mode A)
- Present the Audit Checklist summary
- Highlight any ❌ items that require user decision
- DO NOT proceed to implementation without user confirmation

---

## Guardrails

- **NEVER** produce a design that only names concepts without typed interfaces
- **NEVER** flatten multi-tier structures (PluginContext + AdminContext → single Context)
- **NEVER** reference a system without reading its actual source files first
- **NEVER** write tasks anchored to abstract processes instead of concrete deliverables
- **ALWAYS** distinguish between `[CORE]` (strict rules) and `[EDGE]` (relaxed rules)
- **ALWAYS** append the Coverage Report and Audit Summary before finalizing
