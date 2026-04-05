## Purpose

Define a general AI-enforced OpenSpec workflow that combines artifact contracts, phase gates, risk tiers, and skill orchestration.

## Requirements

### Requirement: Workflow SHALL orchestrate artifacts and skills together

The workflow SHALL define both artifact generation requirements and the skill transitions needed to move a change from exploration to archive. It MUST treat schema as the contract for artifacts and phase gates, while skills execute the reasoning, review, implementation, and repair steps inside those gates.

#### Scenario: User starts a new governed change
- **WHEN** a user creates a change under `ai-enforced-workflow`
- **THEN** the workflow SHALL define the expected artifact sequence and the corresponding skill-assisted transitions across explore, artifact creation, artifact review, implementation, implementation verification, repair, sync, and archive

### Requirement: Workflow SHALL support risk-tiered execution

The workflow SHALL classify changes into `LIGHT`, `STANDARD`, or `STRICT` risk levels and MUST adjust required artifacts, required skills, blocking rules, and independent verification requirements according to that classification.

#### Scenario: Low-risk change is evaluated
- **WHEN** a change affects a narrow scope without architecture, migration, or reference-alignment complexity
- **THEN** the workflow SHALL allow a lighter path with fewer mandatory gates than a `STRICT` change

#### Scenario: High-risk change is evaluated
- **WHEN** a change affects core infrastructure, public interfaces, complex migrations, or explicit reference alignment
- **THEN** the workflow SHALL require stricter design evidence, stronger review gates, and a blocking verification path before implementation and archive

#### Scenario: Standard-risk change is evaluated
- **WHEN** a change is classified as `STANDARD`
- **THEN** the workflow SHALL require an independent implementation verification gate before sync or archive, and SHALL require planning for that gate in design/tasks artifacts

#### Scenario: Strict-risk change is evaluated
- **WHEN** a change is classified as `STRICT`
- **THEN** the workflow SHALL require both independent artifact verification and independent implementation verification before progression through the corresponding phase gates

### Requirement: Workflow SHALL define phase gates

The workflow SHALL define explicit gates between artifact creation, implementation, verification, sync, and archive. For risk tiers that require independent review, those phase gates SHALL include the corresponding independent verification step. A failed gate MUST redirect the change to the appropriate correction phase rather than allowing silent progression.

#### Scenario: Artifact review fails before implementation
- **WHEN** artifact verification finds a blocking issue
- **THEN** the workflow SHALL prevent implementation from proceeding until the change artifacts are corrected or the blocking finding is explicitly resolved

#### Scenario: Implementation verification fails before archive
- **WHEN** implementation verification finds a blocking issue
- **THEN** the workflow SHALL prevent sync and archive until the issue is repaired and verification passes again

### Requirement: Workflow SHALL require independent verification orchestration for governed gates

For risk tiers that require independent verification, the workflow SHALL treat the related OpenSpec verify and repair skills as the mandatory orchestration path for invoking and consuming independent verifier output. The workflow SHALL define Gemini CLI as the default independent verifier command contract while allowing equivalent future implementations.

#### Scenario: Mandatory independent verifier gate is planned
- **WHEN** a `STANDARD` or `STRICT` change defines a required independent verifier gate
- **THEN** the workflow SHALL require design/tasks to name verifier source, invocation mode, output format, report path, fallback behavior, and the responsible skill entry point

#### Scenario: Independent verification output is generated
- **WHEN** independent verification is executed for a required gate
- **THEN** the workflow SHALL require machine-consumable findings output that can be routed into repair and re-verification instead of ad hoc standalone reviewer notes

### Requirement: Workflow SHALL enforce anti-abstraction guardrails

The workflow SHALL require key architectural abstractions to be grounded through low-ambiguity design anchors. At minimum, governed changes MUST define stack-specific equivalents, named deliverables, failure semantics, boundary examples, contrast structures, and verification hooks at the level required by their risk tier.

#### Scenario: Cross-stack architectural concept is introduced
- **WHEN** a design introduces a concept such as a boundary contract, event mechanism, extension system, or state workflow
- **THEN** the workflow SHALL require the design to identify the equivalent construct in the target stack or project context rather than leaving the concept as a generic label

#### Scenario: High-risk design enters review
- **WHEN** a `STRICT` change enters artifact review
- **THEN** the workflow SHALL require the full anti-abstraction guardrail set before the change can proceed to implementation
