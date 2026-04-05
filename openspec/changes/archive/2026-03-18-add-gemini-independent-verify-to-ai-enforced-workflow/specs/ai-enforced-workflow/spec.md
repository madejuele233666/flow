## MODIFIED Requirements

### Requirement: Workflow SHALL support risk-tiered execution

The workflow SHALL classify changes into `LIGHT`, `STANDARD`, or `STRICT` risk levels and MUST adjust required artifacts, required skills, blocking rules, and independent verification requirements according to that classification.

#### Scenario: Low-risk change is evaluated
- **WHEN** a change affects a narrow scope without architecture, migration, or reference-alignment complexity
- **THEN** the workflow SHALL allow a lighter path with fewer mandatory gates than a `STRICT` change and MAY treat independent verification as optional

#### Scenario: Medium-risk change is evaluated
- **WHEN** a change affects multiple modules, modifies workflow behavior, or changes verification rules without introducing core infrastructure or migration risk
- **THEN** the workflow SHALL require an independent implementation verification gate before sync or archive and SHALL require the change artifacts to name the verifier plan

#### Scenario: High-risk change is evaluated
- **WHEN** a change affects core infrastructure, public interfaces, complex migrations, or explicit reference alignment
- **THEN** the workflow SHALL require independent artifact review and independent implementation verification, plus a blocking re-verification path before implementation and archive

### Requirement: Workflow SHALL define phase gates

The workflow SHALL define explicit gates between artifact creation, implementation, independent verification, sync, and archive. A failed gate MUST redirect the change to the appropriate correction phase rather than allowing silent progression.

#### Scenario: Artifact review fails before implementation
- **WHEN** artifact verification or a required independent artifact verification gate finds a blocking issue
- **THEN** the workflow SHALL prevent implementation from proceeding until the change artifacts are corrected or the blocking finding is explicitly resolved

#### Scenario: Implementation verification fails before archive
- **WHEN** implementation verification or a required independent implementation verification gate finds a blocking issue
- **THEN** the workflow SHALL prevent sync and archive until the issue is repaired and the required verification passes again

## ADDED Requirements

### Requirement: Workflow SHALL define independent verification execution details

For any gate that requires independent verification, the workflow SHALL require design and task artifacts to name the verifier source, invocation mode, output format, report location, fallback behavior, and the related OpenSpec skills that orchestrate the review. The default independent verifier implementation SHALL be Gemini CLI running in headless mode with structured output through the relevant verify and repair skills unless an equivalent alternative is explicitly approved by the change design.

#### Scenario: Standard change prepares implementation verify
- **WHEN** a `STANDARD` change defines its verification plan
- **THEN** the workflow SHALL require the artifacts to name the Gemini CLI-based implementation verify step, the related verification skill that invokes or consumes it, its report output, and the conditions that require rerunning it after repair

#### Scenario: Strict change prepares artifact and implementation verify
- **WHEN** a `STRICT` change defines its verification plan
- **THEN** the workflow SHALL require the artifacts to define independent verifier steps for both artifact review and implementation verification, bind those steps to the related verify and repair skills, and define fallback behavior if the verifier cannot run
