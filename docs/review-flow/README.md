# Standalone Review Flow

## Purpose

This directory defines a schema-independent way to validate whether a broad
implementation target is correct.

Use it for:

- direct file-path validation
- diff review
- release-readiness checks
- non-change rollout audits
- one-off repository repairs
- subsystem correctness checks

This is an implementation-validation workflow.

Planning artifacts may be used as optional reference material, but they are not
the defining structure of the standalone flow.

For the current distilled principles that apply across both schema and
non-schema flows, read:

- [review-loop principles](/home/madejuele/projects/2K0300/docs/review-flow/review-loop-principles.md)

## Core Rule

The reviewer emits findings and execution evidence.

The main process decides rerun, challenger entry, or closure, and it must not
substitute its own judgment for the prior working sub-agent output.

## Contracts

Shared standalone contracts live here:

- [review-loop-core-v1.json](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/contracts/review-loop-core-v1.json)
- [review-loop-reopen-record-v1.json](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/contracts/review-loop-reopen-record-v1.json)
- [review-loop-standalone-adapter-v1.json](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/contracts/review-loop-standalone-adapter-v1.json)
- [review-loop-standalone-spawn-decision-v1.json](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/contracts/review-loop-standalone-spawn-decision-v1.json)
- [VERIFY-IMPLEMENTATION.md](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/VERIFY-IMPLEMENTATION.md)

## Minimal Inputs

Every standalone review run must define:

- `target_ref`
- `review_goal=implementation_correctness`
- `review_phase=docs_first|source_first`
- `review_pass_type`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract`

When the caller provides only the module root and a broad implementation
request, bootstrap defaults and scope inference come from:

- `review-loop-core-v1.json -> bootstrap_defaults`
- `review-loop-core-v1.json -> bootstrap_rules`
- `review-loop-standalone-adapter-v1.json -> bootstrap_target_ref_templates`

Recommended optional inputs:

- `target_description`
- `acceptance_reference_paths`
- `constraints_or_invariants`

Examples:

- `target_ref=repo:2K0300-release-audit-2026-04-15`
- `target_ref=diff:new/user`
- `target_ref=paths:new/code/platform,new/code/runtime`
- `target_ref=workflow:direct-stagea-rollout`

## Recommended Run Layout

Use a stable run directory such as:

```text
review-runs/<run-name>/
  working/
    attempt-1/
      findings.json
      verifier-evidence.json
      spawn-decision.json
    attempt-2/
      findings.json
      verifier-evidence.json
      reopen-record.json   # when challenger findings promote into next working
      spawn-decision.json  # only for an explicit recovery exception
  challenger/
    attempt-1/
      findings.json
      verifier-evidence.json
      spawn-decision.json
