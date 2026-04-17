# Transition Resolver Design Lessons

This file preserves the useful design lessons from the older
`transition-resolver-execution-plan.md` without keeping its task-plan shape in
the active surface.

Use this file as historical rationale and design guidance.

Do not treat it as a replacement for the current authoritative workflow
contracts, resolver contracts, or closure gate.

## Why The Resolver Was Necessary

The root problem was never the reviewer sub-agent itself.

The root problem was that the main process had too much room to improvise
workflow decisions from prompt prose.

That led to recurring failures such as:

- treating main-process self-judgment as if it were sub-agent pass evidence
- opening a fresh challenger before a recorded working prerequisite existed
- using a fresh working session for ordinary reruns
- stopping after writing `spawn-decision.json`
- substituting shell or `exec` for the built-in reviewer path
- over-modeling workflow state with prose instead of machine-readable state

The durable lesson is:

- semantic review judgment belongs to the reviewer
- orchestration authority must be mechanically constrained

## Stable Invariants

These invariants remain the backbone of the current loop:

1. Ordinary repair reruns stay in the same `working` session.
2. `challenger` is always fresh.
3. Only `challenger` can grant final closure.
4. Challenger entry requires an explicitly recorded prior sub-agent pass and
   its `agent_id`.
5. Main-process inspection is never equivalent to prior sub-agent evidence.
6. Writing `spawn-decision.json` is preparatory only.
7. Reviewer invocation continues in the same turn unless the caller explicitly
   requested `dry-run` or `manual_pause`.
8. Built-in reviewer invocation is the default path when available.
9. Reviewer spawns use `fork_context=false`.
10. Reviewer input stays limited to the minimal verification bundle, optional
    cache context, and output paths.
11. Schema and non-schema callers share the same review-loop semantics.
12. The shared module models one semantic workflow:
    `review_goal=implementation_correctness`.

## Stable Non-Goals

These non-goals remain useful guardrails:

- do not move reviewer semantic judgment into the resolver
- do not let cache or repo-index become closure authority
- do not let the resolver arbitrarily edit unrelated files
- do not preserve redundant contracts only because they already exist

## Baseline Decisions That Still Matter

### No Shared Artifact vs Implementation Split

The shared loop models one workflow: implementation correctness review.

What still varies by caller:

- `review_phase=docs_first`
- `review_phase=source_first`
- phase-specific routing responsibility

What does not vary:

- working/challenger loop semantics

### Docs-First Validation Belongs At Artifact Completion

Docs-first validation should happen at the caller that completes the
artifact-completion boundary.

The important retained lesson is:

- `openspec-propose` or equivalent artifact-completion caller should enter
  docs-first verification automatically
- `openspec-apply-change` must not become the first place where artifact
  quality is repaired

## What The Resolver Must Decide Mechanically

The useful decomposition from the original execution plan is still valid.

### 1. Transition Authority

The resolver must decide:

- start initial working
- rerun same working
- resume same working
- start fresh challenger
- record challenger reopen
- allow close
- deny close

The key lesson:

- closure, rerun, reopen, and challenger entry are explicit machine outcomes,
  not prompt interpretations

### 2. Session Reuse And Freshness

The resolver must distinguish:

- active working baseline
- open vs resumable session state
- ordinary rerun vs exception path
- fresh challenger requirement

The key lesson:

- fresh working is exception-only
- ordinary rerun must not silently drift into a new session

### 3. Authorization

The resolver or caller-normalization layer must distinguish:

- authorized and should run now
- authorized but pause requested
- not authorized

Useful retained rule:

- standalone module-root review must not be forced through a schema wrapper in
  order to become authorized

### 4. Invocation Discipline

The resolver must constrain:

- built-in subagent requirement
- shell fallback policy
- `fork_context=false`
- minimal bundle only

The key lesson:

- invocation policy must be explicit machine output, not a vague suggestion

### 5. Continuation Policy

The resolver must not stop at preparatory artifacts.

It must explicitly decide whether to:

- continue caller flow
- enter repair
- rerun same working
- enter challenger
- wait for user

The key lesson:

- caller continuation must come from normalized review results, not from
  main-process hesitation

### 6. Phase Routing

Useful retained rule set:

- `docs_first` and `source_first` share the same loop semantics
- routing may differ by phase
- docs-first findings must not be reinterpreted into source auto-fix by
  main-process intuition
- routing should be driven by normalized reviewer result, not by rereading raw
  findings prose

