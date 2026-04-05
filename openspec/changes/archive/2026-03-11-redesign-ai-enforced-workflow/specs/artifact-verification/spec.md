## ADDED Requirements

### Requirement: Artifact verification SHALL review proposal, specs, design, and tasks
The system SHALL provide a verification stage that can review `proposal.md`, `specs/**/*.md`, `design.md`, `tasks.md`, or all of them together before implementation begins.

#### Scenario: Full artifact audit is requested
- **WHEN** a user asks to verify a change plan before implementation
- **THEN** the verification process SHALL inspect all available change artifacts and produce a structured report

### Requirement: Artifact verification SHALL score findings by dimension and severity
Artifact verification SHALL report findings using the dimensions `Completeness`, `Correctness`, and `Coherence`, and SHALL classify each finding as `CRITICAL`, `WARNING`, or `SUGGESTION`.

#### Scenario: Missing task coverage is detected
- **WHEN** the verifier detects that required implementation work is not represented in tasks or a critical artifact is absent
- **THEN** it SHALL emit a `CRITICAL` finding with a concrete recommendation and a clear target layer for correction

### Requirement: Artifact verification SHALL produce repairable findings
Each finding emitted by artifact verification SHALL include enough evidence and routing information to support downstream repair. Findings MUST identify the affected artifact layer and the recommended correction target.

#### Scenario: Design and specs diverge
- **WHEN** the verifier detects that `design.md` contradicts or omits a requirement defined in specs
- **THEN** the report SHALL identify the relevant files, explain the divergence, and route correction to the `design` or `specs` layer

### Requirement: Artifact verification SHALL audit anti-abstraction guardrails
Artifact verification SHALL check whether key architectural claims are grounded by concrete anchors rather than abstract terminology alone. The verifier MUST inspect the presence and adequacy of stack equivalents, named deliverables, failure semantics, boundary examples, contrast structures, and verification hooks where required by change risk.

#### Scenario: Abstract concept lacks a concrete anchor
- **WHEN** the verifier finds that a design claims a mechanism or boundary without naming concrete constructs, deliverables, examples, or validation paths
- **THEN** it SHALL emit at least a `WARNING`, and SHALL emit a `CRITICAL` finding when the missing anchor affects a blocking `STRICT` change

### Requirement: Blocking findings SHALL gate implementation
If artifact verification reports one or more `CRITICAL` findings, the workflow SHALL block entry into implementation until those findings are repaired or explicitly resolved.

#### Scenario: Artifact verify returns critical issues
- **WHEN** the artifact verification summary contains blocking findings
- **THEN** the change SHALL remain outside the apply phase and SHALL re-enter artifact correction instead
