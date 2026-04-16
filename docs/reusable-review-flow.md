# Reusable Review Flow

## Purpose

This document extracts the review loop into a standalone process that can be
reused outside `openspec/schemas/ai-enforced-workflow/schema.yaml`.

Use this file when you want the same review behavior without requiring an
OpenSpec schema-driven entrypoint.

For schema-independent usage, prefer the standalone method and contracts in:

- `docs/review-flow/README.md`
- `openspec/schemas/modules/review-loop/contracts/review-loop-core-v1.json`
- `openspec/schemas/modules/review-loop/contracts/review-loop-standalone-adapter-v1.json`
- `openspec/schemas/modules/review-loop/contracts/review-loop-standalone-spawn-decision-v1.json`
- `openspec/schemas/modules/review-loop/VERIFY-IMPLEMENTATION.md`

If you do use the OpenSpec Stage A contracts, the shared JSON source of truth
for field groups is:

- `openspec/schemas/modules/review-loop/contracts/review-loop-core-v1.json`
- `openspec/schemas/modules/review-loop/contracts/review-loop-openspec-adapter-v1.json`

## Core Model

The shared module models one thing: strict implementation validation.

That loop has two pass types:

1. `working`
2. `challenger`

The intent is:

```text
working review
  -> fix and rerun in same session
  -> zero findings with complete coverage
  -> validate previous working outputs
  -> challenger review in fresh session
  -> close or reopen
```

## Review Roles

`working` pass:
- used for convergence
- may be rerun in the same reviewer session
- may consume implementation-layer auto-fix findings
- does not have closure authority

`challenger` pass:
- must run in a fresh reviewer session
- acts as an independent re-check after the latest working pass converges
- is the only pass allowed to grant final implementation closure

Transition ownership:
- the reviewer pass emits findings and execution evidence
- the orchestrator decides rerun, challenger entry, or closure
- the orchestrator must not substitute its own judgment for the prior working
  sub-agent output

## Required Inputs

Every review run must declare:

- `review_goal=implementation_correctness`
- `review_phase`: `docs_first|source_first`
- `review_pass_type`: `working|challenger`
- `risk_tier`: `LIGHT|STANDARD|STRICT`
- `evidence_paths_or_diff_scope`
- `findings_contract`

The outer wrapper supplies the subject key:

- OpenSpec: `change`
- standalone: `target_ref`

When a context-free AI receives only the module root plus a broad implementation
review request, it must bootstrap from:

- `review-loop-core-v1.json -> bootstrap_defaults`
- `review-loop-core-v1.json -> bootstrap_rules`
- `review-loop-standalone-adapter-v1.json -> bootstrap_target_ref_templates`

## Required Outputs

Every review iteration must produce:

- machine-readable findings JSON
- machine-readable reviewer execution evidence JSON
- findings JSON and execution evidence JSON both carry the active adapter
  subject key (`change` or `target_ref`)

Every review pass's `verifier-evidence.json` must additionally include:

- `review_scope`
- `review_coverage`

Recommended minimum execution evidence fields:

- subject key from the active adapter
- `review_goal`
- `review_phase`
- `review_pass_type`
- `findings_contract`
- `agent_id`
- `start_at`
- `end_at`
- `final_state`
- `cache_mode`
- `closure_authority`
- `verifier_output_path`
- `reviewed_paths`
- `skipped_paths`

Routing rule:
- `shared-findings-v1` stays minimal; routing does not come from per-finding
  artifact-layer fields
- `review_phase=docs_first` routes findings back to artifact repair and keeps
  `auto_fixable=false`
- `review_phase=source_first` may allow automatic repair only when the active
  caller policy also permits it
- `reviewed_axes`
- `unreviewed_axes`
- `coverage_status`
- `saturation_status`

## Review Flow

Primary review surface:

- changed code
- changed tests
- directly impacted code

Reference review surface:

- optional planning artifacts
- optional repository index or other cache hints

Steps:

1. Start a new `working` reviewer session.
2. Run the working pass against the declared implementation target.
3. Write findings JSON and execution evidence JSON.
4. If findings are implementation-layer, blocking, and auto-fixable, repair the
   code and rerun in the same working session.
5. Continue working reruns until the latest working pass has:
   - zero findings
   - `coverage_status=complete`
   - `saturation_status=exhaustive`