### 7. Cache Sidecar Limits

The durable lesson is narrow:

- cache may affect review orientation
- cache must not affect closure authority
- cache problems should degrade to bypass/continue-without-cache rather than
  inventing fake review certainty

### 8. Exception Routing

Useful retained exception concepts:

- `agent_not_found`
- `session_completed_unresumable`
- `tooling_recovery`
- `challenger_found_new_findings`
- `policy_requires_challenger`

The key lessons:

- ordinary rerun must not escalate to fresh working for trivial reasons
- challenger findings must produce `challenger_reopen`
- reopen must bind the failed challenger refs and promoted `agent_id`

### 9. Closure Gate

Close must remain an explicit machine outcome.

The original closure lesson still holds:

- deny close unless final pass is challenger
- deny close unless `final_assessment=pass`
- deny close unless findings are empty
- deny close unless `closure_authority=challenger_confirmed`
- deny close unless coverage is complete and saturation exhaustive
- deny close unless the run-dir mechanical gate passed

If challenger finds issues:

- this is not merely `deny close and stop`
- it must route into recorded challenger reopen and the failed challenger must
  become the next working baseline

### 10. Run Layout And Path Coherence

Useful retained rule set:

- path coherence failures are orchestration failures, not reviewer findings
- subject mismatch or unresolved predecessor paths must block challenger entry
  and closure
- unresolved run-dir or missing gate result must block closure

## Resolver State Model Lessons

The old execution plan was right to separate normalized orchestration state
from reviewer prose.

The still-useful state buckets are:

- `subject`
- `session`
- `review_result`
- `predecessor`
- `reopen`
- `caller`
- `authorization`
- `invocation`
- `paths`
- `mechanical_gate`
- optional `cache`

The important lesson is not the exact field list.

The important lesson is:

- orchestration state should be normalized and machine-readable
- reviewer judgment should be reduced only to the minimal normalized result
  needed for transitions

## Decision Surface Lessons

The older plan correctly insisted that resolver outputs must be explicit.

Still-useful output concepts are:

- `decision`
- `reason_code`
- `required_session_mode`
- `required_invocation_mode`
- `reroute_destination`
- `reroute_class`
- `required_evidence_checks`
- `required_path_checks`
- `required_output_artifacts`
- `authorized`
- `blocking`
- `required_mechanical_gate`
- `mechanical_gate_status`
- `denial_reason` when blocked

The key lesson:

- a machine decision surface should say what must happen next, not merely
  “continue review”

## Fail-Closed Lessons

The original execution plan identified the right class of denial cases.

The enduring ones are:

- missing or invalid predecessor `source_review`
- predecessor findings not converged
- predecessor evidence not a valid working pass
- incomplete coverage or saturation before challenger
- failed challenger reopen metadata missing or inconsistent
- ordinary rerun requested without a reusable working session and without an
  explicit exception reason
- caller tries to substitute shell or `exec` for required built-in reviewer
  invocation
- verifier paths are missing or subject-incoherent
- workflow tries to stop after preparatory artifacts only
- docs-first review tries to route directly into implementation auto-fix
- closure is requested before the mechanical gate succeeds

The key lesson:

- orchestration should fail closed before close, challenger entry, or rerun are
  honored

## Module-Shape Lessons

The implementation details can change, but these boundaries remain useful:

- the resolver is orchestration-only
- it may be implemented as a local deterministic module
- it may call a guard or validator
- it must not replace reviewer judgment
- it must not silently replace the mechanical closure gate with in-memory
  intuition

## Minimal-Input Lesson

The old execution plan had a long candidate input model.

The durable lesson is not to preserve every old field.

The durable lesson is:

- include only the minimum normalized state required to decide the next
  orchestration step
- avoid pushing raw findings prose or reviewer reasoning into the resolver
- version any new machine outputs before callers rely on them

## How To Use This File Now

Use this file when:

- extending the resolver
- auditing whether a new workflow feature expands main-process discretion
- checking whether a proposed contract field belongs to orchestration or to
  reviewer judgment
- deciding whether a new routing or denial case should become machine-readable

Do not use this file as:

- the operational entrypoint
- the current authoritative contract surface
- closure evidence

Use these files for current operation instead:

- `docs/review-flow/current-authoritative-verification-flow.md`
- `openspec/schemas/modules/review-loop/REFERENCE-INDEX.md`
- `openspec/schemas/modules/review-loop/transition-resolver/CALLER-INTEGRATION.md`
