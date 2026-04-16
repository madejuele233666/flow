# 迁移、验证与停止规则

## 实施入口

使用 OpenSpec 分层新建 change，不要把所有层塞进一个 change。

推荐 change 边界：
- Change A:
  `evolve-ai-enforced-workflow-core-review-loop`
  - 只覆盖 Layer 1 + Layer 2
- Change B:
  `introduce-tracked-findings-for-repeatable-families`
  - 只覆盖 Layer 3
- Change C:
  `introduce-non-blocking-variant-analysis`
  - 只覆盖 Layer 4
- Change D:
  `harden-stable-code-review-first-contracts`
  - 只覆盖 Layer 5

共同规则：
- risk tier: `STRICT`
- schema: `ai-enforced-workflow`

## 每个 change 的最小产物

每个 change 都必须创建：
- `proposal.md`
- `design.md`
- `tasks.md`
- `specs/<capability>/spec.md`

补充规则：
- 如果一个 change 覆盖多个 capability，必须为每个 capability 提供对应的
  delta spec
- 不允许只写 `proposal/design/tasks` 而省略 spec，因为 Layer 1 的 artifact
  review 本身就依赖 `specs/*/spec.md`

### Change A 的 capability 建议

- `ai-enforced-workflow`
- `repository-index-cache`

注意：
- `review-planner` 在 Layer 2 中先以内嵌结构落地，不要求作为独立 capability
- Change A 不应包含 `tracked-findings` 或 `variant-analysis`

### Change B 的 capability 建议

- `tracked-findings`

### Change C 的 capability 建议

- `variant-analysis`

### Change D 的 capability 建议

- 仅对已经稳定的对象做 contract hardening
- 不要求新增 capability；也可以表现为对既有 capability 的 hardening

## 首批必须修改的文件

### Layer 1 相关

- `openspec/schemas/ai-enforced-workflow/schema.yaml`
- `openspec/schemas/ai-enforced-workflow/verification-sequence.md`
- `openspec/schemas/ai-enforced-workflow/index-sequence.md`
- `openspec/schemas/ai-enforced-workflow/agent-spawn-decision-v1.schema.json`
- `.codex/agents/verify-reviewer.toml`
- `.codex/agents/index-maintainer.toml`
- `/home/madejuele/.codex/skills/openspec-artifact-verify/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-verify-change/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-repair-change/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-apply-change/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-index-preflight/SKILL.md`
- `/home/madejuele/.codex/skills/openspec-index-maintain/SKILL.md`

### Layer 2 相关

仍然以上述文件为主。

不要新增：
- 独立 planner sequence 文件
- 独立 planner schema 文件
- 独立 planner artifact 文件

### Layer 3 相关

在 Change A 已稳定后，才允许新增：
- `tracked-findings.json`
- 结构化 JSON sidecar 输出

补充限制：
- 只有在当前 change 已实际命中白名单 tracked family 时，才允许创建
  `tracked-findings.json`
- 没有 tracked finding 时不得创建空文件

不要新增：
- shared schema
- tracked-findings 的正式 contract hardening

这些都必须留到 Layer 5 / Change D。

### Layer 4 相关

在 Change B 已稳定后，才允许新增：
- `variant-analysis.json`
- 结构化 JSON sidecar 输出

不要新增：
- shared schema
- variant-analysis 的正式 contract hardening

这些都必须留到 Layer 5 / Change D。

## 兼容性要求

必须继续兼容：
- 现有 `findings.json`
- 现有 `verifier-evidence.json`
- 现有 `latest-attempt.json`
- 现有 attempt directory naming
- 现有 repo-index layout

兼容原则：
- additive first
- semantic downgrade allowed
- silent breaking change forbidden

## 推荐实施顺序

1. 先实现 Layer 1
2. 只在 Layer 1 稳定后实现 Layer 2
3. 观察一段时间
4. 关闭 Change A 或明确暂停在 Layer 2
5. 再决定是否开启 Change B
6. Change B 稳定后再决定是否开启 Change C
7. 最后再决定是否进入 Change D / Layer 5

## 验收清单

### Layer 1 验收

必须证明：
1. artifact review 可独立阻塞 implementation entry
2. implementation review 不依赖 repo-index gate
3. working reviewer 可跨 repair rerun 复用
4. challenger pass 是唯一 closure authority

### Layer 2 验收

必须证明：
1. implementation review evidence 内存在结构化 `review_scope`
2. implementation review evidence 内存在最小 `review_coverage`
3. `review_scope` 不是独立 gate
4. `review_scope` 没有演化成新的 path-universe authority

### Layer 3 验收

必须证明：
1. 白名单 family 能稳定去重
2. tracked store 失败时 review 仍可继续
3. 非白名单 finding 不被硬塞入 tracked set

### Layer 4 验收

必须证明：
1. 至少一个白名单 family 能稳定产生 sibling search
2. candidate variant 不会自动变 blocker
3. variant analysis 失败不阻塞当前 closure

### Layer 5 验收

必须证明：
1. 新 schema 对应的是已经稳定存在的结构
2. schema 化没有新增 gate
3. schema 化没有扩大 authority surface

## 必须停止并回退的信号

### 针对 Layer 1

出现以下任一情况必须停：
- repo-index 仍然在实现层阻塞 review
- challenger pass 不再是唯一 closure authority

### 针对 Layer 2

出现以下任一情况必须停：
- reviewer 因 scope summary 不完整而无法开始 review
- scope summary 需要新 checkpoint 或新 agent
- scope summary 开始主导 authority

### 针对 Layer 3

出现以下任一情况必须停：
- tracked family 噪声持续增多
- fingerprint 经常错误合并不同问题
- fingerprint 经常把同一问题裂成多个 entry

### 针对 Layer 4

出现以下任一情况必须停：
- variant analysis 明显拉高 closure latency
- candidate variants 大量变成噪声
- current checkpoint 被 sibling search 拖住

### 针对 Layer 5

出现以下任一情况必须停：
- 为了 schema 而牺牲 review 质量
- schema 数量增长速度快于实际收益
- consumer 兼容改造成本过高

## 非阻塞风险与处理方式

### `normalized_bug_shape` 风险

处理方式：
- 只在 Layer 3 的白名单 family 内使用
- 先补样例，再扩 family
- 发现噪声就缩回 family 范围

### variant analysis 质量风险

处理方式：
- precision first
- 保留 `query_summary`
- 保留 `search_scope`
- 把它当增强，不当 authority

### `shared-findings-v2` 兼容风险

处理方式：
- 放到 Layer 5 再正式化
- 正式化前先做 consumer compatibility test

## 对旧文档的处理

### `docs/code-review-first-execution-plan.md`

降级为历史单文件参考。

### `docs/code-review-first-execution-plan.zh-CN.md`

降级为历史单文件参考。

### 后续新增内容

不要再往旧单文件里堆。

所有新增方案、争议、细化，都应当归入本目录对应边界文件。
