# Current Authoritative Verification Flow

This file records the current authoritative verification flow that has already
been manually checked and accepted.

Use this file as the reference when verifying the current execution and any
follow-up work that claims to implement the same review-loop behavior.

## Scope

This flow governs:

- schema-driven OpenSpec verification
- standalone module-root verification
- working / challenger session orchestration
- challenger reopen handling
- closure gating

It does not turn old historical review-runs into authority.

Historical runs may remain on disk, but they are not the source of truth unless
they satisfy the current shared contracts and the current guard.

## Authoritative Sources

Primary authority:

- `openspec/schemas/modules/review-loop/README.md`
- `openspec/schemas/modules/review-loop/VERIFY-IMPLEMENTATION.md`
- `openspec/schemas/modules/review-loop/contracts/review-loop-core-v1.json`
- `openspec/schemas/modules/review-loop/contracts/review-loop-reopen-record-v1.json`
- `openspec/schemas/ai-enforced-workflow/verification-sequence.md`

Supporting standalone / operator docs:

- `docs/review-flow/README.md`
- `docs/reusable-review-flow.md`

Resolver-layer authority:

- `openspec/schemas/modules/review-loop/transition-resolver/README.md`
- `openspec/schemas/modules/review-loop/transition-resolver/contracts/transition-resolver-input-v1.json`
- `openspec/schemas/modules/review-loop/transition-resolver/contracts/transition-resolver-routing-v1.json`
- `openspec/schemas/modules/review-loop/transition-resolver/contracts/transition-resolver-decision-v1.json`
- `openspec/schemas/modules/review-loop/transition-resolver/bin/transition_resolver_validate.py`
- `openspec/schemas/modules/review-loop/transition-resolver/bin/transition_resolver_resolve.py`

Mechanical closure gate:

- `openspec/schemas/modules/review-loop/bin/review_loop_guard.py`

## Core Model

The shared module models one thing only:

- `review_goal=implementation_correctness`

There is no shared semantic split between `artifact` and `implementation`.

Different callers may still use:

- `review_phase=docs_first`
- `review_phase=source_first`

That phase changes routing and review surface, not the review-loop semantics.

## Required Review Loop

The required loop is:

```text
working
  -> write findings + verifier evidence
  -> repair and rerun in same working session
  -> converge on pass + zero findings + complete + exhaustive
  -> validate previous working recorded outputs
  -> challenger in fresh session
  -> close
  -> or challenger_reopen and promote failed challenger into next working baseline
```

## Execution Rules

1. Start with `review_pass_type=working`.
2. Write machine-readable:
   - `findings.json`
   - `verifier-evidence.json`
3. Ordinary reruns stay in the same working session.
4. Ordinary reruns within the same working baseline must keep the same
   `agent_id`.
5. A fresh working session is exception-only.
6. Challenger must always be a fresh session.
7. Challenger entry requires validation of the previous working sub-agent's
   recorded outputs:
   - `agent_id`
   - `findings_path`
   - `verifier_evidence_path`
8. The main process must not treat its own inspection as equivalent to prior
   sub-agent evidence.
9. Writing `spawn-decision.json` is preparatory only.
10. If review is required, the workflow must continue into actual reviewer
    invocation in the same turn unless the caller explicitly requested
    `dry-run` or `manual_pause`.
11. When reviewer sub-agents are required, built-in subagent invocation is the
    default path.
12. Reviewer spawns must use `fork_context=false` and pass only the minimal
    verification bundle, optional `index_context`, and `output_paths`.

## Working Convergence Conditions

Working may advance toward challenger only when the latest working pass
records all of the following:

- `final_assessment=pass`
- zero findings
- `coverage_status=complete`
- `saturation_status=exhaustive`

A working zero-findings result is convergence only.

It is not closure.

## Challenger Rules

Challenger rules are strict:

- challenger must be fresh
- only challenger may grant final closure
- challenger entry must be authorized from recorded working outputs, not from
  main-process intuition

If challenger returns zero findings and agrees with the converged working
result, closure may proceed only when:

- final pass is `challenger`
- `final_assessment=pass`
- zero findings
- `closure_authority=challenger_confirmed`
- `coverage_status=complete`
- `saturation_status=exhaustive`

## Challenger Reopen Rules

If challenger finds new issues:

- do not resume the old working session as the active baseline
- write machine-readable `reopen-record.json`
- use `review-loop-reopen-record-v1.json`
- bind the failed challenger findings and verifier evidence
- set `promoted_working_agent_id` to the failed challenger `agent_id`
- treat that failed challenger session as the next working baseline

This is the current authoritative reopen semantic.

The failed challenger becomes the next working baseline.

## Closure Gate

Final closure still requires the mechanical run-dir gate:

```bash
python3 openspec/schemas/modules/review-loop/bin/review_loop_guard.py --run-dir <review-run-dir>
```

A claimed closure is not authoritative if this gate fails.

At minimum, a valid final run must:

- include at least one challenger attempt
- end on a challenger attempt
- record `closure_authority=challenger_confirmed`

## Resolver Status

The transition resolver now exists as a real shared module rather than only as
planning prose.

Current authoritative resolver outputs are:

- `spawn_initial_working`
- `send_input_same_working`
- `resume_same_working`
- `spawn_fresh_challenger`
- `record_challenger_reopen`
- `spawn_exception_working`
- `enter_repair`
- `return_caller_flow`
- `wait_for_user`
- `allow_close`
- `deny_close`
- `blocked`

The resolver is orchestration-only.

It must not replace reviewer semantic judgment.

It should be implemented as a deterministic local module by default rather than
as a no-context subagent.

If AI is used around the resolver, its role should be limited to producing
normalized input state or reviewer outputs, not final transition authority.

## Non-Authoritative Historical Runs

The following historical transition-resolver runs are not authoritative under
the current contracts and guard behavior:

- `docs/review-flow/archive/transition-resolver-hardening-2026-04-17/review-runs/transition-resolver-execution-plan-2026-04-17`
- `docs/review-flow/archive/transition-resolver-hardening-2026-04-17/review-runs/transition-resolver-execution-plan-rerun-2026-04-17`

Use their `RUN-STATUS.md` files as status markers only.

Do not use them as closure evidence for the current workflow semantics.

## Verification Checklist

When verifying the current execution, check at least these points:

1. Ordinary reruns stay in the same working session and same working baseline.
2. Challenger starts only after recorded working outputs are validated.
3. Challenger is always fresh.
4. Challenger findings produce `challenger_reopen` plus a promoted challenger
   working baseline.
5. Closure comes only from a final challenger pass.
6. Closure also passes the mechanical run-dir guard.
