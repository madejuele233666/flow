---
name: openspec-verify-change
description: Verify implementation matches change artifacts. Use when the user wants to validate that implementation is complete, correct, and coherent before archiving.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.2"
  generatedBy: "1.2.0"
---

Use this as a thin implementation-verification entrypoint.

Shared sequence reference:
- `openspec/schemas/ai-enforced-workflow/verification-sequence.md#verify-sequence/default`
- Verifier invocation template: `verify-reviewer-inline-v1`

## Entrypoint Contract

- `mode`: `implementation`
- `evidence`: changed implementation files plus tasks/specs/design and verification artifacts
- `report path`: authoritative verifier-subagent findings JSON path, verifier execution evidence JSON path, and Gemini raw/report paths (when Gemini is enabled)
- `routing target`: `openspec-repair-change` for findings that cannot be auto-fixed in implementation
- `success continuation`: return control to the active apply/repair flow automatically unless the caller explicitly requested `verify-only`, `dry-run`, or `manual_pause`
- `runtime profile`: from `.codex/agents/verify-reviewer.toml`

## Steps

1. Resolve change (`openspec status --change "<name>" --json`).
2. Load change context and implementation evidence (`openspec instructions apply --change "<name>" --json`).
3. Build minimal verification bundle:
- `change`
- `mode=implementation`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract=shared-findings-v1`
- `retry_policy`
4. Execute shared sequence `verify-sequence/default` using a fresh verifier instance (no inherited verifier memory).
5. Require authoritative verifier-subagent findings JSON and execution evidence JSON with invocation metadata before treating the implementation gate as complete.
6. If findings are eligible for automatic implementation repair, return them to the active apply/verify loop and rerun verification automatically within budget.
7. If findings require upstream repair, route to `openspec-repair-change`; after repair, rerun the required verification automatically rather than waiting for a manual `/opsx:verify`.
8. If the result is `pass` or policy-acceptable `pass_with_warnings`, return success to the active flow so completion/reporting can continue without a separate user command.
9. Return outcome, retry usage, routing decision, continuation target, and authoritative output paths.

## Guardrails

- Keep this skill thin; orchestration behavior belongs to shared sequence.
- Enforce fresh verifier instance on each rerun; do not reuse prior verifier memory.
- Do not duplicate platform runner command text in policy/task prose.
- Record resolved runner command only in execution evidence/logs.
- Do not force a manual verify rerun when the shared sequence and retry policy still permit automatic continuation.
- Do not treat a manually authored verifier summary as authoritative evidence.
