## Gemini Verification Exercise Log

Date: 2026-03-18
Change: `add-gemini-independent-verify-to-ai-enforced-workflow`

### 1) CLI smoke tests (`-p`, `-y`, `--approval-mode yolo`, `--output-format json`)

- Command: `gemini -p "Return exactly: SMOKE_P_OK" --output-format text`
  - Result: `SMOKE_P_OK` returned successfully.
- Command: `gemini -y --output-format json -p "Return JSON with field smoke='Y_OK' and nothing else."`
  - Result: success; JSON envelope returned with `response` containing `{"smoke":"Y_OK"}`.
- Command: `gemini --approval-mode yolo --output-format json -p "Return JSON with field smoke='APPROVAL_YOLO_OK' and nothing else."`
  - Result: success; JSON envelope returned with `response` containing `{"smoke":"APPROVAL_YOLO_OK"}`.
- Command: `printf 'STDIN_SEGMENT_TEST' | gemini -y --output-format json -p "Echo whether stdin marker appears..."`
  - Result: success; verifier reported stdin marker was visible in received context.

Smoke-test conclusion:
- `-p` works as headless prompt mode.
- `-y` and `--approval-mode yolo` both enabled auto-approval behavior.
- `--output-format json` works, but payload is wrapped in a top-level envelope (`session_id`, `response`, `stats`).

### 2) `STANDARD` path exercise (mandatory independent implementation verify)

Report written:
- `exercise/reports/gemini/standard-implementation-verify.json`

Command used:
- `gemini -y --output-format json -p "<STANDARD implementation verification prompt with explicit file paths>"`

Observed behavior:
- Independent implementation verification executed successfully and produced findings in JSON envelope format.
- This exercise demonstrates the required independent verification gate artifact can be generated before sync/archive.

### 3) `STRICT` path exercise (independent artifact + implementation verify + rerun)

Reports written:
- `exercise/reports/gemini/strict-artifact-verify.json`
- `exercise/reports/gemini/strict-implementation-verify.json`
- `exercise/reports/gemini/strict-artifact-rerun-clean.json`

Commands used:
- `gemini -y --output-format json -p "<STRICT artifact verification prompt with proposal/specs/design/tasks paths>"`
- `gemini --approval-mode yolo --output-format json -p "<STRICT implementation verification prompt with spec/skill paths>"`
- `gemini -y --output-format json -p "<STRICT rerun prompt referencing prior report path and current artifact paths>"`

Observed behavior:
- Artifact-side strict verification produced a blocked outcome with actionable findings.
- Implementation-side strict verification produced structured validation output.
- Rerun command produced a rerun plan/findings payload, demonstrating post-repair rerun mechanics.

### 4) Caveats and fallback expectations

Observed caveats:
- JSON mode output is an envelope; machine consumers must parse `response` payload (which can include markdown fenced JSON).
- stdin is appended into prompt context, not treated as a separate strongly-typed input channel.
- Transient quota throttling/retry messages occurred during some runs; retries later succeeded.
- Some prompts had high latency (multi-request traces in `stats`).

Fallback expectations for governed gates:
- If Gemini invocation fails, retry with the same path-based prompt and explicit report path.
- If output is non-JSON or malformed, treat gate as not satisfied and rerun with a stricter prompt.
- For `STANDARD`/`STRICT`, do not proceed to sync/archive without a skill-mediated independent verification report artifact.
- Preserve prior report path and rerun report path to support repair-loop provenance.

### 5) Post-fix recheck

After addressing the artifact-level findings (missing risk tier, missing independent verification plan, and missing verifier-property details in Section 4 tasks), a focused strict recheck was run:

- `exercise/reports/gemini/strict-artifact-verify-postfix-fast.json`

Result:
- Assessment: `PASSED`
- Confirmed presence of:
  - `Risk Tier: STRICT` in proposal
  - `Independent Verification Plan (STANDARD/STRICT)` in design
  - verifier source/mode/format/report path/fallback/skill fields in tasks 4.2/4.3

### 6) Report contract normalization fix

A follow-up review found that some generated Gemini envelope reports were not stable machine-consumable artifacts for repair-loop reuse. To restore a stable provenance chain:

- Replaced active report files with normalized JSON contracts:
  - `exercise/reports/gemini/standard-implementation-verify.json`
  - `exercise/reports/gemini/strict-artifact-verify.json`
  - `exercise/reports/gemini/strict-implementation-verify.json`
  - `exercise/reports/gemini/strict-artifact-rerun-clean.json`
- Preserved previous envelope outputs for audit-only traceability:
  - `exercise/reports/gemini/standard-implementation-verify.legacy-envelope.json`
  - `exercise/reports/gemini/strict-artifact-verify.legacy-envelope.json`
  - `exercise/reports/gemini/strict-implementation-verify.legacy-envelope.json`
  - `exercise/reports/gemini/strict-artifact-rerun-clean.legacy-envelope.json`

Post-fix status:
- Active STRICT gate reports now point to design/task-declared report paths and contain machine-consumable JSON fields needed by repair-loop routing and provenance tracking.

### 7) Agent/Codex skill parity closure

The previously noted warning about `.agent/skills` vs `.codex/skills` divergence was resolved by syncing the updated verify/repair skills across both locations:

- `.agent/skills/openspec-artifact-verify/SKILL.md` == `.codex/skills/openspec-artifact-verify/SKILL.md`
- `.agent/skills/openspec-repair-change/SKILL.md` == `.codex/skills/openspec-repair-change/SKILL.md`
- `.agent/skills/openspec-verify-change/SKILL.md` == `.codex/skills/openspec-verify-change/SKILL.md`

Result:
- `strict-implementation-verify.json` assessment is now `pass` (warning cleared).
