---
name: openspec-artifact-verify
description: Verify proposal, specs, design, and tasks before implementation. Use when the user wants to check whether a change plan is complete, correct, coherent, and ready for apply.
license: MIT
compatibility: Works with any OpenSpec change.
metadata:
  author: project
  version: "1.0"
---

# OpenSpec Artifact Verify

Verify change artifacts before implementation begins.

## Input

Optionally specify:
- a change name
- an artifact scope: `proposal`, `specs`, `design`, `tasks`, or `all`

If omitted, use the active change from context when it is unambiguous.

## Steps

### 1. Load the change

Run:
- `openspec status --change "<name>" --json`
- `openspec instructions apply --change "<name>" --json`

Read the available artifact files from the change.

### 2. Determine verification strictness

Use the proposal risk tier if available:
- `LIGHT`
- `STANDARD`
- `STRICT`

If no tier exists, infer conservatively from the change scope and note the inference.

Independent artifact verification rule:
- `LIGHT`: optional
- `STANDARD`: optional unless explicitly required by change artifacts
- `STRICT`: mandatory independent artifact verification through this skill before implementation

### 3. Verify three dimensions

For the selected artifact scope, evaluate:

- **Completeness**
  Are required sections, capabilities, requirements, decisions, tasks, and review hooks present?

- **Correctness**
  Do artifacts match the user intent, declared capabilities, and explicit design or workflow rules?

- **Coherence**
  Do proposal, specs, design, and tasks agree with each other, or do they drift?

### 4. Audit anti-abstraction guardrails

Check whether important architectural claims are grounded by:
- stack equivalents
- named deliverables
- failure semantics
- boundary examples
- contrast structures
- verification hooks

For `STRICT` changes, missing critical guardrails are blocking.

### 5. Emit structured findings

Each finding MUST include:
- `id`
- `severity`: `CRITICAL`, `WARNING`, or `SUGGESTION`
- `dimension`: `Completeness`, `Correctness`, or `Coherence`
- `artifact`: `proposal`, `specs`, `design`, or `tasks`
- `problem`
- `evidence`
- `recommendation`
- `redirect_layer`
- `blocking`
- `verifier_provenance`:
  - `source` (for example `gemini-cli`)
  - `execution_method` (for example `skill-mediated-cli`)
  - `invocation_mode` (for example `headless-prompt`)
  - `output_format` (for example `json`)
  - `report_path`

Use `redirect_layer` from:
- `proposal`
- `specs`
- `design`
- `tasks`

### 6. Produce final assessment

Return:
- a scorecard by dimension
- grouped findings by severity
- a final assessment:
  - `pass`
  - `pass_with_warnings`
  - `blocked`

Guidance:
- any `CRITICAL` finding blocks apply
- `WARNING` findings do not block unless they are declared blocking for a `STRICT` change
- `SUGGESTION` findings never block

### 7. Hand off to repair

If blocked or materially degraded, recommend `openspec-repair-change` and preserve findings in a format that repair can consume directly.

### 8. Independent verifier execution contract (Gemini default)

When independent artifact verification is required, this skill is the mandatory entry point for invoking or consuming the independent verifier output. Do not accept standalone Gemini reports that bypass this skill's normalization and routing.

Default command contract (path-based inputs, no stdin-heavy prompts):

```bash
gemini -y --output-format json -p "Review STRICT change artifacts for <change-name>. Use files: proposal=<path>, specs=<glob>, design=<path>, tasks=<path>. Return structured findings with severity, dimension, evidence, and recommendations."
```

Optional approval-mode variant:

```bash
gemini --approval-mode yolo --output-format json -p "Review artifacts listed under <change-dir> and emit blocking findings only."
```

Example normalized report fragment:

```json
{
  "assessment": "blocked",
  "findings": [
    {
      "id": "AV-001",
      "severity": "CRITICAL",
      "dimension": "Correctness",
      "artifact": "design",
      "problem": "Design omits fallback path required by STRICT verifier gate.",
      "evidence": "design.md lacks fallback behavior in Independent Verification Plan.",
      "recommendation": "Add fallback behavior and responsible skill handoff.",
      "redirect_layer": "design",
      "blocking": true,
      "verifier_provenance": {
        "source": "gemini-cli",
        "execution_method": "skill-mediated-cli",
        "invocation_mode": "headless-prompt",
        "output_format": "json",
        "report_path": "reports/gemini/artifact-verify.json"
      }
    }
  ]
}
```

## Guardrails

- NEVER treat presence of sections as proof of quality
- NEVER emit a blocking finding without concrete evidence
- ALWAYS name the artifact layer that must be corrected
- NEVER treat ad hoc Gemini output as valid independent verification unless produced or consumed through this skill
