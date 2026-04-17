# Transition Resolver Execution Plan

## Purpose

This document records the full optimization agenda discussed for the review
workflow, but it is intentionally **not** an OpenSpec change.

It borrows a change-like structure so the work can be executed cleanly without
creating a self-referential `openspec/changes/...` entry about the workflow
that governs changes.

Use this file as the execution brief for:

- `openspec/schemas/ai-enforced-workflow`
- `openspec/schemas/modules/review-loop`
- schema-independent review usage under `docs/review-flow`

## Current Problem

The main process still has too much room to improvise orchestration decisions.
That causes failures such as:

- treating main-process self-judgment as if it were sub-agent pass evidence
- opening a fresh challenger before a recorded working-pass prerequisite exists
- using a fresh working session for ordinary reruns
- stopping after writing `spawn-decision.json` instead of continuing into review
- falling back to shell/`exec` even when built-in subagent invocation should be
  used
- over-modeling review state with prompt prose and ad hoc field interpretation

The reviewer sub-agent is not the root problem. The main process is.

## Goal

Move orchestration authority out of prompt interpretation and into a reusable
transition resolver layer that can be shared by schema and non-schema flows.

The resolver may be implemented with:

- Python
- command-line tooling
- machine-readable transition tables
- guard/validator programs
- a small module API

Implementation form is flexible. Authority boundaries are not.

## Hard Requirements

The resolver design must preserve these invariants:

1. Ordinary repair reruns stay in the same `working` session.
2. `challenger` must always use a fresh session.
3. Only `challenger` can grant final closure.
4. A new `challenger` may start only after the previous sub-agent explicitly
   recorded pass, and that record includes the prior sub-agent `agent_id`.
5. The main process must not treat "I checked and it looks fine" as equivalent
   to "the prior sub-agent passed".
6. Writing `spawn-decision.json` is preparatory only; review must continue in
   the same turn unless the caller explicitly requested `dry-run` or
   `manual_pause`.
7. When reviewer sub-agents are required, built-in subagent invocation is the
   default path; shell/`exec` is not the normal substitute.
8. Verifier reviewer spawns must use `fork_context=false` and receive only the
   minimal verification bundle, optional cache context, and output paths.
9. Schema and non-schema callers must share the same review-loop semantics.
10. The shared module must model one thing: implementation correctness review.
    `artifact` and `implementation` are not separate semantic species.

## Non-Goals

- Do not move reviewer semantic judgment into the resolver.
- Do not let cache or repo-index become closure authority.
- Do not create a new OpenSpec change for this document.
- Do not let the resolver arbitrarily edit unrelated files.
- Do not preserve redundant contracts just because they already exist.

## Completed Baseline Decisions

The following changes are already completed and therefore are **not** the
pending tasks of this document. They are baseline constraints that the
transition resolver must inherit.

### Change A: Remove Artifact vs Implementation Semantic Split

The shared review module already models one core workflow:
`implementation_correctness`.

What remains valid:

- callers may still choose `review_phase=docs_first` or
  `review_phase=source_first`
- routing may differ by phase

What is no longer acceptable:

- treating `artifact` and `implementation` as two different shared review-loop
  semantics

### Change B: Move Docs-First Validation Earlier

Docs-first validation already belongs to the caller that completes the
artifact-completion boundary, not to `openspec-apply-change`.

Required baseline behavior:

- `openspec-propose` completes artifact generation
- the workflow then automatically enters docs-first verification
- `openspec-apply-change` must not become the place where artifact quality is
  first repaired

## Current Work Scope

The tasks below are the actual pending work for this document.

They all serve the same three goals:

1. extract shared constraints into machine-readable resolver inputs
2. simplify contracts to the minimum orchestration state that matters
3. mechanically prevent the main process from violating the review workflow

## Priority Plan

### Priority 1

Establish hard transition authority:

- review-loop transition
- session reuse / freshness policy
- closure gate

### Priority 2

Establish hard invocation discipline:

- spawn authorization
- invocation mode selection
- continuation policy

