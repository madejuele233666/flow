# Stage A Direct Rollout

## Status

Direct rollout document for completing `code-review-first` Stage A without
creating a new OpenSpec change.

This file is execution support only. It does not replace the authoritative
layered design in:
- `docs/code-review-first/01-principles-and-boundaries.md`
- `docs/code-review-first/03-layer-1-core-review-loop.md`
- `docs/code-review-first/04-layer-2-lightweight-scope-summary.md`
- `docs/code-review-first/08-migration-validation-and-stop-rules.md`

## Scope

This rollout covers only:
- Layer 1: Core Review Loop
- Layer 2: Lightweight Scope Summary

This rollout does not cover:
- tracked findings
- variant analysis
- contract hardening
- standalone planner artifacts

## Working Rule

Because this repository change rewrites the workflow itself, the rollout uses
direct file edits plus local validation instead of a new `openspec/changes/*`
change.

The layered documents above remain the external authority.

Direct rollout validation entrypoints:
- `openspec/bin/stagea_direct_rollout_validate.py`
  - mechanical contract checks over the explicit Stage A file set
- direct reviewer pass over the same explicit file set
  - uses file-path evidence directly
  - does not require `openspec/changes/*`

## Deliverables

Stage A is complete only when all of the following are true:

1. Artifact review and implementation review are explicit separate phases.
2. Artifact review can independently block implementation entry.
3. Implementation review no longer depends on repo-index as a gate.
4. Working reviewer sessions can be reused across repair reruns.
5. Challenger pass is the only closure authority for implementation review.
6. `verifier-evidence.json` records:
   - `review_phase` (`docs_first|source_first`)
   - `review_pass_type`
   - `cache_mode`
   - `closure_authority`
7. Implementation review evidence also records:
   - `review_scope`
   - `review_coverage`
8. No standalone planner file, planner schema, or planner agent is added.
9. No `tracked-findings.json` or `variant-analysis.json` is introduced.

## Files In Scope

Shared workflow contracts:
- `openspec/schemas/ai-enforced-workflow/verification-sequence.md`
- `openspec/schemas/ai-enforced-workflow/index-sequence.md`
- `openspec/schemas/ai-enforced-workflow/schema.yaml`
- `openspec/schemas/ai-enforced-workflow/agent-spawn-decision-v1.schema.json`

Agent definitions:
- `.codex/agents/verify-reviewer.toml`
- `.codex/agents/index-maintainer.toml`

Skills:
- `/home/madejuele/.codex/skills/openspec-propose/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-ff-change/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-continue-change/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-artifact-verify/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-verify-change/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-repair-change/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-apply-change/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-index-preflight/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-index-maintain/SKILL.md`

Supporting specs:
- `openspec/specs/verify-subagent-orchestration/spec.md`

## Execution Order

1. Finish Layer 1 shared contract rewrites.
2. Update agent prompts and skills to match Layer 1.
3. Validate Layer 1 behavior and semantics.
4. Add Layer 2 inline `review_scope` and `review_coverage`.
5. Validate full Stage A behavior.

## Stop Rules

Stop and repair before continuing if any of the following appear:
- repo-index still defines implementation authority scope
- missing repo-index still blocks implementation review
- the artifact-completion caller does not run docs-first review before
  implementation entry
- `openspec-apply-change` reopens the docs-first artifact gate
- `review_scope` becomes a standalone gate
- `review_scope` requires a dedicated planner artifact or agent
- Gemini is described as a mandatory Stage A gate

## Validation Targets

Validation must prove:
- artifact blockers stop implementation entry
- implementation review can continue with `cache_mode=missed` or
  `cache_mode=stale_but_ignored`
- zero-findings working implementation review is convergence only
- implementation closure requires a challenger pass
- challenger pass cannot start from `review_coverage.coverage_status=partial`
