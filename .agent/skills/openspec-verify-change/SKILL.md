---
name: openspec-verify-change
description: Verify implementation matches change artifacts. Use when the user wants to validate that implementation is complete, correct, and coherent before archiving.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

Verify that an implementation matches the change artifacts (specs, tasks, design).

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show changes that have implementation tasks (tasks artifact exists).
   Include the schema used for each change if available.
   Mark changes with incomplete tasks as "(In Progress)".

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand:
   - `schemaName`: The workflow being used (e.g., "spec-driven")
   - Which artifacts exist for this change
   - Risk tier from proposal (`LIGHT` / `STANDARD` / `STRICT`) when available

3. **Get the change directory and load artifacts**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   This returns the change directory and context files. Read all available artifacts from `contextFiles`.

4. **Initialize verification report structure**

   Create a report structure with three dimensions:
   - **Completeness**: Track tasks and spec coverage
   - **Correctness**: Track requirement implementation and scenario coverage
   - **Coherence**: Track design adherence and pattern consistency

   Each dimension can have CRITICAL, WARNING, or SUGGESTION issues.

   Add verifier provenance support fields for findings produced via independent verification:
   - `verifier_provenance.source`
   - `verifier_provenance.execution_method`
   - `verifier_provenance.invocation_mode`
   - `verifier_provenance.output_format`
   - `verifier_provenance.report_path`

5. **Verify Completeness**

   **Task Completion**:
   - If tasks.md exists in contextFiles, read it
   - Parse checkboxes: `- [ ]` (incomplete) vs `- [x]` (complete)
   - Count complete vs total tasks
   - If incomplete tasks exist:
     - Add CRITICAL issue for each incomplete task
     - Recommendation: "Complete task: <description>" or "Mark as done if already implemented"

   **Spec Coverage**:
   - If delta specs exist in `openspec/changes/<name>/specs/`:
     - Extract all requirements (marked with "### Requirement:")
     - For each requirement:
       - Search codebase for keywords related to the requirement
       - Assess if implementation likely exists
     - If requirements appear unimplemented:
       - Add CRITICAL issue: "Requirement not found: <requirement name>"
       - Recommendation: "Implement requirement X: <description>"

6. **Verify Correctness**

   **Requirement Implementation Mapping**:
   - For each requirement from delta specs:
     - Search codebase for implementation evidence
     - If found, note file paths and line ranges
     - Assess if implementation matches requirement intent
     - If divergence detected:
       - Add WARNING: "Implementation may diverge from spec: <details>"
       - Recommendation: "Review <file>:<lines> against requirement X"

   **Scenario Coverage**:
   - For each scenario in delta specs (marked with "#### Scenario:"):
     - Check if conditions are handled in code
     - Check if tests exist covering the scenario
     - If scenario appears uncovered:
       - Add WARNING: "Scenario not covered: <scenario name>"
       - Recommendation: "Add test or implementation for scenario: <description>"

7. **Verify Coherence**

   **Design Adherence**:
   - If design.md exists in contextFiles:
     - Extract key decisions (look for sections like "Decision:", "Approach:", "Architecture:")
     - Verify implementation follows those decisions
     - If contradiction detected:
       - Add WARNING: "Design decision not followed: <decision>"
       - Recommendation: "Update implementation or revise design.md to match reality"
   - If no design.md: Skip design adherence check, note "No design.md to verify against"

   **Code Pattern Consistency**:
   - Review new code for consistency with project patterns
   - Check file naming, directory structure, coding style
   - If significant deviations found:
     - Add SUGGESTION: "Code pattern deviation: <details>"
     - Recommendation: "Consider following project pattern: <example>"