### Priority 3

Establish phase routing consistency:

- docs-first / source-first routing

### Priority 4

Establish sidecar and exception handling:

- cache sidecar routing
- exception routing
- run layout / path coherence

### Priority 5

Expose the resolver as a reusable module that both schema and external callers
can consume without re-encoding the same rules in prompt prose.

## Current Resolver Task List

### 1. Review Loop Transition

来源：

- `openspec/schemas/modules/review-loop/contracts/review-loop-core-v1.json`
- `openspec/schemas/ai-enforced-workflow/verification-sequence.md`
- `openspec/schemas/modules/review-loop/README.md`
- `openspec/schemas/modules/review-loop/VERIFY-IMPLEMENTATION.md`

应接入：

- `review_pass_type=working|challenger`
- `closure_authority`
- `coverage_status`
- `saturation_status`
- `final_assessment`
- `findings=[] / 非空`
- `source_review` 三元绑定
- `challenger_entry.source_review_required`

resolver 输出：

- `send_input same working`
- `resume same working`
- `spawn fresh challenger`
- `record challenger_reopen`
- `close`

### 2. Session Reuse / Freshness Policy

来源：

- 同上
- `spawn-decision`
- `verifier evidence`

应接入：

- 当前 `active_working_agent_id`
- 当前 session 是否 `still open`
- 是否 `resumable`
- 当前 action 是否 ordinary rerun
- 是否 exception path

resolver 输出：

- ordinary rerun 必须 `send_input` / `resume`
- fresh working 只允许 exception
- challenger 必须 fresh

### 3. Spawn Authorization

来源：

- `openspec/schemas/ai-enforced-workflow/verification-sequence.md`
- `openspec/schemas/ai-enforced-workflow/schema.yaml`
- skills 入口

应接入：

- 当前 workflow entrypoint
- 当前是否是 module-root standalone invocation
- 当前是否已提供最小 review bundle
- 当前 step 是否声明 `verify-sequence/default`
- 当前是否 `verify-only|dry-run|manual_pause`
- 授权范围：`reviewer sessions only`

resolver 输出：

- 本步是否允许 `verify-reviewer`
- 授权是否已满足
- 授权范围是否越界

最低规则：

- schema caller 可以通过当前 caller/step 明确落在 review workflow 中来授予
  reviewer authorization
- standalone caller 可以通过 module root invocation + minimal review bundle
  来授予 reviewer authorization
- `dry-run` 和 `manual_pause` 可以阻止自动执行，但不能伪造授权成功
- `verify-only` 允许 review 执行，但不自动推进后续 caller chaining
- standalone `target_ref` review 不得被强制包进 schema-local wrapper 才能获得
  authorization
- resolver 必须能区分：
  - `authorized_and_should_run_now`
  - `authorized_but_pause_requested`
  - `not_authorized`

### 4. Invocation Mode Selection

来源：

- `openspec/schemas/ai-enforced-workflow/verification-sequence.md`
- `.codex/agents/verify-reviewer.toml`

应接入：

- 是否必须 built-in subagent
- 是否允许 shell fallback
- 是否必须 `fork_context=false`
- 是否只允许 minimal bundle

resolver 输出：

- `spawn_agent(verify-reviewer, fork_context=false)`
- 禁止 `exec` 代替 verifier
- 禁止 full parent context

最低规则：

- 如果 built-in subagent API 可用，则 `exec` 不得作为等价替代路径
- `fork_context=false` 是硬约束，不是建议
- bundle 只允许：
  - verification bundle
  - optional cache context
  - output paths
- resolver 应返回 invocation policy，而不是只返回一个模糊的
  "可以调用 reviewer"

### 5. Continuation Policy

来源：

- `propose / continue / apply / artifact-verify / verify-change / repair-change`
  skills

应接入：

- 当前 step 是否完成
- 当前是否有 blocker
- 当前是否 `verify-only|dry-run|manual_pause`
- 当前 caller 是 `propose / continue / apply / repair / verify`

