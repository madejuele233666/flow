# 分层落地总览

## 总体策略

这套方案不再追求“一次性定义完整新世界”，而是采用五层渐进式落地：

1. 先把主路径做对
2. 再让 scope 更聪明
3. 再给少量问题加连续性
4. 再把已确认问题扩成 sibling search
5. 最后才决定哪些东西值得 schema 化、契约化

## 五层定义

### Layer 1: Core Review Loop

目标：
- 把 artifact review / implementation review / challenger pass 变成真正的主闭环

进入主路径：
- 是

强制产出：
- artifact review evidence
- implementation review evidence
- challenger pass evidence

不做：
- 独立 planner 文件
- ledger
- variant analysis

### Layer 2: Lightweight Scope Summary

目标：
- 引入 risk-based scope，但不制造新的流程节点

进入主路径：
- 是，但作为 `verifier-evidence.json` 的内嵌结构，不是独立 gate

强制产出：
- `review_scope`
- 最小 `review_coverage`

不做：
- 独立 planner checkpoint
- planner 自己的 authority

### Layer 3: Tracked Findings

目标：
- 只对白名单 bug family 引入跨 rerun 连续性

进入主路径：
- 否

输出规则：
- 只有在当前 change 已实际出现至少一个白名单 tracked family 时，才写
  `tracked-findings.json`
- 如果当前 change 从未命中白名单 family，不要为满足机制完整性而写空文件

只覆盖：
- repeatable family 白名单

### Layer 4: Variant Analysis

目标：
- 从一个 confirmed defect 扩展到 sibling search

进入主路径：
- 否

强制产出：
- 可选 `variant-analysis.json`

关键限制：
- 不参与 closure authority

### Layer 5: Contract Hardening

目标：
- 只有前几层跑稳后，才升级为正式 schema 和 shared contracts

进入主路径：
- 否，直到被证明值得

## 层间依赖

```text
Layer 1
  -> Layer 2
      -> Layer 3
          -> Layer 4
              -> Layer 5
```

不允许跳过：
- 没有 Layer 1，不做 Layer 2+
- 没有稳定的 Layer 2，不做 Layer 3
- 没有稳定的 tracked family，不做 Layer 4
- 没有稳定运行数据，不做 Layer 5

## 每层的退出条件

### Layer 1 退出条件

- repo-index 不再阻塞 implementation review
- artifact review 可以单独 block implementation entry
- challenger pass 是唯一 closure authority

### Layer 2 退出条件

- 每次 implementation review 都能输出结构化 scope summary
- reviewer 不再主要依赖 `required_paths`
- 没有新增 gate

### Layer 3 退出条件

- 白名单 family 的同类问题在 rerun 中能稳定去重
- ledger 没有明显噪声爆炸

### Layer 4 退出条件

- 至少一个白名单 family 能稳定做 sibling search
- variant analysis 不会拖住当前 checkpoint closure

### Layer 5 退出条件

- 至少一个增强层能力已经被证明长期稳定
- schema 化不会把复杂度重新灌回主路径

## 每层的失败降级

### Layer 1 失败

不能降级。Layer 1 是基础。

### Layer 2 失败

降级到：
- 继续做 Layer 1
- scope 由 reviewer 直接从 diff 推导

### Layer 3 失败

降级到：
- 只保留 pass-level findings
- 暂停 tracked findings

### Layer 4 失败

降级到：
- 停用 variant analysis
- 保持 Layer 3 不变

### Layer 5 失败

降级到：
- 保持结构化输出
- 不正式 schema 化

## 文件和机制的所属层

| 对象 | 所属层 | 地位 |
|---|---|---|
| two-phase review | Layer 1 | 主路径 |
| repo-index cache semantics | Layer 1 | 主路径 |
| working reviewer / challenger pass | Layer 1 | 主路径 |
| inline `review_scope` | Layer 2 | 主路径内嵌 |
| inline `review_coverage` | Layer 2 | 主路径内嵌 |
| `tracked-findings.json` | Layer 3 | 旁路增强 |
| `variant-analysis.json` | Layer 4 | 旁路增强 |
| standalone planner schema | Layer 5 | 条件升级 |
| shared findings v2 hardening | Layer 5 | 条件升级 |

## 关键设计决定

### 为什么 Layer 2 不先单独建 planner 文件

因为 planner 最容易重新长成新 gate。

先让 reviewer 在 `verifier-evidence.json` 内产出 `review_scope`，可以保留
risk-based scope 的收益，但不会产生：
- 新文件
- 新 schema
- 新 checkpoint
- 新 authority layer

### 为什么 Layer 3 不直接做全量 ledger

因为 fingerprint 是最容易做错的部分之一。

如果一开始就做全量 ledger：
- 噪声会迅速膨胀
- 实现复杂度会上升
- review 反而会被“维护 ledger”拖慢

所以只对白名单 family 做 tracked findings。

### 为什么 Layer 4 不进 closure

因为 variant analysis 的定位是“放大利益”，不是“扩大阻塞面”。

## 推荐 rollout 顺序

1. 完成 Layer 1
2. 验证 Layer 1
3. 完成 Layer 2
4. 观察一段时间
5. 完成 Layer 3
6. 再观察
7. 完成 Layer 4
8. 最后决定是否进入 Layer 5

## 推荐 change 边界

不要把五层内容放进一个大 OpenSpec change。

推荐边界：
- Change A: Layer 1 + Layer 2
- Change B: Layer 3
- Change C: Layer 4
- Change D: Layer 5

原因：
- 每层都需要真实运行观察期
- Layer 3/4 是否值得继续，必须由前层数据决定
- 如果放在一个 change 里，stop rule 和 rollback 边界会被破坏

## 一票否决项

出现以下任一情况，必须暂停往下一层推进：
- Layer 2 已经开始像 gate 一样阻塞 review
- Layer 3 开始把普通 finding 大量塞进 tracked set
- Layer 4 导致 closure latency 显著增加
- 新 schema 数量增长快于真实 review 收益
