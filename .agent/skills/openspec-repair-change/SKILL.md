---
name: openspec-repair-change
description: Repair a change after artifact verification or implementation verification finds issues. Use when findings need to be routed back to proposal, specs, design, tasks, or implementation.
license: MIT
compatibility: Works with OpenSpec changes; `ai-enforced-workflow` uses `verify-sequence/default`.
metadata:
  author: project
  version: "1.2"
---

# OpenSpec Repair Change

Use this skill to turn verification findings into a repair plan and route them to the correct layer.

## Input

Provide:
- the change name
- authoritative verifier-subagent findings JSON from any `verify-sequence/default` invocation, including `openspec-artifact-verify`, apply-phase checkpoint runs inside `openspec-apply-change`, or `openspec-verify-change`
- matching verifier execution evidence JSON for the same authoritative verifier-subagent finding set
- optional Gemini second-opinion outputs as supplemental evidence only
- optional originating phase: `artifact_gate`, `apply`, or `implementation_verify`
- optional continuation override: `verify-only`, `dry-run`, or `manual_pause`
- optional repair mode: `artifact_only`, `implementation_only`, or `mixed`
- optional verifier-subagent summary markdown as derivative context only
- optional raw report path(s) from the Gemini verification step (evidence only; not a substitute for normalized report output)
- optional retry-state snapshot with separate counters:
  - `artifact_rerun_budget`
  - `implementation_auto_fix_budget`

## Steps

### 1. Normalize findings

For each finding, confirm the following fields exist:
- `id`
- `severity`
- `dimension`
- `artifact`
- `problem`
- `evidence`
- `recommendation`
- `redirect_layer`
- `blocking`
- `auto_fixable`

Validate allowed values before routing:
- `severity`: `CRITICAL|WARNING|SUGGESTION`
- `dimension`: `Completeness|Correctness|Coherence`
- `artifact` and `redirect_layer`: `proposal|specs|design|tasks|implementation`

Use authoritative verifier-subagent findings JSON and normalized Gemini reports as the repair input source.
If verifier execution evidence JSON is missing, treat the verification result as non-authoritative and block repair routing until provenance is restored.
If only raw Gemini output is available, require runner recovery (`input_raw_path -> report_path`) before repair planning.
If a normalized verifier or Gemini report is missing required fields, treat it as a contract failure and block the step instead of inferring missing values.

### 1.1 Merge Verifier-Subagent And Gemini Findings

When both authoritative verifier-subagent findings and a Gemini report exist:
- treat the verifier-subagent findings as the primary authoritative verifier review
- treat Gemini as an independent second opinion
- preserve disagreements explicitly instead of collapsing them silently
- prefer upstream routing when either reviewer identifies a missing artifact-level contract

### 2. Route by correction layer

Map each finding to one of:
- `proposal`
- `specs`
- `design`
- `tasks`
- `implementation`

Do not default to implementation if the real issue is upstream.

Auto-fix eligibility rule:
- allow automatic implementation repair only when `mode=implementation && blocking=true && redirect_layer=implementation && auto_fixable=true`
- route all other findings to explicit repair actions via `openspec-repair-change`

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
- which findings are eligible for automatic implementation repair under the conjunctive gate
- which findings must remain manual and routed upstream
- what verifier-subagent review must be rerun after repair
- what Gemini second-opinion verification must be rerun after repair
- which Gemini report path(s) should be replaced or superseded
- what automatic continuation target should run next when no continuation override is set
- retry-budget impact:
  - artifact reruns consume `artifact_rerun_budget`
  - implementation auto-fix loops consume `implementation_auto_fix_budget`

### 6. Close the loop

After repair:
- if the active schema is `ai-enforced-workflow`: if repair touched upstream artifacts (`proposal/specs/design/tasks`), rerun verifier-subagent artifact review first using shared sequence `verify-sequence/default`; run Gemini second opinion when policy requires it (`STRICT` or explicit dual gate)
- if the active schema is `ai-enforced-workflow` and the originating phase was `artifact_gate`: a passing artifact rerun resumes `openspec-apply-change`; do not invoke implementation verification before apply starts
- if the active schema is `ai-enforced-workflow` and the originating phase was `apply` or `implementation_verify`: rerun verifier-subagent implementation review when implementation was edited, or when an upstream artifact rerun changed assumptions after implementation work already exists; run Gemini second opinion when policy requires it (`STRICT` or explicit dual gate)
- for `ai-enforced-workflow`, verifier reruns MUST use built-in subagent API invocation using template `verify-reviewer-inline-v1`, and invocation metadata (`agent_id/start_at/end_at/final_state`) must be retained in logs/evidence
- if the active schema is not `ai-enforced-workflow`: rerun verification using that schema's own verify sequence or skill contract instead of forcing `verify-sequence/default`
- each rerun MUST spawn a fresh verifier instance (no inherited verifier memory)
- use `artifact_rerun_budget` only for artifact reruns and `implementation_auto_fix_budget` only for implementation auto-fix loops
- if the same blocking finding repeats after an implementation auto-fix attempt (`id` + `redirect_layer`), stop auto-fix loop and route to explicit repair actions
- do not replace rerun verification with manual review or user confirmation
- if no continuation override is set and an artifact rerun passes, automatically hand off to `openspec-apply-change` when the originating phase was `artifact_gate`
- if no continuation override is set and an implementation rerun passes, automatically return to the active apply/verify chain without waiting for a manual rerun command

## Guardrails

- NEVER bypass an upstream artifact problem by patching code only
- NEVER collapse artifact issues and implementation issues into one undifferentiated list
- ALWAYS preserve disagreements between verifier-subagent findings and Gemini when they matter to routing
- ALWAYS state which verification step must run next
- NEVER mark a finding auto-fixable when `redirect_layer` is not `implementation`
- Do not hand control back for a manual rerun when no continuation override is set and the next verification/apply step is already known
- NEVER accept a hand-written markdown summary as a substitute for authoritative verifier-subagent findings JSON plus execution evidence JSON