6. Validate the previous working agent's recorded outputs:
   - `agent_id`
   - findings JSON path
   - verifier-evidence JSON path
7. Start a fresh `challenger` reviewer session only after that validation
   succeeds.
8. Run the challenger pass against the converged result.
9. If the challenger pass returns new findings, treat that result as the new
   active baseline and continue with working review again.
10. Only close the review when the challenger pass returns zero findings and
    records `closure_authority=challenger_confirmed`.

Automatic execution rule:

- if the workflow uses sub-agents, do not stop after deciding that review must
  run
- invoking the workflow entrypoint that uses this review flow is explicit authorization for the main process to create the reviewer sub-agents required by that flow, limited to the reviewer sessions required by the workflow
- writing `spawn-decision.json` is preparatory only, not a completed review
  step
- continue in the same turn into the actual reviewer sub-agent invocation
  unless the caller explicitly requested `dry-run` or `manual_pause`
- Do not replace reviewer sub-agent invocation with shell/exec when the
  built-in subagent API is available

Rules:

- working reruns are convergence-only
- working zero findings are not closure
- challenger must be a fresh session
- only challenger can grant final implementation closure
- challenger findings reopen the loop through a machine-readable
  `challenger_reopen` transition back to working

## Coverage Rules

Implementation review is not converged unless both are true:

- `coverage_status=complete`
- `saturation_status=exhaustive`

If either is false:

- the pass is non-authoritative
- challenger review must not start

`review_scope` is support evidence, not a separate gate.

`review_coverage` records what was actually reviewed, what was skipped, and
whether the declared review surface was covered.

## Cache Rules

Optional cache or repository-index support may help with review orientation,
but it must not become a gate.

Allowed behavior:

- use cache hints to discover impacted areas faster
- ignore stale cache and continue source-first review
- continue review when cache is missing

Forbidden behavior:

- block review because cache is missing
- treat cache output as the authority for closure
- freeze the review surface purely from cache-generated required paths

## Spawn And Session Rules

If the workflow uses sub-agents, write a spawn-decision record before any new
reviewer session is created.

That record is preparatory only:

- the orchestrator must continue in the same turn into the corresponding
  reviewer session creation when review is still required
- it must not stop at "spawn-decision written"
- it must not treat shell/exec review as equivalent when sub-agent invocation
  is available

Normal spawn reasons:

- initial working session
- challenger pass

Exception spawn reasons:

- active session unavailable
- session unresumable
- tooling recovery

Cache or repository-index helpers may still be used locally for orientation, but
they are not standalone spawn-contract branches and must not be emitted as
`next_session_role` / `reason_code` values.

Standalone machine-readable spawn values are limited to the standalone
contract:

- `requested_agent_type=verify-reviewer`
- `next_session_role=working|challenger`
- `reason_code=initial_working_session|challenger_pass|challenger_reopen|active_session_unavailable|session_unresumable|tooling_recovery`

OpenSpec-only index/cache-maintenance spawn values must not appear in
standalone spawn records or standalone workflow instructions.

Session policy:

- review reruns should reuse the active working session
- ordinary working reruns must keep the same `agent_id`
- a changed working `agent_id` requires an explicit recovery spawn-decision
  record
- challenger must always use a fresh session

## Auto-Fix Routing

Automatic repair is allowed only when all of the following are true:

- `review_goal=implementation_correctness`
- `blocking=true`
- `auto_fixable=true`

All other blocking findings must route to manual repair or caller-local
repair.

## Minimal Adoption Checklist

If you reuse this flow without OpenSpec schema support, keep at least these
constraints:

1. Treat the target as an implementation-validation subject, not as an artifact
   workflow.
2. Reuse the same working reviewer session for convergence.
3. Require a fresh challenger session before implementation closure.
4. Always write findings and execution evidence for each pass.
5. Require `review_scope` and `review_coverage` for every review pass.
6. Treat cache as optional support, never as closure authority.
7. Do not let zero-findings working review close the review.

## Suggested File Mapping

If you want a lightweight local convention without OpenSpec:

- `review/findings.json`
- `review/verifier-evidence.json`
- `review/spawn-decision.json`
- `review/cache-preflight.json`

The exact paths can change. The important part is keeping the contracts and
phase semantics stable.
