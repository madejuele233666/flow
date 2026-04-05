## ADDED Requirements

### Requirement: Workflow SHALL orchestrate artifacts and skills together
The workflow SHALL define both artifact generation requirements and the skill transitions needed to move a change from exploration to archive. It MUST treat schema as the contract for artifacts and phase gates, while skills execute the reasoning, review, implementation, and repair steps inside those gates.

#### Scenario: User starts a new governed change
- **WHEN** a user creates a change under `ai-enforced-workflow`
- **THEN** the workflow SHALL define the expected artifact sequence and the corresponding skill-assisted transitions across explore, artifact creation, artifact review, implementation, implementation verification, repair, sync, and archive

### Requirement: Workflow SHALL support risk-tiered execution
The workflow SHALL classify changes into `LIGHT`, `STANDARD`, or `STRICT` risk levels and MUST adjust required artifacts, required skills, and blocking rules according to that classification.

#### Scenario: Low-risk change is evaluated
- **WHEN** a change affects a narrow scope without architecture, migration, or reference-alignment complexity
- **THEN** the workflow SHALL allow a lighter path with fewer mandatory gates than a `STRICT` change

#### Scenario: High-risk change is evaluated
- **WHEN** a change affects core infrastructure, public interfaces, complex migrations, or explicit reference alignment
- **THEN** the workflow SHALL require stricter design evidence, stronger review gates, and a blocking verification path before implementation and archive

### Requirement: Workflow SHALL define phase gates
The workflow SHALL define explicit gates between artifact creation, implementation, verification, sync, and archive. A failed gate MUST redirect the change to the appropriate correction phase rather than allowing silent progression.

#### Scenario: Artifact review fails before implementation
- **WHEN** artifact verification finds a blocking issue
- **THEN** the workflow SHALL prevent implementation from proceeding until the change artifacts are corrected or the blocking finding is explicitly resolved

#### Scenario: Implementation verification fails before archive
- **WHEN** implementation verification finds a blocking issue
- **THEN** the workflow SHALL prevent sync and archive until the issue is repaired and verification passes again

### Requirement: Workflow SHALL enforce anti-abstraction guardrails
The workflow SHALL require key architectural abstractions to be grounded through low-ambiguity design anchors. At minimum, governed changes MUST define stack-specific equivalents, named deliverables, failure semantics, boundary examples, contrast structures, and verification hooks at the level required by their risk tier.

#### Scenario: Cross-stack architectural concept is introduced
- **WHEN** a design introduces a concept such as a boundary contract, event mechanism, extension system, or state workflow
- **THEN** the workflow SHALL require the design to identify the equivalent construct in the target stack or project context rather than leaving the concept as a generic label

#### Scenario: High-risk design enters review
- **WHEN** a `STRICT` change enters artifact review
- **THEN** the workflow SHALL require the full anti-abstraction guardrail set before the change can proceed to implementation
