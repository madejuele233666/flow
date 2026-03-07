## Context

The Flow Engine currently lacks a single, definitive architectural documentation file that explains its internal 8-layer design, single-task constraints, event/hook coupling, and purely localized Git-based text storage mechanism. Providing this document makes the codebase accessible to new contributors or AI systems.

## Goals / Non-Goals

**Goals:**
- Provide a detailed map of `flow_engine/` and all its subdirectories.
- Clarify the design principles, such as Hexagonal Architecture, IPC ghost daemon, pluggable hooks, and single-tasking constraints.
- Produce a `docs/architecture.md` file that catalogs every protocol and interface.

**Non-Goals:**
- Does not change any runtime code.
- Does not modify any user-facing CLI behavior.

## Decisions

- **Placement**: We will place the documentation in `docs/architecture.md` at the project root to ensure high visibility.
- **Format**: We will use Markdown for the documentation. It will be structured top-down, starting from the CLI interface all the way down to the persistent Git text ledger.

## Risks / Trade-offs

- **Risk**: Documentation may drift as the codebase evolves.
  - **Mitigation**: Future architectural changes should be submitted with updates to `docs/architecture.md` via the OpenSpec process.
