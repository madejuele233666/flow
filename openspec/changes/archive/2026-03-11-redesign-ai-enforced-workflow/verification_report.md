## Verification Report: redesign-ai-enforced-workflow

### Summary

This report validates that the redesigned workflow artifacts, schema, and skills were implemented coherently enough to support the intended collaboration model.

### What Was Exercised

Test changes were created with the `ai-enforced-workflow` schema:

- `test-ai-enforced-light`
- `test-ai-enforced-standard`
- `test-ai-enforced-strict`

The following CLI checks were exercised:

- `openspec schemas --json`
- `openspec instructions proposal --change test-ai-enforced-light --json`
- `openspec instructions design --change test-ai-enforced-standard --json`
- `openspec instructions design --change test-ai-enforced-strict --json`
- `openspec instructions tasks --change test-ai-enforced-strict --json`

### Validation Results

#### 1. Schema recognition

Result: PASS

- `openspec schemas --json` recognizes `ai-enforced-workflow`
- Description and artifact list match the redesigned schema intent

#### 2. Risk tier surface area

Result: PASS

- Proposal instructions now require explicit `LIGHT / STANDARD / STRICT`
  classification and justification
- Design instructions explicitly reference `STANDARD` and `STRICT`
- Task instructions explicitly describe different verification expectations for
  `LIGHT`, `STANDARD`, and `STRICT`

#### 3. Anti-abstraction guardrails

Result: PASS

Design instructions now require:
- stack equivalents
- named deliverables
- failure semantics
- boundary examples
- contrast structures
- verification hooks

Task instructions now require:
- concrete outputs
- verification work
- named deliverables instead of abstract actions

#### 4. Skill split and findings contract

Result: PASS

The skill set now separates responsibilities:

- `openspec-align`: reference extraction and coverage mapping
- `openspec-architect`: design reasoning and stack-equivalent framing
- `openspec-artifact-verify`: artifact review
- `openspec-repair-change`: repair routing

The verify/repair loop now shares a structured findings contract with the
following required fields:

- `severity`
- `dimension`
- `evidence`
- `recommendation`
- `redirect_layer`
- `blocking`

#### 5. Repair routing model

Result: PASS (design-level validation)

`openspec-repair-change` explicitly routes findings to:

- `proposal`
- `specs`
- `design`
- `tasks`
- `implementation`

and requires re-running the correct verification stage after repair.

### Residual Gaps

#### Gap 1: Risk-tier gates are policy-driven, not CLI-enforced

The current OpenSpec CLI does not dynamically change artifact availability or
apply blocking rules based on the proposal's selected risk tier. The redesigned
workflow expresses this behavior through schema instructions and skills, not
through engine-level hard gates.

Impact:
- The workflow is usable now
- Enforcement depends on skill compliance and review discipline
- Future CLI integration could make these gates machine-enforced

#### Gap 2: Skill orchestration is declarative, not automatic

The schema now states when `openspec-align`, `openspec-architect`,
`openspec-artifact-verify`, and `openspec-repair-change` should be used, but
OpenSpec does not automatically dispatch those skills.

Impact:
- The collaboration model is defined
- Human or agent behavior must still choose the right skill at the right time

### Final Assessment

The redesign is coherent and implementable as a project-level workflow today.

The main remaining limitation is not in the schema or skill design, but in the
current OpenSpec runtime model: risk-tier gates and skill invocation are
expressed as strong protocol rules rather than hard CLI enforcement.
