## Purpose

Define how verification findings are routed, repaired, and re-verified across artifact and implementation layers.

## Requirements

### Requirement: Repair loop SHALL route issues to the correct layer

The system SHALL classify verification findings by correction target and MUST distinguish between issues in `proposal`, `specs`, `design`, `tasks`, and `implementation`.

#### Scenario: A scope problem is discovered
- **WHEN** verification determines that the intended behavior was incorrectly scoped in the proposal
- **THEN** the repair loop SHALL route the issue back to the `proposal` layer instead of patching implementation directly

#### Scenario: An implementation divergence is discovered
- **WHEN** verification determines that code diverges from valid specs and design
- **THEN** the repair loop SHALL route the issue to the `implementation` layer and keep upstream artifacts unchanged unless new evidence requires broader updates

### Requirement: Repair loop SHALL support iterative verification

After a repair is applied, the system SHALL require the relevant verification step to run again until blocking findings are cleared or the change is intentionally re-scoped. If the change risk tier requires independent verification, the repair loop SHALL rerun the same independent verifier gate before allowing the workflow to continue.

#### Scenario: Blocking finding is repaired
- **WHEN** a repair step claims to resolve a blocking finding
- **THEN** the workflow SHALL rerun the relevant verification stage before allowing the change to continue

### Requirement: Repair loop SHALL preserve verifier provenance across repair cycles

The shared findings model SHALL preserve verifier provenance across repair cycles, including verifier source, execution method, and source report identity/path, so independently produced findings remain attributable through remediation and re-verification.

#### Scenario: Findings from multiple verifiers are repaired
- **WHEN** a repair plan includes both author-side and independent-verifier findings
- **THEN** the repair loop SHALL preserve verifier attribution per finding and SHALL avoid collapsing findings into an un-attributed combined list

### Requirement: Repair loop SHALL support artifact and implementation findings

The repair process SHALL accept findings produced by artifact verification and implementation verification through a shared, structured issue model. That model SHALL preserve verifier provenance, including verifier source and execution method, so repair and re-verification can distinguish self-review output from independent-review output. Independent Gemini verification findings MUST enter the loop through the related OpenSpec verify skills and be rerouted through the repair skill rather than bypassing those skills with standalone reports.

#### Scenario: Mixed findings are reported
- **WHEN** a verification report contains both design-layer and implementation-layer issues
- **THEN** the repair process SHALL preserve those distinctions and plan corrections in the correct order

### Requirement: Repair loop SHALL rerun required independent verifier gates through skill orchestration

When workflow risk tier requires independent verification, post-repair verification SHALL rerun the applicable independent gate through `openspec-repair-change` coordination with the related verify skills. Standalone independent reports outside the skill loop SHALL NOT satisfy required re-verification gates.

#### Scenario: Strict change is repaired after artifact verification failure
- **WHEN** a `STRICT` change repairs a blocking artifact finding that required independent review
- **THEN** the repair loop SHALL require rerunning the independent artifact verifier gate through the skill-mediated path before implementation can proceed

### Requirement: Repair loop SHALL restore missing design anchors

When a finding is caused by abstract or under-specified design language, the repair process SHALL restore the missing anchors at the correct artifact layer instead of bypassing the issue with implementation-only edits.

#### Scenario: Missing failure semantics is reported
- **WHEN** verification reports that a design defines a mechanism without failure or recovery behavior
- **THEN** the repair loop SHALL route the issue back to the design or tasks layer and require the missing semantics to be made explicit before closure
