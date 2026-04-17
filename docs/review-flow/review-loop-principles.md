# Review Loop Principles

This file distills the useful parts of the old `code-review-first` rollout
docs and the transition-resolver design notes into the current loop guidance.

It is the short, human-facing summary for the latest implementation-validating
review loop.

Authoritative runtime sources remain:

- `openspec/schemas/modules/review-loop/REFERENCE-INDEX.md`
- `docs/review-flow/current-authoritative-verification-flow.md`
- `openspec/schemas/modules/review-loop/README.md`
- `openspec/schemas/modules/review-loop/VERIFY-IMPLEMENTATION.md`

## The Core Idea

The review system has one semantic job:

`review_goal=implementation_correctness`

Caller-specific phases only change routing:

- `review_phase=docs_first`
- `review_phase=source_first`

Do not split the loop into separate artifact and implementation semantics.
Do not invent extra review goals just to name a phase.

## Non-Negotiable Invariants

1. Working reruns stay in the same working session.
2. Ordinary reruns must preserve the same working baseline.
3. Challenger must always be fresh.
4. Challenger is the only closure authority.
5. Challenger entry requires recorded working outputs from the prior working pass.
6. The main process must not treat its own inspection as sub-agent evidence.
7. Writing `spawn-decision.json` is preparatory only.
8. If review is required, the loop continues in the same turn unless the caller explicitly requested `dry-run` or `manual_pause`.
9. Built-in reviewer subagent invocation is the default path when available.
10. Reviewer spawns use `fork_context=false` and the minimal verification bundle.

## What The Main Process May Not Do

- It may not substitute shell or `exec` for the built-in reviewer path.
- It may not open a fresh working session for an ordinary rerun.
- It may not promote a challenger result into closure authority by intuition.
- It may not use cache or repo-index as closure authority.
- It may not let a docs-first artifact gate become a hidden implementation gate.

## What Stays Mechanical

The current loop depends on machine-readable state, not prose interpretation.

Mechanical inputs:

- `findings.json`
- `verifier-evidence.json`
- `reopen-record.json`
- `spawn-decision.json`
- resolver input and decision contracts
- final run-dir closure gate

Mechanical decisions:

- same-session rerun or exception-only recovery
- fresh challenger entry
- challenger reopen promotion
- allow close / deny close / blocked

## Sidecars Are Helpers

The useful lesson from the old layered plan is simple:

- sidecars may improve review quality
- sidecars may not become authority
- sidecars may not block the main loop unless they are proven stable enough to be promoted

That includes:

- repo-index or cache helpers
- scope summaries
- tracked findings
- variant analysis

If a sidecar fails, degrade instead of blocking the whole review flow.

## Artifact Completion Rule

Docs-first verification belongs at artifact completion, not at apply time.

If a caller completes artifacts, the flow should automatically verify them.
The main process should not stop and ask the user to manually bless the bundle if the loop already requires verification.

That means:

- artifact completion callers should hand off to docs-first review immediately
- apply-stage repair should not be the first place artifact quality gets fixed

## Resolver Lesson

The transition resolver exists because the main process previously had too much room to improvise workflow decisions from prose.

Useful resolver principles:

- orchestration authority must be mechanically constrained
- semantic judgment stays with the reviewer
- path coherence matters
- retry/reopen/fresh-session behavior must be explicit
- resolver outputs must be normalized and deterministic

The resolver is orchestration-only.

It should not become a second reviewer.

## Minimal Active Surface

The active surface should stay small:

- current authoritative verification flow
- review-loop reference index
- review-loop module docs
- resolver docs and contracts

Historical planning documents should not remain in the active path once their useful parts have been absorbed.

## What Was Kept From The Old Rollout Docs

Kept:

- same-session working reruns
- challenger freshness
- challenger-only closure
- docs-first verification at artifact completion
- sidecars must not become gates
- only stable capability gets promoted into a contract

Dropped:

- separate planner gate
- ledger as a new authority surface
- variant analysis as closure blocker
- any split between artifact and implementation semantics

## What To Read First

1. `docs/review-flow/current-authoritative-verification-flow.md`
2. `openspec/schemas/modules/review-loop/REFERENCE-INDEX.md`
3. `openspec/schemas/modules/review-loop/README.md`
4. `openspec/schemas/modules/review-loop/VERIFY-IMPLEMENTATION.md`

If you need the historical rollout rationale, read the archive of the old
`code-review-first` docs after this summary.
