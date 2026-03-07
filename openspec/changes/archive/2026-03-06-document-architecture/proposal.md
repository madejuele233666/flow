## Why

The Flow Engine project has grown into a highly decoupled, hex-architectural, asynchronous system with distinct patterns (Event Bus, Hook System, Ghost Daemon, Git Ledger, etc). However, there is no single, comprehensive, deep-dive architecture document that outlines every layer and interface. We need to document the architecture in detail so that future development, open-source contributors, or AI agents have a clear, precise map of all sub-systems, APIs, and the contracts (protocols) between them.

## What Changes

- Create a brand new architecture documentation file, detailing the 8 logic layers of the Flow Engine.
- Break down each module (Client Protocol, State Machine, Event Bus, Hooks, Storage, Scheduler, IPC).
- Expose the core `Protocol`s, `Interface`s, and fundamental methodologies that drive the single-tasking constraint and zero-dependency philosophy.
- The new document will be stored in the root or `docs/` folder as a definitive guide.

## Capabilities

### New Capabilities
- `architecture-documentation`: Provide a detailed, deep-dive architectural map of the Flow Engine, describing the hex-architecture, plugin system, state machine, decoupled events/hooks, pure text storage with Git Ledger, scheduler mechanics, and IPC C/S protocol. 

### Modified Capabilities

## Impact

- No codebase runtime logic will be affected.
- Helps onboard new developers and guides future architectural evolutions.
- Serves as the ultimate AI/MCP system context map for semantic understanding of the engine.
