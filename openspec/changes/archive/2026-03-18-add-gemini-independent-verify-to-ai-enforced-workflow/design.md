## Context

`ai-enforced-workflow` currently requires verification gates, but it does not require those gates to be executed by a reviewer that is independent from the authoring AI. That leaves a predictable blind spot: the same model can produce artifacts or code, then rationalize them during verification.

The repository already has the surrounding workflow pieces:

- `ai-enforced-workflow` defines phase gates and risk-tiered behavior
- `artifact-verification` defines pre-implementation review
- `change-repair-loop` defines how findings route back upstream
- `openspec-artifact-verify`, `openspec-verify-change`, and `openspec-repair-change` consume and produce structured findings

The missing piece is an explicit contract for independent verification. Based on direct CLI tests in this repository, the current Gemini CLI supports the mechanics needed for that role:

- `-p` is the explicit headless flag and avoids TUI mode
- `-y` and `--approval-mode yolo` are valid approval controls
- `--output-format json` returns machine-consumable `response` and `stats`
- stdin is appended to the prompt rather than treated as an isolated payload, so path-based inputs are more reliable than piping large artifact blobs

That independent verification cannot be modeled as a bare CLI side path. To stay governable, Gemini review has to run through the related OpenSpec skills so the workflow preserves context loading, findings normalization, redirect layers, and repair routing.

## Goals / Non-Goals

**Goals:**
- Add an explicit independent verifier gate to the workflow semantics instead of treating second-model review as an informal habit
- Make Gemini CLI the default verifier implementation without hard-coding it as the only future option
- Define how `LIGHT`, `STANDARD`, and `STRICT` tiers escalate independent verification requirements
- Extend findings contracts so repair and re-verification preserve verifier provenance
- Require design and task artifacts to name the verifier command path, report format, and fallback behavior
- Require design and task artifacts to name which related skill invokes or consumes each Gemini verification step

**Non-Goals:**
- Rebuild OpenSpec CLI to automatically orchestrate Gemini executions
- Replace existing verify skills with a brand-new workflow phase name
- Standardize all model invocation in the repository around Gemini CLI

## Decisions

### Decision 1: Model the change as an independent verifier gate orchestrated by the existing skills

The workflow will define a new requirement around independent verification semantics. Gemini CLI is the default executor for that gate, but the contract lives at the workflow level as "independent verifier required through the related OpenSpec skills", not merely "run this exact command".

This keeps the workflow focused on review independence while still giving the implementation a concrete default. It also avoids rewriting the workflow contract if the project later switches from CLI execution to an equivalent API-backed wrapper, while preserving the existing skill boundaries for artifact verify, implementation verify, and repair.

Alternatives considered:
- Hard-code Gemini CLI directly into every requirement
- Leave the workflow unchanged and only update skill prose
- Allow direct Gemini CLI reports outside the skill system

Gemini-only wording was rejected because it overfits the current tool choice. Skill-only wording was rejected because it would not make independent review a governed phase gate.
Direct standalone reports were rejected because they bypass findings normalization and break repair-loop routing.

### Decision 2: Use risk tiers to control where Gemini-based independent review is mandatory

The workflow will escalate independent review according to risk:

- `LIGHT`: independent verification is optional
- `STANDARD`: independent implementation verification is mandatory before sync or archive
- `STRICT`: independent artifact review and independent implementation verification are both mandatory

This keeps the blind-spot mitigation where it matters most without forcing trivial changes through the heaviest possible review path.

Alternatives considered:
- Require Gemini review for every change
- Require Gemini only for final implementation verify

Requiring it everywhere was rejected because it adds unnecessary cost to low-risk work. Requiring it only at the end was rejected because `STRICT` changes can still drift at the artifact layer long before code exists.

### Decision 3: Standardize the verifier invocation contract around headless JSON output and path-based inputs

The default verifier invocation will use Gemini CLI in headless structured-output mode:

```bash
gemini -y --output-format json -p "<verification prompt>"
```

The workflow will treat this as a command contract for the default executor and require tasks to name the skill that invokes or consumes the report plus the report artifact that captures the result.

The design will explicitly prefer path-based inputs such as change names, artifact paths, and report files over large stdin pipelines. In local tests, stdin content was appended to the prompt rather than processed as an isolated payload, which makes strict scripted analysis less predictable than file-driven review prompts.

Alternatives considered:
- Use plain text output and parse markdown heuristically
- Feed entire artifacts through stdin pipelines

Plain text was rejected because repair needs stable, machine-consumable findings. Stdin-heavy prompting was rejected because the observed CLI behavior is less deterministic for scriptable workflow gates. Direct CLI usage without skills was rejected because it bypasses the workflow's structured findings contract.

