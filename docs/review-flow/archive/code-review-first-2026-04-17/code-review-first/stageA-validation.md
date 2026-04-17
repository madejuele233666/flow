# Stage A Validation

## Scope

Validation for the no-change Stage A direct rollout documented in:
- `docs/code-review-first/stageA-direct-rollout.md`

Authority references:
- `docs/code-review-first/01-principles-and-boundaries.md`
- `docs/code-review-first/03-layer-1-core-review-loop.md`
- `docs/code-review-first/04-layer-2-lightweight-scope-summary.md`
- `docs/code-review-first/08-migration-validation-and-stop-rules.md`

## Mechanical Checks

Validator entrypoint:
- `openspec/bin/stagea_direct_rollout_validate.py`

Validated:
- YAML / JSON / TOML syntax for:
  - `openspec/schemas/ai-enforced-workflow/schema.yaml`
  - `openspec/schemas/ai-enforced-workflow/agent-spawn-decision-v1.schema.json`
  - `.codex/agents/verify-reviewer.toml`
  - `.codex/agents/index-maintainer.toml`
- Stage A contract tokens across the rollout scope:
  - direct rollout doc
  - verify-subagent spec
  - shared sequences
  - schema
  - templates
  - both agents
  - six Stage A skills
- Forbidden legacy verifier lifecycle terms removed from current Stage A
  contracts:
  - `fresh_confirmation`
  - `policy_requires_fresh_confirmation`
  - `fresh-confirmation`
- Blocking cache fallback removed from current Stage A cache-helper contract:
  - no `refresh|bypass|block` remains in current Stage A surfaces

Result:
- `Stage A validation passed.`

## Independent Reviewer Loop

Reviewer:
- `verify-reviewer`

Review change id used for direct rollout evidence:
- `stageA-direct-rollout`

Rerun policy used:
- reuse the same verifier session until convergence
- do not open a second verifier before rerun completion

Rerun summary:
1. Initial review returned three blocking findings:
   - legacy `fresh_confirmation` lifecycle still present
   - cache helper still allowed blocking fallback
   - no supported no-change validation entrypoint existed
2. Follow-up patches:
   - reduced spawn-decision contract to `working` and `challenger`
   - removed blocking cache fallback from Stage A cache-helper surfaces
   - added `openspec/bin/stagea_direct_rollout_validate.py`
   - wired the rollout doc to the direct validation entrypoint
3. First rerun returned one warning:
   - validator coverage was narrower than the documented rollout scope
4. Final patch:
   - extended validator coverage to the full Stage A rollout scope
5. Final rerun result:
   - `final_assessment=pass`
   - `findings=[]`

## Completion Check

Validated outcomes:
- artifact review and implementation review are explicitly separated
- repo-index is cache helper only
- implementation review can degrade to source-first review
- implementation closure authority belongs only to challenger pass
- implementation evidence carries inline `review_scope` and `review_coverage`
- no standalone planner artifact, planner schema, or planner agent was added
