## MODIFIED Requirements

### Requirement: Artifact verification SHALL produce repairable findings

Each finding emitted by artifact verification SHALL include enough evidence and routing information to support downstream repair. Findings MUST identify the affected artifact layer, the recommended correction target, and verifier provenance including the verifier source and execution method when an independent verifier is used.

#### Scenario: Design and specs diverge
- **WHEN** the verifier detects that `design.md` contradicts or omits a requirement defined in specs
- **THEN** the report SHALL identify the relevant files, explain the divergence, record which verifier produced the finding, and route correction to the `design` or `specs` layer

## ADDED Requirements

### Requirement: Artifact verification SHALL support independent verifier execution through related skills

The verification process SHALL support an independent verifier execution path for artifact review and SHALL normalize its output into the shared findings model used by repair. When the workflow requires structured independent review, the default verifier implementation SHALL be Gemini CLI in headless JSON mode invoked or consumed through the related OpenSpec verification skill unless the change design explicitly names an equivalent alternative.

#### Scenario: Strict artifact audit is requested
- **WHEN** a `STRICT` change enters artifact review
- **THEN** the verification process SHALL run or consume the required independent verifier report through the related artifact verification skill and preserve the resulting findings as machine-consumable evidence

#### Scenario: Required independent artifact verifier cannot run
- **WHEN** the workflow requires independent artifact verification and the designated verifier does not produce a usable report
- **THEN** the verification stage SHALL block progression and emit a finding or failure state that routes the issue back to the artifact planning layer
