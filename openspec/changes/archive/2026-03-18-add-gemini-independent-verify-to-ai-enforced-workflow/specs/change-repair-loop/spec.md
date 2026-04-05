## MODIFIED Requirements

### Requirement: Repair loop SHALL support iterative verification

After a repair is applied, the system SHALL require the relevant verification step to run again until blocking findings are cleared or the change is intentionally re-scoped. If the change risk tier requires independent verification, the repair loop SHALL rerun the same independent verifier gate before allowing the workflow to continue.

#### Scenario: Blocking finding is repaired
- **WHEN** a repair step claims to resolve a blocking finding
- **THEN** the workflow SHALL rerun the relevant verification stage and any required independent verifier pass before allowing the change to continue

### Requirement: Repair loop SHALL support artifact and implementation findings

The repair process SHALL accept findings produced by artifact verification and implementation verification through a shared, structured issue model. That model SHALL preserve verifier provenance, including the verifier source and execution method, so repair and re-verification can distinguish self-review output from independent-review output. Independent Gemini verification findings MUST enter the loop through the related OpenSpec verify skills and be rerouted through the repair skill rather than bypassing those skills with standalone reports.

#### Scenario: Mixed findings are reported
- **WHEN** a verification report contains both design-layer and implementation-layer issues
- **THEN** the repair process SHALL preserve those distinctions, retain verifier provenance for each finding, and plan corrections in the correct order

#### Scenario: Gemini independent verify reports blocking issues
- **WHEN** Gemini-based independent verification reports blocking issues for artifacts or implementation
- **THEN** the repair loop SHALL consume those findings through the related verify skill output and route them through the repair skill before any re-verification occurs
