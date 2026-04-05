# verify-sequence/default

Shared verification orchestration for `ai-enforced-workflow` across any project domain.

Consumers:
- `.codex/skills/openspec-artifact-verify/SKILL.md`
- `.codex/skills/openspec-verify-change/SKILL.md`
- `.codex/skills/openspec-apply-change/SKILL.md`
- `.codex/skills/openspec-repair-change/SKILL.md`
- `openspec/schemas/ai-enforced-workflow/schema.yaml` apply/checkpoint instructions

## Verifier Agent Contract

- Agent definition: `.codex/agents/verify-reviewer.toml`
- Role: reviewer only (read-only)
- Parent-context rule: do not inherit full implementer conversation
- Loop-state rule: every verify pass MUST use a fresh verifier instance (no prior verifier memory)
- Output rule: normalized JSON only; malformed output blocks the step
- Invocation rule: verifier runs MUST use built-in subagent invocation from the
  main process (shell invocation is fallback-only)
- Invocation template id: `verify-reviewer-inline-v1`

## Minimal Verification Bundle (Single Source)

The verifier invocation bundle is defined once here and reused by schema, templates, and skills:

- `change`
- `mode`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract`
- `retry_policy`

`mode` is `artifact` or `implementation`.

## Runtime Profile Policy

Verifier runtime profile comes from `.codex/agents/verify-reviewer.toml` for this shared sequence.

## Authoritative Verification Evidence

Checkpoint acceptance requires authoritative verifier evidence, not a manually
written summary.

Required authoritative outputs per verifier iteration:
- verifier-subagent findings JSON path
- verifier execution evidence JSON path

Markdown summaries are optional derivative artifacts only. They are not
authoritative and MUST NOT satisfy the gate by themselves.

Minimum execution evidence fields:
- `change`
- `mode`
- `template_id`
- `findings_contract`
- `agent_id`
- `start_at`
- `end_at`
- `final_state`
- `verifier_output_path`
- optional `gemini_raw_path`
- optional `gemini_report_path`

## Findings Contract

Normalized verifier JSON:

```json
{
  "change": "<change-name>",
  "mode": "artifact|implementation",
  "final_assessment": "pass|pass_with_warnings|blocked",
  "findings": [
    {
      "id": "F-001",
      "severity": "CRITICAL|WARNING|SUGGESTION",
      "dimension": "Completeness|Correctness|Coherence",
      "artifact": "proposal|specs|design|tasks|implementation",
      "problem": "...",
      "evidence": "...",
      "recommendation": "...",
      "redirect_layer": "proposal|specs|design|tasks|implementation",
      "blocking": true,
      "auto_fixable": false
    }
  ]
}
```

Supported bundle identifier:
- `findings_contract` MUST be `shared-findings-v1`.
- Any other `findings_contract` value blocks the checkpoint before verification.

Cross-field findings constraints (`shared-findings-v1`):
- `id` MUST be unique within a single findings array.
- Across consecutive reruns in the same verify/fix loop, semantically unchanged
  unresolved findings MUST keep the same `id`.
- `auto_fixable=true` is valid only when `redirect_layer=implementation`.
- Findings with `redirect_layer` other than `implementation` MUST set
  `auto_fixable=false`.
- `severity=SUGGESTION` MUST set `blocking=false`.
- Any violation above is a contract failure and blocks the checkpoint before
  routing/classification.

## Built-in Invocation Template: `verify-reviewer-inline-v1`

Use this in-process invocation structure for verifier runs:

```json
{
  "agent_type": "verify-reviewer",
  "bundle": {
    "change": "<change-name>",
    "mode": "artifact|implementation",
    "risk_tier": "LIGHT|STANDARD|STRICT",
    "evidence_paths_or_diff_scope": ["..."],
    "findings_contract": "shared-findings-v1",
    "retry_policy": { "...": "..." }
  }
}
```

Wait organization requirements:
- main process waits on the built-in subagent API directly (no shell wait loop
  required for codex verifier invocation)

Execution evidence requirements:
- Record invocation metadata per run:
  `agent_id`, `start_at`, `end_at`, `final_state`
- Record authoritative verifier findings JSON path and execution evidence JSON
  path, plus any Gemini raw/report paths used

Task policy rule:
- Tasks and templates reference template id `verify-reviewer-inline-v1`; do not
  require shell command bodies for codex verifier invocation.

## Sequence

1. Validate entry constraints before verification:
- `findings_contract` is `shared-findings-v1`
2. Start verify/fix loop iteration with a fresh `verify-reviewer` instance.
3. Invoke `verify-reviewer` via built-in subagent API with the minimal
   verification bundle using template `verify-reviewer-inline-v1`.
4. Require authoritative verifier evidence artifacts for this iteration:
- verifier-subagent findings JSON exists
- execution evidence JSON exists and contains invocation metadata
5. Validate normalized verifier-subagent findings JSON against `shared-findings-v1`:
- envelope keys: `change`, `mode`, `final_assessment`, `findings`
- enum values for `final_assessment`, `severity`, `dimension`, `artifact`,
  `redirect_layer`
- required per-finding fields for routing and auto-fix gates
- cross-field constraints above (`id` uniqueness, `id` stability across
  consecutive reruns for unchanged unresolved findings, `auto_fixable`/`redirect_layer`,
  `SUGGESTION`/`blocking`)
6. Decide second-opinion gate:
- mandatory when `risk_tier=STRICT` or checkpoint is explicitly dual-gated
- optional otherwise
7. If Gemini is required, execute logical runner contract `gemini-capture`.
8. If primary Gemini execution writes raw but misses report JSON at
   `report_path`, run recovery using existing raw envelope.
9. Merge verifier-subagent and Gemini findings when both exist:
- preserve disagreements explicitly instead of silently collapsing them
- when either reviewer reports a blocking upstream finding, treat it as a
  repair-routing blocker
10. Classify findings:
- eligible auto-fix candidate: `mode=implementation` and `blocking=true` and
  `redirect_layer=implementation && auto_fixable=true`
- repair-routing blocker: any `blocking=true` finding that is not an eligible
  auto-fix candidate
- policy-acceptable non-blocking warning/suggestion: may terminate without
  repair routing unless checkpoint policy marks it must-fix
11. If any repair-routing blocker exists, stop auto-fix loop and route to
   `openspec-repair-change`.
12. If eligible auto-fix candidates exist and no repair-routing blocker exists,
    and implementation budget remains, main flow applies fixes, then return to
    step 1 with a fresh verifier instance (no inherited verifier memory).
13. Stop loop when one of the following holds:
- no blocking findings remain (`pass` or policy-acceptable warnings)
- no eligible auto-repair findings remain
- retry budget exhausted
- the same blocking finding repeats across consecutive iterations after
  attempted implementation auto-fix (`id` + `redirect_layer`)
- non-implementation blocker requires explicit repair routing

## Runner Contract: `gemini-capture`

Required inputs:
- logical runner id (`gemini-capture`)
- prompt source
- raw report path
- report path (`report_path`)
- maximum attempts
- JSON-response requirement
- optional `input_raw_path` for recovery

Output requirements:
- raw Gemini envelope JSON
- normalized report JSON at `report_path`

Policy:
- tasks and templates reference the logical runner contract only
- resolved Linux/Windows command is recorded in execution evidence or logs

## Retry Policy

Keep separate counters:
- `artifact_rerun_budget`: reruns after artifact-layer corrections
- `implementation_auto_fix_budget`: auto-fix loops for implementation findings

A rerun in one flow does not consume budget from the other flow.

## Automatic Continuation Policy

Default `ai-enforced-workflow` continuation is automatic unless the caller
explicitly requests `verify-only`, `dry-run`, or `manual_pause`.

Automatic phase chaining rules:
- successful artifact verification (`pass` or policy-acceptable
  `pass_with_warnings`) hands off directly to `openspec-apply-change`
  instead of waiting for a separate manual `/opsx:apply`
- successful implementation verification returns control to the active
  caller so completion/reporting can continue without a separate manual
  `/opsx:verify`
- repair-triggered reruns continue automatically: artifact repair reruns
  artifact verification first; if it passes, `artifact_gate` resumes apply,
  while `apply` or `implementation_verify` resumes implementation verification
  only when implementation work already exists for that originating phase
- implementation auto-fix reruns stay inside the active apply/verify loop
  until pass, blocking upstream repair, or budget stop conditions occur

## Project-Agnostic Enforcement Scope

Any change using `ai-enforced-workflow` MUST follow this sequence regardless of repository, stack, or product domain.