resolver 输出：

- 自动继续
- 自动进入 verify
- 自动进入 repair
- 暂停等待用户
- 返回 caller flow

最低规则：

- 只要 review 是当前 step 的必需动作，就不能在写完
  `spawn-decision.json` 后停住
- review 结束后，resolver 必须明确给出是：
  - return caller flow
  - enter repair
  - rerun same working
  - enter challenger
  - wait for user
- blocker 必须是显式 blocker，不能把"主进程想再想想"当成 blocker

### 6. Docs-First / Source-First Routing

来源：

- `review_phase`
- pass-level evidence
- current caller

应接入：

- `review_phase=docs_first|source_first`
- 当前 caller surface
- findings 是否允许 auto-fix
- reroute target

resolver 输出：

- route to `openspec-repair-change`
- route back to docs artifact repair
- route back to source repair
- 是否允许 implementation auto-fix

最低规则：

- `docs_first` 与 `source_first` 共享同一 review-loop transition semantics
- `docs_first` findings 不得因为主进程主观判断而被转成 implementation
  auto-fix
- `source_first` 是否允许 implementation auto-fix，必须由 phase 与 finding
  属性共同决定
- resolver 返回的应是 repair destination，而不是抽象建议

### 7. Cache Sidecar Routing

来源：

- `openspec/schemas/ai-enforced-workflow/index-sequence.md`
- `/home/madejuele/.codex/skills/openspec-index-preflight/SKILL.md`

应接入：

- 当前 review phase
- `cache_mode`
- `fallback_policy`
- cache 是否 useful
- cache 是否可信到足以辅助定向

resolver 输出：

- bypass cache
- use cache
- continue without cache

最低规则：

- cache 只能影响 review orientation，不能影响 closure authority
- cache 缺失、cache 陈旧、cache 不可信都只能导向
  `continue without cache` 或 `bypass cache`
- resolver 不负责触发维护型 sidecar，只负责决定当前 review 是否消费 cache

### 8. Exception Routing

来源：

- spawn reason codes
- session state
- tool availability

应接入：

- `agent_not_found`
- `session_completed_unresumable`
- `tooling_recovery`
- `challenger_found_new_findings`
- `policy_requires_challenger`

resolver 输出：

- exception fresh working
- challenger reopen
- stop as blocked
- continue same session

最低规则：

- ordinary rerun 绝不能因为轻微异常就升级成 fresh working
- `challenger_found_new_findings` 必须返回 `challenger reopen`
- `policy_requires_challenger` 不应被解释成 blocker，而应被解释成
  "不可 close，必须 fresh challenger"
- `tooling_recovery` 是否允许 fresh working，必须显式记录 exception reason

### 9. Closure Gate

来源：

- final challenger evidence
- findings
- coverage/saturation
- source review binding

应接入：

- final pass type
- zero findings
- `closure_authority=challenger_confirmed`
- `complete + exhaustive`

resolver 输出：

- allow close
- deny close
- reopen working

最低规则：

- close 是 resolver 的显式结果，不能由主进程自己脑补
- 只要缺任一项：
  - final pass is challenger
  - zero findings
  - `closure_authority=challenger_confirmed`
  - `coverage_status=complete`
  - `saturation_status=exhaustive`
  就必须 `deny close`
- challenger 返回 findings 时，结果不是 `deny close and stop`，而是
  `reopen working`

### 10. Run Layout / Path Coherence

来源：

- run-dir artifacts
- `spawn_decision_path`
- `verifier_output_path`
- `findings_path`
- `verifier_evidence_path`

应接入：

- path existence
- path binding
- path subject consistency

resolver 输出：

- next step allowed / denied
- challenger allowed / denied
- review iteration incomplete

Only orchestration state belongs here.

Reviewer semantic judgment does not.

最低规则：

- path coherence failure 是 orchestration failure，不是 reviewer finding
- path subject mismatch 必须阻止 challenger entry 和 closure
- predecessor paths 无法解析时，resolver 必须返回 `review iteration incomplete`

