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

Two-stage flow:
- Stage 1: read-only verifier subagent (`.codex/agents/verify-reviewer.toml`) review
- Stage 2: Gemini second opinion through logical runner contract `gemini-capture` only when required (`STRICT` or explicit dual gate)

Runtime profile policy:
- Use verifier runtime profile from `.codex/agents/verify-reviewer.toml` by default.

Loop rule:
- Each verify/fix iteration MUST spawn a fresh verifier instance with no inherited verifier memory.

Continuation override vocabulary:
- The only supported continuation overrides are `verify-only`, `dry-run`, and `manual_pause`.
- Do not substitute ad hoc phrases such as "manual stop" or "pause after a stage".

Minimal verification bundle (reuse exactly):
- `change`
- `mode`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract`
- `retry_policy`

### Artifact Verification

- Sequence reference: `verify-sequence/default`
- Mode: `artifact`
- Verifier agent path: `.codex/agents/verify-reviewer.toml`
- Invocation method: built-in subagent API in main process
- Invocation template id: `verify-reviewer-inline-v1`
- Verifier-subagent review scope:
- Authoritative verifier-subagent findings JSON path:
- Verifier execution evidence JSON path:
- Verifier runtime profile: from `.codex/agents/verify-reviewer.toml`
- Gemini policy: `STRICT` or explicit dual gate only
- Runner contract: `gemini-capture`
- Prompt inputs:
- Output format: `authoritative verifier-subagent findings json + execution evidence json` (+ Gemini raw/report when enabled)
- Raw report path (when Gemini enabled):
- `report_path` (when Gemini enabled):
- Fallback behavior: `retry once; if raw exists but report_path output is missing, run recovery using input_raw_path -> report_path before blocking`
- Originating phase field: `artifact_gate`
- Continuation target on pass: `apply`
- Loop behavior: `artifact mode does not perform implementation auto-fix; a passing artifact gate hands off to apply`
- Execution evidence path: record verifier invocation metadata (`agent_id/start_at/end_at/final_state`) and Gemini resolved command when Gemini runs
- Skill entry point: `openspec-artifact-verify`

### Implementation Verification

- Sequence reference: `verify-sequence/default`
- Mode: `implementation`
- Verifier agent path: `.codex/agents/verify-reviewer.toml`
- Invocation method: built-in subagent API in main process
- Invocation template id: `verify-reviewer-inline-v1`
- Verifier-subagent review scope:
- Authoritative verifier-subagent findings JSON path:
- Verifier execution evidence JSON path:
- Verifier runtime profile: from `.codex/agents/verify-reviewer.toml`
- Gemini policy: `STRICT` or explicit dual gate only
- Runner contract: `gemini-capture`
- Prompt inputs:
- Output format: `authoritative verifier-subagent findings json + execution evidence json` (+ Gemini raw/report when enabled)
- Raw report path (when Gemini enabled):
- `report_path` (when Gemini enabled):
- Fallback behavior: `retry once; if raw exists but report_path output is missing, run recovery using input_raw_path -> report_path before blocking`
- Loop behavior: `if auto-fixable implementation findings exist and budget remains, main flow fixes then reruns with a fresh verifier instance`
- Originating phase field: `apply` or `implementation_verify`
- Continuation target on pass: `implementation_verify` while implementation work already exists; otherwise archive/report completion according to caller flow
- Execution evidence path: record verifier invocation metadata (`agent_id/start_at/end_at/final_state`) and Gemini resolved command when Gemini runs
- Skill entry point: `openspec-verify-change`

<!--
Use absolute or repo-relative file paths in the prompt inputs.
If repair reruns are required, document whether `openspec-repair-change`
reuses the same Gemini contract or writes a new report path.
-->

## Migration Plan

<!-- Rollout, rollback, or transition notes -->

## Open Questions

<!-- Outstanding decisions or unknowns -->

## Risks / Trade-offs

<!-- Known risks and trade-offs -->