### Decision 4: Extend findings with verifier provenance instead of treating all reports as equivalent

Independent review only adds value if downstream repair can tell who produced each finding. The shared findings model will therefore preserve verifier provenance, at minimum:

- verifier source
- execution method
- report identity or source report reference

This provenance will be required for artifact verification outputs and preserved by repair planning so re-verification can compare self-review and independent-review results without collapsing them into one undifferentiated list.

Alternatives considered:
- Keep the existing findings shape and attach Gemini output as free text
- Store provenance only in report headers, not per finding

Free-text attachment was rejected because repair cannot consume it reliably. Report-level provenance only was rejected because mixed findings from multiple reviewers become hard to normalize.

## Independent Verification Plan (STANDARD/STRICT)

This change is `STRICT`, so both independent artifact verification and independent implementation verification are required.

### Step A: Independent Artifact Verification

- Verifier source: `gemini-cli`
- Invocation mode: headless prompt via `openspec-artifact-verify`
- Output format: JSON envelope with machine-consumable findings payload
- Report path: `openspec/changes/add-gemini-independent-verify-to-ai-enforced-workflow/exercise/reports/gemini/strict-artifact-verify.json`
- Skill entry point: `openspec-artifact-verify`
- Fallback behavior:
  - Retry once with the same path-based prompt if CLI execution fails transiently.
  - If output is malformed/non-JSON, rerun with stricter JSON-only prompt.
  - Treat unresolved failures as blocking for `STRICT`.

### Step B: Independent Implementation Verification

- Verifier source: `gemini-cli`
- Invocation mode: headless prompt via `openspec-verify-change`
- Output format: JSON envelope with normalized findings payload
- Report path: `openspec/changes/add-gemini-independent-verify-to-ai-enforced-workflow/exercise/reports/gemini/strict-implementation-verify.json`
- Skill entry point: `openspec-verify-change`
- Fallback behavior:
  - Retry with explicit file-path scope if initial prompt is too broad.
  - If response is not consumable, rerun and require structured fields before proceeding.
  - Do not allow archive progression without this report for `STRICT`.

### Step C: Post-Repair Independent Rerun

- Verifier source: `gemini-cli`
- Invocation mode: headless prompt driven by `openspec-repair-change` rerun plan
- Output format: JSON envelope with rerun plan and findings
- Report path: `openspec/changes/add-gemini-independent-verify-to-ai-enforced-workflow/exercise/reports/gemini/strict-artifact-rerun-clean.json`
- Skill entry point: `openspec-repair-change` coordinating `openspec-artifact-verify` / `openspec-verify-change`
- Fallback behavior:
  - Preserve source report and rerun report paths for provenance.
  - If rerun cannot be produced, keep gate blocked and rerun required verifier path.

## Risks / Trade-offs

- [Risk] Gemini CLI behavior may drift across versions and change output details.
  Mitigation: anchor the contract on tested flags (`-p`, `-y`, `--output-format json`) and require fallback behavior in design/tasks.

- [Risk] Independent review can become ceremonial if prompts are vague or reports are not consumed by repair.
  Mitigation: require machine-consumable outputs and route Gemini findings through the same structured repair model as other verify stages.

- [Risk] `LIGHT` changes may skip Gemini review and still miss issues.
  Mitigation: preserve the option to invoke independent review voluntarily and reserve strict blocking behavior for higher-risk tiers.

- [Risk] Headless CLI execution with `-y` could approve more tool access than a narrowly scoped review needs.
  Mitigation: constrain prompts to explicit paths and verification tasks, and require the design to name fallback or exception handling for environments where full approval is not acceptable.

## Migration Plan

1. Update the workflow-related specs to define independent verification gates, Gemini-as-default execution details, and findings provenance.
2. Update `openspec/schemas/ai-enforced-workflow/schema.yaml` and related templates so design/tasks must name the verifier command, the related skill hook, the report output, and fallback behavior.
3. Update `openspec-artifact-verify`, `openspec-verify-change`, and `openspec-repair-change` so they are the mandatory path for producing and consuming Gemini-backed findings without losing routing information.
4. Exercise the new rules with a test change that demonstrates `STANDARD` and `STRICT` verification paths.

## Open Questions

- Should the workflow require a fixed report filename convention for Gemini outputs, or only require that the path be named explicitly in tasks?
- For `STANDARD` changes, should a failed Gemini execution block archive immediately, or allow a user-approved manual retry path first?
- Should artifact verification always consume Gemini JSON directly, or allow a normalized wrapper report generated by another local script?
- Should the workflow require an explicit skill-to-command mapping table in design.md, or is naming the responsible skill in each verification task sufficient?
