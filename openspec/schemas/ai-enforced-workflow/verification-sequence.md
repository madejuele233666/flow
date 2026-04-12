# verify-sequence/default

Shared Stage A verification orchestration for `ai-enforced-workflow` across any
project domain.

Consumers:
- `$CODEX_HOME/skills/openspec-artifact-verify/SKILL.md`
- `$CODEX_HOME/skills/openspec-verify-change/SKILL.md`
- `$CODEX_HOME/skills/openspec-apply-change/SKILL.md`
- `$CODEX_HOME/skills/openspec-repair-change/SKILL.md`
- `openspec/schemas/ai-enforced-workflow/schema.yaml`
- `openspec/schemas/ai-enforced-workflow/index-sequence.md`

## Stage A Goal

Keep the main path short:

```text
artifact review
  -> pass or block implementation entry

implementation review (working)
  -> repair reruns stay in same working session
  -> zero findings with complete coverage
  -> challenger pass
  -> close or reopen
```

`repo-index` is optional cache support only.
It is never the authority for implementation scope, coverage completion, or
closure.

## Verifier Agent Contract

- Agent definition: `.codex/agents/verify-reviewer.toml`
- Role: reviewer only (read-only)
- Parent-context rule: do not inherit full implementer conversation
- Review phases:
  - `artifact`
  - `implementation`
- Review pass types:
  - `working`
  - `challenger`
- Session rule:
  - artifact review normally uses `review_pass_type=working`
  - implementation repair reruns MAY continue inside the active working session
  - challenger passes MUST use a fresh verifier session
- Authority rule:
  - artifact review may block implementation entry
  - implementation closure authority comes only from a challenger pass
- Output rule: normalized JSON only; malformed output blocks the step
- Invocation rule: verifier runs MUST use built-in subagent invocation from the
  main process (shell invocation is fallback-only)
- Invocation template id: `verify-reviewer-inline-v2`

## Minimal Verification Bundle

The verifier invocation bundle is defined once here and reused by schema,
templates, and skills:

