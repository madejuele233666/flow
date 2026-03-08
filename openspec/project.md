# Flow Engine — Project AI Collaboration Principles

This project enforces strict architectural precision in all AI-assisted design work.
When AI produces any `design.md` or `tasks.md`, the following principles are mandatory.
For detailed examples, checklists, and SOPs, see `docs/ai_architecture_guidelines.md`.

## Core Principles

1. **Architecture-First: Code-Level Contracts, Not Concepts**
   Any architectural claim (EventBus, Plugin System, State Machine, etc.) MUST be paired with concrete evidence: `Protocol` class definitions, `@dataclass` type signatures, and explicit boundary constraints. A design that names concepts without defining typed interfaces is invalid.

2. **Port Contract Anti-Leakage**
   All module boundaries exposed to external consumers MUST define a `Protocol` class:
   - Input parameters: only primitive types (`str`, `int`, `dict`, `list`)
   - Return values: only `dict` or `list[dict]`
   - Domain objects (`Enum`, `QWidget`, internal models) MUST NOT cross boundaries

3. **Tiered Plugin Sandboxing**
   Any plugin/extension architecture MUST implement at least two permission tiers:
   - **Standard Context**: registration-only APIs
   - **Admin Context**: read-only `@property` access to internals, whitelist-granted only

4. **Typed Payloads Mandatory**
   All event and hook communications MUST use `@dataclass(frozen=True)` payloads.
   Raw `dict` passing for events is prohibited. Every new event type requires a payload dataclass.

5. **Defense Mechanisms for Core Infrastructure**
   - EventBus MUST have both synchronous `emit()` and asynchronous `emit_background()` paths
   - Hook systems MUST support at minimum: `PARALLEL`, `WATERFALL`, `BAIL_VETO` strategies
   - Hook handlers MUST each have an independent circuit breaker (threshold + timeout + recovery)

6. **Alignment Protocol (When Referencing Existing Systems)**
   When instructed to "reference", "align with", or "replicate" an existing system:
   1. List every source file to align against (not concept docs)
   2. Extract core classes and signatures from each file
   3. Build a module mapping table (reference → new), marking "replicate" vs "adapt"
   4. Append a coverage report (✅/❌/⚠️) to the design before finalizing

7. **AI Self-Verification (Mandatory Before Finalizing Artifacts)**
   After producing `design.md`: run the Architecture Audit Checklist (see `docs/ai_architecture_guidelines.md` Chapter 5) and append the result.
   After producing `tasks.md`: confirm every core-infrastructure task group has a `【检查点】` block, and every pure-logic file task has a `【防腐规定】` rule.
