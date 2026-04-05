## ADDED Requirements

### Requirement: Repair loop SHALL route issues to the correct layer
The system SHALL classify verification findings by correction target and MUST distinguish between issues in `proposal`, `specs`, `design`, `tasks`, and `implementation`.

#### Scenario: A scope problem is discovered
- **WHEN** verification determines that the intended behavior was incorrectly scoped in the proposal
- **THEN** the repair loop SHALL route the issue back to the `proposal` layer instead of patching implementation directly

#### Scenario: An implementation divergence is discovered
- **WHEN** verification determines that code diverges from valid specs and design
- **THEN** the repair loop SHALL route the issue to the `implementation` layer and keep upstream artifacts unchanged unless new evidence requires broader updates

### Requirement: Repair loop SHALL support iterative verification
After a repair is applied, the system SHALL require the relevant verification step to run again until blocking findings are cleared or the change is intentionally re-scoped.

#### Scenario: Blocking finding is repaired
- **WHEN** a repair step claims to resolve a blocking finding
- **THEN** the workflow SHALL rerun the relevant verification stage before allowing the change to continue

### Requirement: Repair loop SHALL support artifact and implementation findings
The repair process SHALL accept findings produced by artifact verification and implementation verification through a shared, structured issue model.

#### Scenario: Mixed findings are reported
- **WHEN** a verification report contains both design-layer and implementation-layer issues
- **THEN** the repair process SHALL preserve those distinctions and plan corrections in the correct order

### Requirement: Repair loop SHALL restore missing design anchors
When a finding is caused by abstract or under-specified design language, the repair process SHALL restore the missing anchors at the correct artifact layer instead of bypassing the issue with implementation-only edits.

#### Scenario: Missing failure semantics is reported
- **WHEN** verification reports that a design defines a mechanism without failure or recovery behavior
- **THEN** the repair loop SHALL route the issue back to the design or tasks layer and require the missing semantics to be made explicit before closure