- `change`
- `mode`
- `review_phase`
- `review_pass_type`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract`

Rules:
- `mode` remains `artifact|implementation` for findings-envelope compatibility.
- `review_phase` MUST be `artifact|implementation`.
- `mode` and `review_phase` MUST match.
- `review_pass_type` MUST be `working|challenger`.

The invocation envelope MAY extend with optional `index_context`:
- `contract`
- `manifest_path`
- `manifest_present`
- `preflight_report_path`
- `cache_mode`
- `fallback_policy`

`index_context` is cache handoff only. It does not define the authoritative
review surface.

The invocation envelope MUST also carry checkpoint-scoped `output_paths` owned
by the main process:
- `findings_path`
- `verifier_evidence_path`
- optional `gemini_raw_path`
- optional `gemini_report_path`
- optional `spawn_decision_path`

## Runtime Profile Policy

Verifier runtime profile comes from `.codex/agents/verify-reviewer.toml`.

## Agent Spawn Decision Contract

Any new verifier or index-maintainer spawn in this workflow MUST be preceded by
an `agent-spawn-decision-v1` JSON record.

Canonical schema:
- `openspec/schemas/ai-enforced-workflow/agent-spawn-decision-v1.schema.json`

Canonical example:

```json
{
  "contract": "agent-spawn-decision-v1",
  "change": "<change-name>",
  "phase": "artifact_gate|apply|implementation_verify|preflight|repair",
  "requested_agent_type": "verify-reviewer|index-maintainer",
  "spawn_kind": "policy_required|exception",
  "reason_code": "initial_working_session|challenger_pass|index_refresh_required|active_session_unavailable|session_unresumable|tooling_recovery",
  "decision": "allow|deny",
  "recorded_at": "2026-04-12T12:34:56Z",
  "summary": "...",
  "prior_session": {
    "agent_id": null,
    "session_role": "none|working|challenger|maintenance",
    "reuse_expected": false,
    "reuse_attempted": false,
    "reuse_succeeded": false,
    "reuse_blocker": "not_applicable|policy_requires_challenger|agent_not_found|session_completed_unresumable|tooling_recovery"
  },
  "policy_basis": {
    "sequence_ref": "openspec/schemas/ai-enforced-workflow/verification-sequence.md#verify-sequence/default",
    "rule_ref": "initial-working-session|challenger-pass|index-refresh|exception-recovery"
  },
  "evidence": {
    "findings_path": ".../findings.json",
    "verifier_evidence_path": ".../verifier-evidence.json",
    "preflight_report_path": ".../implementation-index-preflight.json"
  },
  "notes": []
}
```

Field rules:
- `decision=allow` is required before spawning.
- Policy-required verifier spawns are:
  - `initial_working_session`
  - `challenger_pass`
- Same-session implementation reruns MUST reuse the active working verifier
  session unless an exception record explicitly allows a new spawn.
- `spawn_kind=policy_required` is for normal workflow-mandated spawns only:
  `initial_working_session`, `challenger_pass`, `index_refresh_required`.
- `spawn_kind=exception` is for otherwise-disallowed new spawns caused by
  failed reuse only: `active_session_unavailable`, `session_unresumable`,
  `tooling_recovery`.
- `reason_code=challenger_pass` requires
  `prior_session.reuse_blocker=policy_requires_challenger`.

## Authoritative Verification Evidence

Checkpoint acceptance requires authoritative verifier findings JSON plus
verifier execution evidence JSON.

Repository-index cache evidence is optional support evidence only. It does not
replace verifier evidence and it does not define closure authority.

Minimum execution evidence fields:
- `change`
- `mode`
- `review_phase`
- `review_pass_type`
- `template_id`
- `findings_contract`
- `agent_id`
- `start_at`
- `end_at`
- `final_state`
- `cache_mode`
- `closure_authority` (`none|challenger_confirmed`)
- `verifier_output_path`
- `reviewed_paths`
- `skipped_paths`
- `reviewed_axes`
- `unreviewed_axes`
- `coverage_status` (`complete|partial`)
- `saturation_status` (`exhaustive|early_stop`)
- `skip_reasons` (required when `skipped_paths` is non-empty)
- optional `early_stop_reason`
- optional `gemini_raw_path`
- optional `gemini_report_path`
- optional `gemini_resolved_command`
- optional `verifier_session_id`
- optional `session_rerun_index`
- optional `fresh_spawn_index`
- optional `spawn_reason`
- optional `spawn_decision_path`
- optional `index_contract`
- optional `index_manifest_path`
- optional `index_preflight_report_path`
- optional `index_mode`

Implementation-review evidence MUST additionally include:
- `review_scope`
- `review_coverage`

Field rules:
- `closure_authority=challenger_confirmed` is valid only on an implementation
  `review_pass_type=challenger` pass with zero findings.
- artifact review normally records `cache_mode=bypassed`.
- implementation review may record:
  `used|missed|stale_but_ignored|refreshed|bypassed`.

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

Cross-field findings constraints (`shared-findings-v1`):
- `id` MUST be unique within a single findings array.
- `auto_fixable=true` is valid only when `redirect_layer=implementation`.
- Findings with `redirect_layer` other than `implementation` MUST set
  `auto_fixable=false`.
- `severity=SUGGESTION` MUST set `blocking=false`.

## Review Coverage Contract

Pass-level execution evidence remains authoritative for coverage and saturation.

Coverage semantics:
- `reviewed_paths`: files or artifacts reviewed in this pass
- `skipped_paths`: declared paths intentionally not reviewed in this pass
- `reviewed_axes`: review axes completed in this pass
- `unreviewed_axes`: review axes not completed in this pass
- `coverage_status`:
  - `complete`: the declared review surface for this pass was covered
  - `partial`: the pass ended without full declared review coverage
- `saturation_status`:
  - `exhaustive`: the reviewer completed the pass
  - `early_stop`: the reviewer stopped before exhausting the declared surface

Stage A derivation rules:
- artifact review derives its primary surface from changed
  `proposal/specs/design/tasks`
- implementation review derives its primary surface from:
  - changed code
  - changed tests
  - directly impacted code
  - approved artifacts as reference material
  - optional repository-index cache hints
- repository-index cache MUST NOT freeze implementation authority scope
- reviewers MUST NOT derive authority from `required_paths` or `required_axes`

Implementation inline structures:

```json
{
  "review_scope": {
    "changed_code_paths": ["..."],
    "changed_test_paths": ["..."],
    "impacted_interfaces": ["..."],
    "mandatory_deep_scan_paths": ["..."],
    "cache_inputs": ["..."]
  },
  "review_coverage": {
    "reviewed_paths": ["..."],
    "deep_scanned_paths": ["..."],
    "skipped_paths": [
      {
        "path": "...",
        "reason": "...",
        "skip_class": "deferred|irrelevant|blocked-by-missing-context"
      }
    ],
    "coverage_status": "complete|partial"
  }
}
```

Implementation rules:
- `review_scope` and `review_coverage` live inside `verifier-evidence.json`.
- `review_scope` is review support, not a separate gate.
- `coverage_status=partial` blocks implementation convergence and challenger
  entry, but it does not create a separate planner authority layer.
- challenger passes MAY start only after the latest working implementation pass
  has:
  - zero findings
  - `coverage_status=complete`
  - `saturation_status=exhaustive`

## Built-in Invocation Template: `verify-reviewer-inline-v2`

Use this in-process invocation structure for verifier runs:

```json
{
  "agent_type": "verify-reviewer",
  "bundle": {
    "change": "<change-name>",
    "mode": "artifact|implementation",
    "review_phase": "artifact|implementation",
    "review_pass_type": "working|challenger",
    "risk_tier": "LIGHT|STANDARD|STRICT",
    "evidence_paths_or_diff_scope": ["..."],
    "findings_contract": "shared-findings-v1"
  },
  "index_context": {
    "contract": "repo-index-v1",
    "manifest_path": "...",
    "manifest_present": true,
    "preflight_report_path": "...",
    "cache_mode": "used|missed|stale_but_ignored|refreshed|bypassed",
    "fallback_policy": "refresh|bypass"
  },
  "output_paths": {
    "findings_path": ".../findings.json",
    "verifier_evidence_path": ".../verifier-evidence.json",
    "gemini_raw_path": ".../gemini-raw.json",
    "gemini_report_path": ".../gemini-report.json",
    "spawn_decision_path": ".../verifier-spawn-decision.json"
  }
}
```

## Sequence

1. Determine:
- `review_phase`
- `review_pass_type`
- whether the step is artifact entry, implementation working review, or
  implementation challenger review

2. Derive the primary review surface:
- artifact review: changed `proposal/specs/design/tasks`
- implementation review: changed code, changed tests, directly impacted code,
  approved artifacts as reference, optional cache hints

3. Decide whether the next pass needs a newly spawned agent session.
- artifact review normally uses one working reviewer spawn
- initial implementation working review requires a verifier spawn
- challenger passes require a fresh verifier spawn
- same-session implementation reruns MUST reuse the active working verifier
  session unless an exception record explicitly allows a new spawn

4. When a new verifier or index-maintainer session will be spawned, write
   `agent-spawn-decision-v1` before spawning.

5. Decide whether repository-index cache helper work is useful.
- artifact review normally bypasses cache
- implementation review MAY use cache discovery or refresh
- missing cache MUST NOT block implementation review
- stale cache MAY be ignored

6. When cache helper work runs, treat its report as optional support evidence.
- do not treat it as an authoritative frozen review surface
- do not require it before implementation review can continue

7. Validate entry constraints before verification:
- `findings_contract` is `shared-findings-v1`
- `mode` matches `review_phase`
- `review_pass_type` is `working|challenger`

8. Invoke `verify-reviewer` via built-in subagent API with template
   `verify-reviewer-inline-v2`.

9. Require verifier artifacts for this iteration:
- findings JSON exists
- execution evidence JSON exists

10. Validate execution evidence:
- required Stage A fields exist
- `closure_authority=challenger_confirmed` appears only on a challenger pass
- implementation passes include `review_scope` and `review_coverage`
- `skip_reasons` exist when `skipped_paths` is non-empty
- partial or early-stopped passes remain non-authoritative

11. Validate findings JSON against `shared-findings-v1`.

12. Optional second-opinion policy:
- Gemini is never a mandatory Stage A gate by default
- repositories MAY opt into Gemini as a secondary review only on challenger
  passes or other explicitly dual-gated checkpoints
- same-session working reruns MUST NOT pretend Gemini made them authoritative

13. Merge verifier and Gemini findings when both exist, preserving meaningful
    disagreements.

14. Classify findings:
- eligible auto-fix candidate:
  `mode=implementation && blocking=true && redirect_layer=implementation && auto_fixable=true`
- repair-routing blocker:
  any `blocking=true` finding outside the implementation auto-fix gate

15. Artifact outcome rules:
- any blocking artifact finding stops implementation entry
- zero-findings artifact review allows implementation to start
- artifact pass does not require a challenger closure step

16. Implementation outcome rules:
- if repair-routing blockers exist, route to `openspec-repair-change`
- if eligible auto-fix findings exist and no repair-routing blocker exists,
  continue inside the active working session
- when the active working implementation session first returns zero findings,
  spawn a challenger pass
- if the challenger finds new issues, that challenger result becomes the new
  active working baseline

17. Stop only when:
- artifact review passes with authoritative working evidence, or
- implementation challenger pass returns zero findings with
  `closure_authority=challenger_confirmed`

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
- use only when repository policy explicitly enables Gemini dual review
- resolved Linux/Windows command is recorded in execution evidence when Gemini
  runs
- missing Gemini output is blocking only for checkpoints that explicitly
  require Gemini

## Automatic Continuation Policy

Default `ai-enforced-workflow` continuation is automatic unless the caller
explicitly requests `verify-only`, `dry-run`, or `manual_pause`.

Automatic phase chaining rules:
- successful artifact review hands off directly to `openspec-apply-change`
- successful implementation challenger review returns to the active caller flow
  automatically