```

The exact path is flexible. The important part is keeping findings, evidence,
and challenger handoff paths stable and machine-readable.

Required per-run payload details:
- `findings.json` carries the active adapter subject key (`target_ref` for
  standalone runs)
- `verifier-evidence.json` carries the same subject key plus inline
  `review_scope` and `review_coverage`

## Sequence

1. Pick a `target_ref`.
2. Declare the explicit scope through `evidence_paths_or_diff_scope`.
3. Start a `working` review pass.
4. Write `findings.json` and `verifier-evidence.json`, including
   `review_phase=docs_first|source_first`.
5. Record the active subject key in both findings and verifier evidence:
   - standalone: `target_ref`
   - OpenSpec-wrapped usage: `change`
6. Include inline `review_scope` and `review_coverage` in
   `verifier-evidence.json`.
7. If the implementation changes, rerun in the same working session.
8. Keep the same working `agent_id` across ordinary reruns within the same
   working baseline.
9. If the working `agent_id` changes without a challenger-driven promotion,
   treat it as an exception-only recovery path and require an explicit
   machine-readable `spawn-decision.json`.
10. Continue until the latest working pass records:
   - `final_assessment=pass`
   - empty findings
   - `coverage_status=complete`
   - `saturation_status=exhaustive`
11. Validate the prior working outputs.
12. Start a fresh `challenger` session only after that validation succeeds.
13. Close only if the challenger returns zero findings and
    `closure_authority=challenger_confirmed`.
14. If challenger finds new issues, treat that result as the new active
    baseline and promote the challenger session into working review.
15. Record that reopen transition machine-readably:
    - use [review-loop-reopen-record-v1.json](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/contracts/review-loop-reopen-record-v1.json)
    - the reopen record must reference the failed challenger findings/evidence
    - then promote the challenger session into the next working baseline
      using the challenger `agent_id`
    - do not spawn a fresh working reviewer unless an explicit recovery
      exception separately applies

Automatic execution rule:

- if review is required, do not stop after deciding to review
- invoking the workflow entrypoint that uses this review flow is explicit authorization for the main process to create the reviewer sub-agents required by that flow, limited to the reviewer sessions required by the workflow
- verifier reviewer spawns MUST use `fork_context=false` and pass only the
  minimal verification bundle, optional `index_context`, and `output_paths`
- writing `spawn-decision.json` is preparatory only
- continue in the same turn into the actual reviewer sub-agent invocation
  unless the caller explicitly requested `dry-run` or `manual_pause`
- do not replace reviewer sub-agent invocation with shell/exec when the
  built-in subagent API is available

## Challenger Entry Rule

A challenger pass may start only after the main process validates the previous
working sub-agent outputs referenced by:

- `agent_id`
- `findings_path`
- `verifier_evidence_path`

The main process must verify:

- the findings JSON belongs to the recorded `agent_id`
- `final_assessment=pass`
- findings are empty
- the evidence belongs to a `working` pass for
  `review_goal=implementation_correctness`
- `coverage_status=complete`
- `saturation_status=exhaustive`

Without that record, challenger must not start.

The challenger spawn record itself must use the machine-readable standalone
contract:

- [review-loop-standalone-spawn-decision-v1.json](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/contracts/review-loop-standalone-spawn-decision-v1.json)

## Direct AI Invocation

If the caller says "reference this module root and verify whether the
implementation is correct", the intended entrypoint is:

- [README.md](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/README.md)
- [VERIFY-IMPLEMENTATION.md](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/VERIFY-IMPLEMENTATION.md)

The AI should interpret that as a strict working/challenger implementation
review loop, not as a request to invent an artifact phase.

Active implementation surface:

- [current-authoritative-verification-flow.md](/home/madejuele/projects/2K0300/docs/review-flow/current-authoritative-verification-flow.md)
- [review-loop reference index](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/REFERENCE-INDEX.md)
- [transition-resolver module](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/transition-resolver/README.md)
- [transition resolver caller integration](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/transition-resolver/CALLER-INTEGRATION.md)

Archived construction-period scaffolding:

- [review-flow archive index](/home/madejuele/projects/2K0300/docs/review-flow/archive/README.md)
- [transition-resolver hardening archive](/home/madejuele/projects/2K0300/docs/review-flow/archive/transition-resolver-hardening-2026-04-17/README.md)
- [code-review-first archive](/home/madejuele/projects/2K0300/docs/review-flow/archive/code-review-first-2026-04-17/README.md)
- [transition-resolver design lessons archive](/home/madejuele/projects/2K0300/docs/review-flow/archive/transition-resolver-design-lessons-2026-04-17/README.md)

## Mechanical Validation

After writing run artifacts, validate the run directory with:

```bash
python3 /home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/bin/review_loop_guard.py --run-dir review-runs/<run-name>
```

This is the final closure gate, not a mid-loop lint:

- a working-only run must fail
- a final passing run must end on challenger with
  `closure_authority=challenger_confirmed`

Reference fixture runs:

- [standalone-context-free-bootstrap-close](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/fixtures/review-runs/standalone-context-free-bootstrap-close)
- [standalone-challenger-reopen-close](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/fixtures/review-runs/standalone-challenger-reopen-close)

Archived transition-resolver test harness:

- [transition-resolver test-harness archive](/home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/transition-resolver/archive/test-harness-2026-04-17/README.md)
