## 1. Documentation Setup

- [x] 1.1 Create `docs` directory if it doesn't exist
- [x] 1.2 Initialize `docs/architecture.md` with the main header and table of contents

## 2. Document the Core Layers

- [x] 2.1 Write the "Interface & Port Layer" section describing `FlowClient` Protocol and its Local/Remote implementations
- [x] 2.2 Write the "State Machine & Mutex" section detailing the `TaskState` strict enum and `can_transition` logic
- [x] 2.3 Write the "Event Bus & Hook System" section explaining decoupled communications (`pluggy` style hooks, `BackgroundEventWorker`)
- [x] 2.4 Write the "Storage & Ledger Layer" section highlighting the Markdown parsing and Git backend for version control
- [x] 2.5 Write the "Scheduler & AI Integration" section about Gravity Ranker and stub implementations
- [x] 2.6 Write the "IPC Protocol" section illustrating the custom JSON-RPC implementation

## 3. Formatting and Review

- [x] 3.1 Verify that code snippets (e.g. interfaces, abstracts) are properly formatted
- [x] 3.2 Add a top-level architectural diagram (ASCII) as an overview
- [x] 3.3 Proofread and fix spelling/consistency before completion
