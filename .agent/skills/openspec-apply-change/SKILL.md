---
name: openspec-apply-change
description: Implement tasks from an OpenSpec change. Use when the user wants to start implementing, continue implementation, or work through tasks.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.2"
  generatedBy: "1.2.0"
---

Implement tasks from an OpenSpec change.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` to get available changes and ask the user to choose

   Always announce: "Using change: <name>" and how to override.

2. **Check status to understand the schema**

   ```bash
   openspec status --change "<name>" --json
   ```

   Parse the JSON to understand:
   - `schemaName`: the workflow being used
   - which artifact contains the tasks

   If `schemaName = "ai-enforced-workflow"`:
   - treat passing artifact verification as a hard precondition to implementation
   - if there is no current passing artifact gate for the active artifact state in this flow, invoke `openspec-artifact-verify` automatically before starting task execution
   - if artifact verification blocks, route to `openspec-repair-change`, let repair rerun artifact verification automatically, and resume apply only after the artifact gate passes

3. **Get apply instructions**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   This returns:
   - context file paths
   - progress
   - task list with status
   - dynamic instruction based on current state

   Handle states:
   - If `state: "blocked"`: show message and suggest using `openspec-continue-change`
   - If `state: "all_done"`: report completion and suggest archive
   - Otherwise: proceed to implementation

4. **Read context files**

   Read the files listed in `contextFiles` from the apply instructions output.

5. **Show current progress**

   Display:
   - schema being used
   - progress
   - remaining tasks overview
   - dynamic instruction from CLI

6. **Implement tasks (loop until done or blocked)**

   For each pending task:
   - show which task is being worked on
   - make the code or document changes required
   - keep changes minimal and focused
   - if the task is a verification or checkpoint task in `ai-enforced-workflow`, execute shared verification sequence `verify-sequence/default`, invoke read-only verifier-subagent review via built-in subagent API organized by template `verify-reviewer-inline-v1`, and write authoritative verifier-subagent findings JSON plus execution evidence JSON
   - require `findings_contract=shared-findings-v1`; block if the contract identifier is missing or unsupported
   - validate verifier-subagent findings JSON contract before using findings; malformed or contract-violating verifier output is an immediate blocker (at least: `id` uniqueness, stable `id` across consecutive reruns for unchanged unresolved findings, `auto_fixable`/`redirect_layer` constraints, and `SUGGESTION => blocking=false`)
   - use verifier runtime profile from `.codex/agents/verify-reviewer.toml`
   - require execution evidence JSON with `agent_id/start_at/end_at/final_state`; missing provenance is an immediate blocker even if a markdown summary exists
   - every verify rerun MUST use a fresh verifier instance; do not inherit prior verifier memory
   - run Gemini second opinion only when risk tier or checkpoint policy requires it; when Gemini runs, write both raw and normalized reports
   - if Gemini primary run fails after writing the raw envelope but before producing the normalized report, run Gemini runner recovery (`input_raw_path` -> `report_path`) before pausing
   - when Gemini runs, record the resolved Linux/Windows command in execution evidence or logs
   - when normalized findings return, allow automatic implementation repair only for blocking findings where `mode=implementation && redirect_layer=implementation && auto_fixable=true`
   - if any blocking finding is outside the implementation auto-fix gate, stop auto-fix loop and route to `openspec-repair-change`
   - policy-acceptable non-blocking warnings/suggestions may terminate verification without repair routing unless checkpoint policy marks them must-fix
   - maintain separate retry counters:
     - artifact verification reruns (`artifact_rerun_budget`)
     - implementation auto-fix loops (`implementation_auto_fix_budget`)
   - do not spend implementation auto-fix budget on artifact reruns, and do not spend artifact rerun budget on implementation auto-fix loops
   - if the same blocking finding repeats after an implementation auto-fix attempt (`id` + `redirect_layer`), stop auto-fix loop and route to `openspec-repair-change`
   - if the verification outcome is blocked or routed to `openspec-repair-change`, do not mark the task complete; route into repair and resume automatically unless `verify-only`, `dry-run`, or `manual_pause` is explicitly set
   - otherwise mark task complete in the tasks file: `- [ ]` -> `- [x]`
   - continue to the next task

   After all pending tasks are complete:
   - if `schemaName = "ai-enforced-workflow"`, invoke `openspec-verify-change` automatically for the same change
   - if implementation verification returns eligible automatic implementation fixes, apply them and rerun verification automatically within `implementation_auto_fix_budget`
   - if implementation verification routes to `openspec-repair-change`, let repair rerun the required verification automatically and then resume the apply/verify chain
   - stop only when verification reaches pass, policy-acceptable warnings, an upstream repair blocker, or retry-budget exhaustion

   Pause if:
   - the task is unclear
   - implementation reveals a design issue
   - an error or blocker is encountered
   - the user interrupts

7. **On completion or pause, show status**

   Display:
   - tasks completed this session
   - overall progress
   - if all done and post-implementation verification passed: suggest archive
   - if paused: explain why and wait for guidance

## Guardrails

- Keep going through tasks until done or blocked
- For `ai-enforced-workflow`, do not start implementation before a passing artifact verify gate for the current artifact state
- Always read context files before starting
- If a task is ambiguous, pause and ask before implementing
- If implementation reveals issues, pause and suggest artifact updates
- Keep changes minimal and scoped to each task
- Update the task checkbox immediately after completing each task
- Pause on errors, blockers, or unclear requirements
- Use `contextFiles` from CLI output, do not assume specific file names
- Do not substitute user confirmation for a required verification stage
- Do not skip verifier-subagent review before a required Gemini second-opinion stage
- Do not stop at the first Gemini runner failure if raw-envelope recovery is still available
- Do not auto-fix any finding unless `mode=implementation && redirect_layer=implementation && auto_fixable=true`
- Track artifact rerun and implementation auto-fix budgets independently
- Ensure each verify/fix iteration spawns a fresh verifier instance (no inherited verifier memory)
- Do not require the user to manually invoke `/opsx:verify` after apply for `ai-enforced-workflow`; completion verification and eligible reruns are part of the same automatic flow
- Do not accept a hand-written "local review" markdown file as proof that verifier-subagent review occurred

## Fluid Workflow Integration

This skill supports the "actions on a change" model:
- Can be invoked anytime if tasks exist
- Allows artifact updates when implementation reveals design issues
- For `ai-enforced-workflow`, automatically chains `artifact-verify -> apply -> verify -> rerun/repair` unless the caller explicitly requests `verify-only`, `dry-run`, or `manual_pause`
