## Context

<!-- Background and current state -->

## Goals / Non-Goals

**Goals:**
<!-- What this design aims to achieve -->

**Non-Goals:**
<!-- What is explicitly out of scope -->

## Decisions

<!-- Key design decisions and rationale -->

## Independent Verification Plan (STANDARD/STRICT)

Document verification using shared sequence `verify-sequence/default` from:
`openspec/schemas/ai-enforced-workflow/verification-sequence.md`

Stage A flow:
- Artifact review:
  - docs are the primary surface
  - passing artifact review allows implementation entry
  - blocking artifact findings stop implementation entry
- Implementation review:
  - code, tests, and directly impacted code are the primary surface
  - approved artifacts are reference material
  - repository-index support is optional cache help only
  - same-session reruns stay in the active working reviewer session
  - challenger pass is the only implementation closure authority

Runtime profile policy:
- Use verifier runtime profile from `.codex/agents/verify-reviewer.toml`.
- Use index-maintainer runtime profile from
  `.codex/agents/index-maintainer.toml` when cache refresh is useful.

Loop rule:
- Same-session implementation reruns MAY continue inside the active working
  reviewer session after repair.
- Same-session zero findings are convergence-only.
- Challenger pass MUST run in a newly spawned verifier session.
- If a challenger pass returns findings, that session becomes the new active
  working baseline.
- Only an implementation challenger pass with zero findings may close the
  checkpoint.

## Repository Index Cache Plan (When Useful)

Document repository-index support explicitly when cache artifacts can help
review orientation.

Required fields:
- Index contract id: `repo-index-v1`
- Canonical repository-index root
- Shared cache-helper sequence: `index-sequence/default`
- Optional refresh scoping hints
- Fallback policy (`refresh|bypass`)
- Verifier invocation template: `verify-reviewer-inline-v2`
- Index-maintainer agent path: `.codex/agents/index-maintainer.toml`
- Index skill entry points:
  - `openspec-index-preflight`
  - `openspec-index-maintain`
- Cache-helper evidence path convention
- Findings path convention
- Verifier execution evidence path convention
- Cache handoff fields:
  - `index_context.contract`
  - `index_context.manifest_path`
  - `index_context.manifest_present`
  - `index_context.preflight_report_path`
  - `index_context.cache_mode`
  - `index_context.fallback_policy`

Minimal verification bundle (reuse exactly):
- `change`
- `mode`
- `review_phase`
- `review_pass_type`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract`

Review completion contract:
- execution evidence MUST record:
  - `review_phase`
  - `review_pass_type`
  - `cache_mode`
  - `closure_authority`
  - `verifier_output_path`
  - `reviewed_paths`
  - `skipped_paths`
  - `reviewed_axes`
  - `unreviewed_axes`
  - `coverage_status`
  - `saturation_status`
  - optional `early_stop_reason`
  - optional `skip_reasons`
- implementation review MUST additionally record inline:
  - `review_scope`
  - `review_coverage`

### Artifact Verification

- Sequence reference: `verify-sequence/default`
- Mode: `artifact`
- Review phase: `artifact`
- Review pass type: `working`
- Verifier agent path: `.codex/agents/verify-reviewer.toml`
- Invocation template id: `verify-reviewer-inline-v2`
- Primary review surface: changed `proposal/specs/design/tasks`
- Default cache mode: `bypassed`
- Authoritative verifier-subagent findings JSON path:
- Verifier execution evidence JSON path:
- Acceptance rule: blocking findings stop implementation entry
- Skill entry point: `openspec-artifact-verify`

### Implementation Verification

- Sequence reference: `verify-sequence/default`
- Cache-helper sequence reference: `index-sequence/default`
- Mode: `implementation`
- Review phase: `implementation`
- Review pass types:
  - `working`
  - `challenger`
- Verifier agent path: `.codex/agents/verify-reviewer.toml`
- Index-maintainer agent path: `.codex/agents/index-maintainer.toml`
- Invocation template id: `verify-reviewer-inline-v2`
- Primary review surface: changed code, changed tests, directly impacted code
- Optional cache-helper report path:
- Authoritative verifier-subagent findings JSON path:
- Verifier execution evidence JSON path:
- Inline implementation evidence:
  - `review_scope`
  - `review_coverage`
- Loop behavior:
  - same-session reruns handle convergence
  - challenger pass starts only after zero findings with complete coverage
- Continuation target on pass:
- Skill entry point: `openspec-verify-change`

### Optional Gemini Dual Review

Use only when repository or checkpoint policy explicitly enables dual review.

- Runner contract: `gemini-capture`
- Raw report path:
- Normalized report path:
- Maximum attempts:
- Recovery behavior:
  - `input_raw_path -> report_path`
- Resolved command goes in execution evidence, not workflow policy prose

## Migration Plan

<!-- Rollout, rollback, or transition notes -->

## Open Questions

<!-- Outstanding decisions or unknowns -->

## Risks / Trade-offs

<!-- Known risks and trade-offs -->