## Resolver State Model

The resolver should consume normalized orchestration state rather than raw
prompt prose.

Recommended top-level state objects:

- `subject`
  - `subject_key`
  - `subject_value`
  - `review_goal`
  - `review_phase`
  - `risk_tier`
  - `evidence_paths_or_diff_scope`
  - `findings_contract`
- `session`
  - `active_working_agent_id`
  - `active_challenger_agent_id`
  - `session_open`
  - `resumable`
  - `exception_reason`
- `review_result`
  - `review_pass_type`
  - `final_assessment`
  - `findings_count`
  - `coverage_status`
  - `saturation_status`
  - `closure_authority`
- `predecessor`
  - `source_review.agent_id`
  - `source_review.findings_path`
  - `source_review.verifier_evidence_path`
- `caller`
  - `entrypoint`
  - `step_name`
  - `verify_only`
  - `dry_run`
  - `manual_pause`
  - `blocker_present`
- `authorization`
  - `module_root_invocation`
  - `minimal_bundle_present`
  - `bundle_field_validation`
  - `reviewer_required`
- `invocation`
  - `requested_invocation_mode`
  - `built_in_subagent_available`
  - `shell_fallback_allowed`
  - `provided_context_scope`
  - `fork_context_requested`
- `paths`
  - `spawn_decision_path`
  - `findings_path`
  - `verifier_evidence_path`
  - `verifier_output_path`
- `cache`
  - `cache_mode`
  - `fallback_policy`
  - `cache_usable`

This state model is intentionally orchestration-only.

It does not encode reviewer judgment detail beyond the normalized result
needed for transitions.

## Resolver Decision Surface

The resolver should produce explicit next-step decisions instead of vague
"continue review" language.

Recommended decision enum:

- `send_input_same_working`
- `resume_same_working`
- `spawn_fresh_challenger`
- `record_challenger_reopen`
- `spawn_exception_working`
- `enter_repair`
- `return_caller_flow`
- `wait_for_user`
- `allow_close`
- `deny_close`
- `blocked`

Recommended required metadata per decision:

- `decision`
- `reason_code`
- `required_session_mode`
- `required_invocation_mode`
- `reroute_destination`
- `required_evidence_checks`
- `required_path_checks`
- `authorized`
- `blocking`
- `mechanical_gate_required`
- `mechanical_gate_status`

## Mechanical Denial Cases

The resolver should fail closed on at least these cases:

1. challenger requested but predecessor `source_review` binding is missing
2. challenger requested but predecessor findings are non-empty
3. challenger requested but predecessor evidence is not a `working` pass
4. close requested but final pass is not challenger
5. close requested but `closure_authority` is not
   `challenger_confirmed`
6. ordinary rerun requested but no active/resumable working session exists and
   no exception reason is recorded
7. built-in subagent required but caller tries to replace it with shell/`exec`
8. required verifier paths are missing or subject-incoherent
9. pause flags are absent, but the workflow tries to stop after preparatory
   artifacts only
10. docs-first review tries to route directly into implementation auto-fix
11. closure requested before the mandatory run-dir mechanical gate succeeds

## Suggested Module Shape

Recommended shape:

```text
review-flow/
  README.md
  transition-resolver-execution-plan.md
  transition-resolver/
    resolver contract(s)
    validator or guard
    optional CLI / Python entrypoint
```

Possible responsibilities of the resolver layer:

- evaluate current review state
- decide allowed next transitions
- emit normalized transition decisions
- validate predecessor evidence before challenger
- validate exception conditions before fresh working spawn
- expose a small callable interface for schema and standalone wrappers
- require a final run-dir mechanical gate before honoring closure

Explicitly not responsible for:

- performing the review itself
- deciding whether a finding is correct
- editing files outside the caller's declared repair scope

The resolver may call a guard or validator for closure gating, but it must not
silently replace that closure gate with its own in-memory judgment.

## Recommended Minimal Resolver Inputs

