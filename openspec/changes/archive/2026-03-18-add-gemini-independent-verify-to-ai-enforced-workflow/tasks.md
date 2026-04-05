## 1. Update workflow contracts

- [x] 1.1 Update `openspec/specs/ai-enforced-workflow/spec.md` to require independent verification gates, risk-tier escalation, artifact/task-level verifier planning details, and the related skill orchestration for Gemini verify
- [x] 1.2 Update `openspec/specs/artifact-verification/spec.md` to require Gemini-backed independent artifact review support through `openspec-artifact-verify` and repairable verifier provenance
- [x] 1.3 Update `openspec/specs/change-repair-loop/spec.md` to preserve verifier provenance and rerun required independent verifier gates after repair through `openspec-repair-change`
- [x] 1.4 【检查点】 Present the workflow-spec delta and verifier-provenance model to the user. MUST obtain explicit user confirmation before proceeding to schema and skill updates.

## 2. Update ai-enforced-workflow schema and templates

- [x] 2.1 Update `openspec/schemas/ai-enforced-workflow/schema.yaml` so risk-tier instructions require independent verification planning for `STANDARD` and `STRICT` changes
- [x] 2.2 Update `openspec/schemas/ai-enforced-workflow/schema.yaml` design/task instructions to require verifier source, invocation mode, output format, report path, fallback behavior, and the related skill entry point for each Gemini verify step
- [x] 2.3 Update `openspec/schemas/ai-enforced-workflow/templates/design.md` and related templates as needed so the default Gemini verify contract can be documented without ad hoc prose
- [x] 2.4 【检查点】 Present the schema diff and template changes to the user. MUST obtain explicit user confirmation before proceeding to skill changes.

## 3. Update verify and repair skills

- [x] 3.1 Update `.codex/skills/openspec-artifact-verify/SKILL.md` so artifact review can run or consume Gemini CLI independent verification in structured form and remains the mandatory entry point for artifact-side Gemini verify
- [x] 3.2 Update `.codex/skills/openspec-verify-change/SKILL.md` so implementation verify uses the default Gemini CLI command contract for required independent review gates and remains the mandatory entry point for implementation-side Gemini verify
- [x] 3.3 Update `.codex/skills/openspec-repair-change/SKILL.md` so repair planning preserves verifier provenance and reruns the correct independent verifier after repair instead of accepting standalone Gemini reports outside the skill loop
- [x] 3.4 Add concrete report examples or command examples showing `gemini -y --output-format json -p "<prompt>"` with path-based review inputs rather than stdin-heavy prompts
- [x] 3.5 【检查点】 Present the skill updates and sample verification report shape to the user. MUST obtain explicit user confirmation before proceeding to workflow exercises.

## 4. Exercise the verification paths

- [x] 4.1 Run Gemini CLI smoke tests that confirm `-p`, `-y`, `--approval-mode yolo`, and `--output-format json` behave as expected for local review prompts
- [x] 4.2 Exercise a `STANDARD` change path showing mandatory independent implementation verification before sync or archive (`verifier_source=gemini-cli`, `invocation_mode=headless -p`, `output_format=json`, `report_path=openspec/changes/add-gemini-independent-verify-to-ai-enforced-workflow/exercise/reports/gemini/standard-implementation-verify.json`, `fallback=retry then block`, `skill=openspec-verify-change`)
- [x] 4.3 Exercise a `STRICT` change path showing independent artifact review and independent implementation verification, plus rerun behavior after repair (`verifier_source=gemini-cli`, `invocation_mode=headless -p`, `output_format=json`, `report_path` under `exercise/reports/gemini/strict-*.json`, `fallback=retry then block`, `skills=openspec-artifact-verify + openspec-verify-change + openspec-repair-change`)
- [x] 4.4 Record the exercise log and any unresolved CLI caveats, including stdin limitations and fallback expectations, with preserved source/rerun report paths for provenance
- [x] 4.5 【检查点】 Present the exercise log and residual risks to the user. MUST obtain explicit user confirmation before proceeding to archive or further rollout.
