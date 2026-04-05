## Why

The current `ai-enforced-workflow` requires verification gates, but it does not require those gates to be executed by an independent model. That leaves a blind spot where the same AI that authored artifacts or code can also verify them, reducing the value of the review loop.

## What Changes

- Modify `ai-enforced-workflow` so governed changes can require an independent verification gate instead of relying only on the originating AI's self-review.
- Define how `LIGHT`, `STANDARD`, and `STRICT` risk tiers escalate the requirement for independent verification, with Gemini CLI as the default verifier implementation for the new gate.
- Update artifact verification and repair-loop contracts so Gemini-produced findings are machine-consumable, attributable to a verifier source, reusable across re-verification, and emitted through the related OpenSpec verify/repair skills rather than ad hoc standalone CLI usage.
- Require workflow design and task artifacts to name the verification executor, fallback behavior, and verification report outputs instead of treating Gemini verification as an informal manual step.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `ai-enforced-workflow`: add independent verification gate requirements, risk-tier gating, and workflow documentation requirements for the Gemini-based verify step and its required skill orchestration
- `artifact-verification`: require support for independent verifier execution through the related verify skills and structured findings provenance so artifact review can be consumed by repair
- `change-repair-loop`: extend the shared findings model so repair and re-verification preserve verifier source and independent-review outcomes across skill-mediated review loops

## Risk Tier

`STRICT`

Justification:
- Modifies core workflow gates and blocking rules used across change lifecycle phases.
- Changes verification and repair contracts that affect both artifact and implementation governance.
- Introduces mandatory independent verifier orchestration and provenance requirements that must remain coherent across schema and skills.

## Impact

- Affected specs: `openspec/specs/ai-enforced-workflow/spec.md`, `openspec/specs/artifact-verification/spec.md`, `openspec/specs/change-repair-loop/spec.md`
- Affected workflow guidance and implementation surface: `openspec/schemas/ai-enforced-workflow/schema.yaml`, `.codex/skills/openspec-artifact-verify/SKILL.md`, `.codex/skills/openspec-verify-change/SKILL.md`, `.codex/skills/openspec-repair-change/SKILL.md`
- Operational impact: `Gemini CLI` becomes the default independent verifier for governed verify gates, using headless invocation and structured output through the existing OpenSpec verify and repair skills
