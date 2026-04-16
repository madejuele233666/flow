# Code-Review-First 分层落地总览

## 状态

本目录是 `code-review-first` 的**最新、最权威**文档集合。

它替代以下大单文件作为后续实施的主要依据：
- `docs/code-review-first-execution-plan.md`
- `docs/code-review-first-execution-plan.zh-CN.md`

这两个旧文件保留为历史参考，但后续实现以本目录为准。

## 目标

用**最短主路径**把自动审查系统改造成真正的 code-review-first 流程，
同时把容易膨胀的能力放到旁路层，避免：

- 把 `repo-index` 换名后继续做 gate
- 把 `review planner` 长成新的 `Stage 0`
- 把 `finding ledger` 做成全量 defect database
- 把 `variant analysis` 变成 closure 阻塞器

## 必读顺序

1. `docs/code-review-first/README.md`
2. `docs/code-review-first/01-principles-and-boundaries.md`
3. `docs/code-review-first/02-layered-rollout-overview.md`
4. `docs/code-review-first/03-layer-1-core-review-loop.md`
5. `docs/code-review-first/04-layer-2-lightweight-scope-summary.md`
6. `docs/code-review-first/05-layer-3-tracked-findings.md`
7. `docs/code-review-first/06-layer-4-variant-analysis.md`
8. `docs/code-review-first/07-layer-5-contract-hardening.md`
9. `docs/code-review-first/08-migration-validation-and-stop-rules.md`

读完上述文件之前，不要开始实施。

## 文档边界

- `01-principles-and-boundaries.md`
  - 回答“为什么这样拆、什么必须简化、哪些绝不进入主路径”
- `02-layered-rollout-overview.md`
  - 回答“总体分层、层间依赖、每层产出和退出条件”
- `03-layer-1-core-review-loop.md`
  - 回答“第一层如何把主路径做对”
- `04-layer-2-lightweight-scope-summary.md`
  - 回答“如何引入 risk-based scope，但不做新 gate”
- `05-layer-3-tracked-findings.md`
  - 回答“如何只对少数 bug family 做连续追踪”
- `06-layer-4-variant-analysis.md`
  - 回答“如何做 sibling search，但不阻塞 closure”
- `07-layer-5-contract-hardening.md`
  - 回答“什么时候值得把旁路能力升级成正式契约”
- `08-migration-validation-and-stop-rules.md`
  - 回答“改哪些文件、怎么验收、什么情况下必须停下来”

## 分层摘要

| 层 | 名称 | 是否主路径 | 目标 |
|---|---|---|---|
| Layer 1 | Core Review Loop | 是 | 先把主审查闭环做对 |
| Layer 2 | Lightweight Scope Summary | 是 | 让实现审查 scope 更聪明，但不变成新 gate |
| Layer 3 | Tracked Findings | 否 | 只对白名单 bug family 做连续追踪 |
| Layer 4 | Variant Analysis | 否 | 把已确认问题扩展成仓内 sibling search |
| Layer 5 | Contract Hardening | 否 | 只有前几层稳定后，才正式 schema 化 |

## 总原则

- 主路径越短越好。
- 旁路能力失败时，不能阻塞主路径。
- 只有被证明长期稳定的能力，才允许变成正式契约。
- 所有层都必须支持降级运行。

## 主路径最小闭环

```text
Artifact Review
  -> pass or block implementation entry

Implementation Review
  -> working reviewer reviews code
  -> repair loop stays in same working session
  -> challenger pass closes or reopens
```

以下能力不在最小闭环里：
- 全量 ledger
- 全量 fingerprint
- variant analysis 阻塞 closure
- 独立 planner gate
- repo-index authority gate

## 实施入口

如果按 OpenSpec 开始实施，不要把五层内容塞进一个大 change。

推荐按层拆分为独立 change：
- Layer 1-2:
  `evolve-ai-enforced-workflow-core-review-loop`
- Layer 3:
  `introduce-tracked-findings-for-repeatable-families`
- Layer 4:
  `introduce-non-blocking-variant-analysis`
- Layer 5:
  `harden-stable-code-review-first-contracts`

共同规则：
- risk tier: `STRICT`
- schema: `ai-enforced-workflow`

## 与现有文档的关系

- `docs/auto-review-architecture.md`
  - 当前系统的现状图
- `docs/code-review-first-architecture.md`
  - target architecture 的高层说明
- `docs/code-review-first/`
  - 分层落地方案，后续实施以这里为准

如果 `docs/code-review-first-architecture.md` 与本目录在机制细节、实施顺序、
复杂度边界上存在任何差异，必须以 `docs/code-review-first/` 为唯一权威来源。