The resolver does not need the whole world. A minimal useful input set is:

- subject key: `change` or `target_ref`
- `review_goal`
- `review_phase`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract`
- requested transition intent
- current pass type
- normalized current `review_result`
  - `final_assessment`
  - `findings_count` or zero-findings equivalent
  - `coverage_status`
  - `saturation_status`
  - `closure_authority`
- current session metadata
- predecessor evidence metadata
- output-path metadata
- caller metadata
- normalized authorization metadata
  - `module_root_invocation`
  - `minimal_bundle_present`
  - `bundle_field_validation`
  - `reviewer_required`
- normalized invocation metadata
  - `requested_invocation_mode`
  - `built_in_subagent_available`
  - `shell_fallback_allowed`
  - `provided_context_scope`
  - `fork_context_requested`
- normalized cache metadata
- exception reason when claiming a fresh working session is necessary

## Recommended Minimal Resolver Outputs

- `decision`: allow or deny
- `resolved_transition`
- `required_session_mode`: reuse working, fresh challenger, fresh working
  exception, or no-spawn
- `reroute_destination`
  - `openspec-repair-change`
  - `docs_artifact_repair`
  - `source_repair`
  - `none`
- `required_evidence_checks`
- `required_invocation_mode`
- `required_output_artifacts`
- `required_mechanical_gate`
- `denial_reason` when blocked

## Execution Order

1. Finish extracting shared orchestration constraints out of prompt prose.
2. Simplify the contracts to the minimum state needed for orchestration.
3. Introduce the transition resolver for review-loop transition, session
   freshness, and closure decisions first.
4. Add spawn authorization, invocation mode, and continuation policy to the
   same resolver boundary.
5. Add phase routing, cache sidecar routing, exception routing, and
   run-layout coherence checks.
6. Wire schema and standalone callers to the same resolver logic.
7. Ensure the resolver inherits completed baselines such as docs-first
   verification at artifact-completion time rather than re-specifying them in
   prompts.
8. Preserve the module's mandatory post-run mechanical gate by requiring the
   exact current command
   `python3 /home/madejuele/projects/2K0300/openspec/schemas/modules/review-loop/bin/review_loop_guard.py --run-dir <review-run-dir>`
   before closure is honored, unless the shared module contract itself is
   formally updated first.
9. Extend resolver ownership only after the core orchestration loop is stable.

## Acceptance Criteria

The work is only successful if all of the following are true:

1. A main process cannot open challenger unless the previous sub-agent pass is
   explicitly recorded and validated.
2. Ordinary repair reruns stay in the same working session by default.
3. Built-in subagent invocation is used for verifier review when available.
4. Writing `spawn-decision.json` no longer counts as "review completed".
5. The resolver preserves the completed baseline that
   `openspec-propose`-class artifact-completion callers automatically proceed
   into docs-first verification once artifacts are ready.
6. Schema and non-schema entrypoints reference the same shared review-loop
   semantics.
7. A context-free AI can use the module root and follow the workflow correctly
   without inventing an `artifact` vs `implementation` semantic split.
8. Final closure still requires the mandatory run-dir mechanical gate from the
   shared review-loop module, rather than resolver-only self-assertion.

## Operator Prompt For External Use

The intended external instruction shape is:

```text
Reference <module-root> and verify whether the implementation is correct.
Follow the working/challenger review loop exactly.
```

That should be enough because the module, contracts, and resolver together
define:

- bootstrap behavior
- transition rules
- closure rules
- invocation rules
- schema-independent subject binding

## Relationship To Existing Files

This document complements, and does not replace:

- `docs/reusable-review-flow.md`
- `docs/review-flow/README.md`
- `openspec/schemas/modules/review-loop/README.md`
- `openspec/schemas/modules/review-loop/VERIFY-IMPLEMENTATION.md`
- `openspec/schemas/modules/review-loop/contracts/*.json`

Those files describe the current shared review loop.
This file records the full optimization program for pushing that loop from
prompt-guided orchestration toward resolver-guided orchestration.
