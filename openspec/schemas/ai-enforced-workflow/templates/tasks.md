## 0. Verification Contract

- Shared sequence:
  - `openspec/schemas/ai-enforced-workflow/verification-sequence.md#verify-sequence/default`
- Cache-helper sequence:
  - `openspec/schemas/ai-enforced-workflow/index-sequence.md#index-sequence/default`
- Minimal verification bundle fields:
  - `change`
  - `mode`
  - `review_phase`
  - `review_pass_type`
  - `risk_tier`
  - `evidence_paths_or_diff_scope`
  - `findings_contract`
- Optional `index_context` fields:
  - `contract`
  - `manifest_path`
  - `manifest_present`
  - `preflight_report_path`
  - `cache_mode`
  - `fallback_policy`
- Required `output_paths` fields:
  - `findings_path`
  - `verifier_evidence_path`
  - optional `gemini_raw_path`
  - optional `gemini_report_path`
  - optional `spawn_decision_path`
- Routing target for blocking findings:
  - `openspec-repair-change`
- Supported continuation overrides:
  - `verify-only`
  - `dry-run`
  - `manual_pause`

## 1. <!-- Task Group Name -->

- [ ] 1.1 <!-- Task description -->
- [ ] 1.2 <!-- Task description -->

## 2. <!-- Task Group Name -->

- [ ] 2.1 <!-- Task description -->
- [ ] 2.2 <!-- For STANDARD/STRICT work: document artifact review, implementation working review, challenger closure, optional cache-helper use, and authoritative evidence paths. Require `agent-spawn-decision-v1` before any new verifier or index-maintainer spawn. Require implementation evidence to include inline `review_scope` and `review_coverage`. State that implementation reruns stay in the working session until challenger entry conditions are met. -->
- [ ] 2.3 [Checkpoint] Run verifier-subagent review for <!-- schema diff / skill output / verification report --> using `verify-sequence/default`. Use repository-index helper `index-sequence/default` only when cache discovery or refresh is useful; do not require cache authority before review. Use the verification contract above for bundle fields, optional `index_context`, required `output_paths`, routing target, and any caller-local guardrails. Write authoritative verifier-subagent findings JSON and verifier execution evidence JSON. Require implementation checkpoints to include inline `review_scope` and `review_coverage`. Same-session implementation reruns are convergence-only; challenger is the only implementation closure authority. If the checkpoint explicitly enables Gemini dual review, run logical runner contract `gemini-capture`, write both raw and normalized reports, require JSON-normalized output, and use recovery (`input_raw_path -> report_path`) before blocking.

## 3. <!-- Task Group Name -->

- [ ] 3.1 <!-- Task description -->
- [ ] 3.2 <!-- Task description -->
