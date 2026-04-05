---
name: openspec-repair-change
description: Repair a change after artifact verification or implementation verification finds issues. Use when findings need to be routed back to proposal, specs, design, tasks, or implementation.
license: MIT
compatibility: Works with any OpenSpec change.
metadata:
  author: project
  version: "1.0"
---

# OpenSpec Repair Change

Use this skill to turn findings into a repair plan and route them to the correct layer.

## Input

Provide:
- the change name
- findings from `openspec-artifact-verify` or `openspec-verify-change`
- optional repair mode: `artifact_only`, `implementation_only`, or `mixed`

## Steps

### 1. Normalize findings

For each finding, confirm the following fields exist:
- `severity`
- `dimension`
- `artifact`
- `problem`
- `evidence`
- `recommendation`
- `redirect_layer`
- `blocking`
- `verifier_provenance`:
  - `source`
  - `execution_method`
  - `invocation_mode`
  - `output_format`
  - `report_path`

If a field is missing, infer carefully and state the inference.

### 2. Route by correction layer

Map each finding to one of:
- `proposal`
- `specs`
- `design`
- `tasks`
- `implementation`

Do not default to implementation if the real issue is upstream.

### 3. Build the repair order

Repair in dependency order:
- proposal
- specs
- design
- tasks
- implementation

This prevents downstream fixes from being applied against invalid upstream assumptions.

### 4. Restore missing anchors when needed

If a finding is caused by abstract or under-specified language, repair the missing anchor explicitly:
- add stack equivalent
- add named deliverable
- add failure semantics
- add boundary example
- add contrast structure
- add verification hook

### 5. Produce a repair plan

Return:
- grouped findings by redirect layer
- the recommended repair order
- what should be edited
- what verification must be rerun after repair
- which independent verifier gates are required to rerun by risk tier
- preserved verifier provenance for each rerun target

### 6. Close the loop

After repair:
- rerun `openspec-artifact-verify` if artifact layers changed
- rerun `openspec-verify-change` if implementation changed
- rerun both if upstream artifacts changed and code may now be misaligned

If risk tier requires independent verification:
- rerun the same independent verifier gate that originally produced blocking findings
- preserve original and rerun report paths for traceability
- do not accept standalone Gemini output outside `openspec-artifact-verify` or `openspec-verify-change`

### 7. Independent verifier rerun contract

When constructing rerun tasks, use path-based prompts and structured output:

```bash
gemini -y --output-format json -p "Re-verify repaired findings for <change-name>. Compare prior report <old-report-path> against updated artifacts/code paths <paths>. Emit JSON findings with blocking flags."
```

Optional approval-mode variant:

```bash
gemini --approval-mode yolo --output-format json -p "Re-verify repaired change <change-name> using report <old-report-path> and current files <paths>."
```

Repair planning should record a verifier rerun matrix, for example:

```json
{
  "rerun_plan": [
    {
      "gate": "artifact-independent-verify",
      "skill": "openspec-artifact-verify",
      "required": true,
      "source_report": "reports/gemini/artifact-verify.json",
      "rerun_report": "reports/gemini/artifact-verify-rerun.json"
    }
  ]
}
```

## Guardrails

- NEVER bypass an upstream artifact problem by patching code only
- NEVER collapse artifact issues and implementation issues into one undifferentiated list
- ALWAYS state which verification step must run next
- NEVER drop verifier provenance during routing, planning, or rerun
- NEVER treat standalone Gemini reports as sufficient when skill-mediated rerun is required
