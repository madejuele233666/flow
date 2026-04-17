# Layer 4：非阻塞 Variant Analysis

## 目标

把一个已确认的真实问题扩展成仓内 sibling search，
但**绝不让它进入当前 checkpoint 的 closure authority**。

## 前置条件

只有满足以下条件才允许进入 Layer 4：
- Layer 3 已经稳定运行
- 白名单 family 的 fingerprint 噪声可控
- team 已接受“variant analysis 是增强，不是主闭环”

## 触发规则

只有当以下条件全部满足时，才允许执行 variant analysis：

1. 某个 tracked family 的 finding 已被 reviewer 确认为真实问题
2. 该 family 有明显重复出现的可能
3. 仓库中存在合理的 sibling search 范围

## 输出文件

使用：
- `openspec/changes/<change>/verification/checkpoint-<n>/attempt-<m>/variant-analysis.json`

如果没有触发 variant analysis，就不要强行写空文件。

在 Layer 4 中，这个文件只要求是结构化 JSON sidecar。

不要在 Layer 4 提前把它升级成正式 shared schema；正式 schema 化只能发生在
Layer 5。

## 最小输出结构

```json
{
  "seed_fingerprint": "sha256:<hex>",
  "family": "missing-error-handling",
  "query_summary": "...",
  "search_scope": ["src/api", "src/services"],
  "confirmed_variants": [],
  "candidate_variants": [],
  "rejected_variants": []
}
```

## authority 规则

### `confirmed_variants`

可以：
- 进入 follow-up review queue
- 进入新的 pass-level findings

但不能：
- 自动让当前 checkpoint closure 失败，除非 reviewer 明确把它们确认为当前
  checkpoint 的 blocking finding

### `candidate_variants`

只能：
- 作为候选线索

不能：
- 自动变 blocking
- 自动写入 tracked store
- 自动扩大当前 mandatory scope

## 关键边界

variant analysis 的定位是：

```text
扩大收益
不是扩大阻塞面
```

如果一个实现让 variant analysis 变成：
- mandatory follow-up gate
- current checkpoint closure prerequisite
- sibling explosion source

那就是错误实现。

## 搜索质量策略

Layer 4 不要求复杂搜索引擎。

首版可以接受：
- repository-local grep/ripgrep
- symbol-neighbor scanning
- call-pattern heuristics
- repeated framework usage matching

首版不要求：
- 全仓语义图
- 跨仓 variant search
- 高级 pattern engine

## 风险控制

### 精度优先

首版必须优先 precision，而不是 recall。

原因：
- 少报一个 sibling 问题，代价小于制造大量候选噪音
- closure 不能被低质量 candidate 拖慢

### 可观测性

每次 variant analysis 必须能解释：
- 为什么触发
- 搜索了哪里
- 为什么某个结果被列为 confirmed/candidate/rejected

### rollout 准入阈值

Change C 在扩大 rollout 之前，必须先定义并验证以下 acceptance thresholds：
- precision threshold：`candidate_variants` 中被后续人工确认有价值的比例必须达到
  预设门槛，否则不得扩大触发范围
- latency threshold：单次 variant analysis 的新增时延必须保持在团队可接受上限内，
  否则只能继续作为窄范围试验能力

在这些阈值被明确写入 Change C 并通过验证前：
- variant analysis 只能在小范围试点 family 上启用
- 不得默认扩展到所有 tracked families

## 必改文件

- `.codex/agents/verify-reviewer.toml`
- `openspec-verify-change`
- `openspec-repair-change`

## 验收标准

1. 至少一个白名单 family 能触发 sibling search
2. confirmed variants 可以进入后续 findings
3. candidate variants 不会自动变 blocker
4. variant analysis 失败不阻塞当前 checkpoint closure
