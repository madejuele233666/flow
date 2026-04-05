---
name: openspec-artifact-verify
description: Verify proposal, specs, design, and tasks before implementation. Use when the user wants to check whether a change plan is complete, correct, coherent, and ready for apply.
license: MIT
compatibility: Works with any OpenSpec change.
metadata:
  author: project
  version: "1.2"
---

# OpenSpec Artifact Verify (Thin Entrypoint)

This skill is an entry point for artifact verification orchestration. It does not redefine runner flow.

Shared sequence reference:
- `openspec/schemas/ai-enforced-workflow/verification-sequence.md#verify-sequence/default`
- Verifier invocation template: `verify-reviewer-inline-v1`

## Entrypoint Contract

- `mode`: `artifact`
- `evidence`: proposal/specs/design/tasks paths selected for review
- `report path`: authoritative verifier-subagent findings JSON path, verifier execution evidence JSON path, and Gemini raw/report paths (when Gemini is enabled)
- `routing target`: `openspec-repair-change` for blocked findings
- `success continuation`: `openspec-apply-change` unless caller explicitly requests `verify-only`, `dry-run`, or `manual_pause`
- `runtime profile`: from `.codex/agents/verify-reviewer.toml`

## Steps

1. Resolve change (`openspec status --change "<name>" --json`).
2. Load artifact evidence from `openspec instructions apply --change "<name>" --json`.
3. Build minimal verification bundle:
- `change`
- `mode=artifact`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract=shared-findings-v1`
- `retry_policy`
4. Execute shared sequence `verify-sequence/default` using a fresh verifier instance (no inherited verifier memory).
5. Require authoritative verifier-subagent findings JSON and execution evidence JSON with invocation metadata before treating the artifact gate as complete.
6. If the result is blocked, route to `openspec-repair-change`.
7. If the result is `pass` or policy-acceptable `pass_with_warnings`, automatically hand off to `openspec-apply-change` for the same change unless the caller explicitly requested `verify-only`, `dry-run`, or `manual_pause`.
8. If repair reruns are needed, keep artifact rerun and apply handoff in the same automatic chain; do not require the user to manually restart `/opsx:apply` after a passing artifact rerun.
9. Return outcome, routing decision, continuation target, and authoritative output paths.

## Guardrails

- Keep this skill thin; orchestration behavior belongs to shared sequence.
- Enforce fresh verifier instance on each rerun; do not reuse prior verifier memory.
- Do not inline platform-specific command bodies in task policy text.
- Record resolved runner command only in execution evidence/logs.
- Do not stop on a passing artifact gate just to ask the user to run apply manually unless the caller explicitly requested `verify-only`, `dry-run`, or `manual_pause`.
- Do not treat manually authored markdown summaries as authoritative verifier evidence.
- Do not perform implementation auto-fix from `mode=artifact`; a passing artifact gate hands off to apply, and blocking findings route to repair.
