# Layer 1：核心审查闭环

## 目标

只做一件事：

```text
把主审查闭环做对
```

这一层完成后，系统应该已经具备：
- 两阶段 review
- `repo-index` 作为 cache，而不是 gate
- persistent working reviewer
- challenger pass 作为唯一 closure authority

## 这一层明确不做什么

- 不单独创建 `artifact-approval.json`
- 不单独创建 `review-plan.json`
- 不创建 ledger
- 不创建 variant-analysis
- 不把 Gemini 作为强制 gate

如果某个设计要求在 Layer 1 引入上述对象，说明设计已经过重。

## 行为模型

### Artifact Review

primary surface:
- `proposal.md`
- `specs/*/spec.md`
- `design.md`
- `tasks.md`

输出责任：
- 判断 artifacts 是否允许 implementation 继续
- machine-readable findings
- artifact review verifier evidence

阻塞规则：
- 任何未解决的 artifact-level blocking finding，都必须阻止 implementation review 进入 closure

### Implementation Review

primary surface:
- changed code
- changed tests
- directly impacted code

reference surface:
- approved artifacts
- optional repo-index cache

输出责任：
- machine-readable findings
- implementation review verifier evidence

### Challenger Pass

职责：
- fresh session
- 独立复核当前 working reviewer 的“零 open findings”结果
- 只有它能赋予 closure authority

## 这一层的最小 evidence 模型

Layer 1 不额外建新文件，只扩展现有 evidence。

### `verifier-evidence.json` 必需新增字段

artifact review 与 implementation review 统一新增：

```json
{
  "review_phase": "docs_first|source_first",
  "review_pass_type": "working|challenger",
  "cache_mode": "used|missed|stale_but_ignored|refreshed|bypassed",
  "closure_authority": "working_evidence_only|working_convergence_only|challenger_reopen_required|challenger_confirmed"
}
```

规则：
- `docs_first` phase 通常写 `cache_mode=bypassed`
- `closure_authority=challenger_confirmed` 只能出现在 fresh challenger pass
- working reviewer 的零 findings 只能代表 convergence，不能代表 closure

### `findings.json` 保持兼容

这一层不引入新的 findings contract。

要求：
- 继续使用现有 machine-readable findings
- 不破坏现有 routing
- 不要求 fingerprint

## `repo-index` 的 Layer 1 语义

### 允许的行为

- repo-index 存在时帮助 reviewer 进入上下文
- repo-index 缺失时直接 source-first review
- repo-index stale 时可以忽略或后台刷新

### 禁止的行为

- 没有 repo-index 就阻止 implementation review
- 用 repo-index 输出 implementation authority scope
- 用 repo-index 冻结 `required_paths` 决定 closure

## Session 语义

Layer 1 只保留两种 reviewer session：
- `working`
- `challenger`

working session：
- 可跨 repair rerun 复用
- 负责收敛当前 implementation findings

challenger session：
- 必须 fresh spawn
- 只在 working session 零 findings 后启动
- 如果 challenger 发现新问题，它自己的结果成为新的当前工作基线

## 必改文件

### `openspec/schemas/ai-enforced-workflow/verification-sequence.md`

必须改成显式两阶段：
- artifact review path
- implementation review path

必须写清：
- working review 与 challenger pass 的区别
- closure authority 只来自 challenger pass

### `openspec/schemas/ai-enforced-workflow/index-sequence.md`

必须改成 cache helper：
- discover
- validate
- maybe refresh
- handoff

必须去掉 implementation gate 语义。

### `.codex/agents/verify-reviewer.toml`

必须改成：
- 支持 `review_phase`
- 支持 `review_pass_type`
- artifact review 以 docs 为 primary surface
- implementation review 以 code/tests 为 primary surface
- 不把 cache 当 authority

### `.codex/agents/index-maintainer.toml`

必须改成：
- 只负责 cache maintenance
- 不对 closure authority 负责

### skills

必须改：
- `openspec-artifact-verify`
- `openspec-verify-change`
- `openspec-repair-change`
- `openspec-apply-change`
- `openspec-index-preflight`
- `openspec-index-maintain`

要求：
- artifact review 和 implementation review 入口清晰分离
- missing cache 不阻塞 implementation review
- repair rerun 优先复用 working reviewer

## 验收标准

Layer 1 完成时，必须满足：

1. 没有 repo-index 仍能 authoritative review implementation
2. artifact review 能独立 block implementation entry
3. working reviewer 可复用
4. challenger pass 是唯一 closure authority
5. 现有 findings/evidence/attempt 结构继续可读

## 明确禁止事项

- 不允许在这一层引入新的独立 gate
- 不允许在这一层引入 ledger
- 不允许在这一层引入 variant analysis
- 不允许在这一层要求 shared-findings 升级
- 不允许在这一层让 Gemini 变成 mandatory gate