8. **Generate Verification Report**

   **Summary Scorecard**:
   ```
   ## Verification Report: <change-name>

   ### Summary
   | Dimension    | Status           |
   |--------------|------------------|
   | Completeness | X/Y tasks, N reqs|
   | Correctness  | M/N reqs covered |
   | Coherence    | Followed/Issues  |
   ```

   **Issues by Priority**:

   1. **CRITICAL** (Must fix before archive):
      - Incomplete tasks
      - Missing requirement implementations
      - Each with specific, actionable recommendation

   2. **WARNING** (Should fix):
      - Spec/design divergences
      - Missing scenario coverage
      - Each with specific recommendation

   3. **SUGGESTION** (Nice to fix):
      - Pattern inconsistencies
      - Minor improvements
      - Each with specific recommendation

   **Interim Assessment (before independent gate)**:
   - If CRITICAL issues: "X critical issue(s) found. Fix before independent verify and archive."
   - If only warnings: "No critical issues in baseline checks. Continue to independent verify gate."
   - If all clear: "Baseline checks passed. Continue to independent verify gate."

9. **Run required independent implementation verification gate**

   For governed risk tiers:
   - `LIGHT`: independent implementation verification is optional
   - `STANDARD`: independent implementation verification is mandatory before sync/archive
   - `STRICT`: independent implementation verification is mandatory before sync/archive

   This skill is the mandatory entry point for implementation-side independent verification. Do not accept standalone Gemini reports that bypass this skill.

   Default Gemini CLI command contract:

   ```bash
   gemini -y --output-format json -p "Review implementation for change <name> using specs under <change-dir>/specs, tasks at <change-dir>/tasks.md, and relevant code paths. Return structured findings with severity, dimension, artifact, problem, evidence, recommendation, redirect_layer, blocking, and verifier_provenance."
   ```

   Optional approval-mode variant:

   ```bash
   gemini --approval-mode yolo --output-format json -p "Verify implementation for <name> against change artifacts in <change-dir>. Output JSON findings only."
   ```

   Path-based prompt guidance:
   - Prefer explicit file and directory paths in prompts
   - Avoid piping large artifact bodies via stdin
   - Read the planned report path from change artifacts (`tasks.md` or `design.md`) and persist output there for repair-loop reuse

   Example report snippet to preserve:

   ```json
   {
     "change": "example-change",
     "assessment": "pass_with_warnings",
     "findings": [
       {
         "id": "IV-014",
         "severity": "WARNING",
         "dimension": "Correctness",
         "artifact": "implementation",
         "problem": "Scenario edge path appears untested.",
         "evidence": "No test found for scenario 'retry after verifier timeout'.",
         "recommendation": "Add scenario test and rerun verify.",
         "redirect_layer": "implementation",
         "blocking": false,
         "verifier_provenance": {
           "source": "gemini-cli",
           "execution_method": "skill-mediated-cli",
           "invocation_mode": "headless-prompt",
           "output_format": "json",
           "report_path": "reports/gemini/implementation-verify.json"
         }
       }
     ]
   }
   ```

10. **Generate final assessment after independent gate**

   Merge baseline checks and independent verifier results into final status:
   - If any blocking finding exists in either stage: "Blocked. Repair required before archive."
   - If no blocking findings but warnings exist: "Pass with warnings. Archive allowed with noted follow-ups."
   - If all checks clear: "Pass. Ready for archive."

**Verification Heuristics**

- **Completeness**: Focus on objective checklist items (checkboxes, requirements list)
- **Correctness**: Use keyword search, file path analysis, reasonable inference - don't require perfect certainty
- **Coherence**: Look for glaring inconsistencies, don't nitpick style
- **False Positives**: When uncertain, prefer SUGGESTION over WARNING, WARNING over CRITICAL
- **Actionability**: Every issue must have a specific recommendation with file/line references where applicable

**Graceful Degradation**

- If only tasks.md exists: verify task completion only, skip spec/design checks
- If tasks + specs exist: verify completeness and correctness, skip design
- If full artifacts: verify all three dimensions
- Always note which checks were skipped and why

**Output Format**

Use clear markdown with:
- Table for summary scorecard
- Grouped lists for issues (CRITICAL/WARNING/SUGGESTION)
- Code references in format: `file.ts:123`
- Specific, actionable recommendations
- No vague suggestions like "consider reviewing"
- For independent verification findings, include `verifier_provenance` fields
