# Layer 2：轻量 Scope Summary

## 目标

把 implementation review 的 scope 从“协议文件主导”拉回“代码风险主导”，
但**不引入新的独立 gate**。

## 核心设计

Layer 2 不引入单独的 `review-plan.json`。

改为：
- reviewer 在 implementation review 开始时
- 先在 `verifier-evidence.json` 内写一个结构化 `review_scope`
- 同时写一个最小 `review_coverage`

## 为什么不先建独立 planner 文件

因为 planner 最容易退化成：

```text
先证明 planner 正确
  -> 再允许 review 开始
```

这会直接复活旧 `Stage 0` 的问题。

Layer 2 的要求是：
- 让 scope 更聪明
- 不增加流程层级
- 不增加 authority 层

## `review_scope` 合同

放置位置：
- `verifier-evidence.json.review_scope`

最小结构：

```json
{
  "review_scope": {
    "changed_code_paths": ["..."],
    "changed_test_paths": ["..."],
    "impacted_interfaces": ["..."],
    "mandatory_deep_scan_paths": ["..."],
    "cache_inputs": ["..."]
  }
}
```

## `review_scope` 的来源

reviewer 必须综合：
- code diff
- changed tests
- public interfaces touched by the diff
- behavior-critical callers/callees
- optional repo-index cache

不要求：
- 单独 schema
- 单独 sequence
- 单独 file artifact

## `review_scope` 规则

### 必须包含

- 所有 changed implementation files
- 所有 changed tests
- public API / external contract 触达面
- 必须 deep scan 的路径

### 可以包含

- cache 提供的 ownership/boundary hints
- obvious dependency spread

### 禁止包含的倾向

- 整仓扫描清单
- workflow protocol files 主导的 scope universe
- 仅为了满足治理字段而加入的无关文件

## mandatory deep scan 规则

以下类别默认进入 `mandatory_deep_scan_paths`：
- public APIs and externally visible contracts
- state machines
- concurrency and async coordination
- permission or trust boundaries
- serialization and protocol logic
- persistence schema and migrations
- hardware interaction and low-level resource management
- error recovery and rollback paths

## `review_coverage` 合同

放置位置：
- `verifier-evidence.json.review_coverage`

最小结构：

```json
{
  "review_coverage": {
    "reviewed_paths": ["..."],
    "deep_scanned_paths": ["..."],
    "skipped_paths": [
      {
        "path": "...",
        "reason": "...",
        "skip_class": "deferred|irrelevant|blocked-by-missing-context"
      }
    ],
    "coverage_status": "complete|partial"
  }
}
```

## Layer 2 的 coverage 语义

### `complete`

满足以下条件时允许：
- 所有 changed code paths 都被 review
- 所有 mandatory deep-scan paths 都被 deep scan
- 所有 skipped paths 都有显式 `skip_class`

### `partial`

出现以下任一情况必须使用：
- mandatory deep-scan path 未真正 deep scan
- changed code path 未被 review
- 有 skipped path 但没有 `skip_class`
- reviewer 明确承认 scope 不完整

`partial` 的语义必须精确如下：
- 它不是独立 gate
- 它不会单独产生新的 planner authority
- 但 implementation review 不能在 `coverage_status=partial` 的状态下宣称
  working convergence 完成
- 如果 reviewer 认为缺失覆盖已经足以影响正确性判断，必须通过现有
  `findings.json` / `verifier-evidence.json` 产出显式 blocking finding，而不是
  发明新的 planner 阻塞状态
- challenger pass 只能在上一轮 implementation review evidence 已经达到
  `coverage_status=complete` 时启动

## `skipped_paths` 字段约束

- automation 只能读取 `skip_class`
- `reason` 仅供人类解释，不得作为分支、聚合、路由或 gating 条件
- 如果未来需要更细粒度自动化，必须先扩展 `skip_class` 的枚举值，不能复用
  `reason` 的自由文本

## 这一层的止损点

如果 Layer 2 产生以下任一现象，必须停止升级，不得进入 Layer 3：

- `review_scope` 开始演变成新的 authority contract
- reviewer 因为 scope summary 结构不完整而阻塞 review
- `review_scope` 需要单独 spawn 新 agent 才能计算
- `review_scope` 输出明显大于实际 review 价值

## 必改文件

- `openspec/schemas/ai-enforced-workflow/verification-sequence.md`
- `openspec/schemas/ai-enforced-workflow/schema.yaml`
- `.codex/agents/verify-reviewer.toml`
- `openspec-artifact-verify`
- `openspec-verify-change`
- `openspec-repair-change`

## 验收标准

1. 每次 implementation review 都能输出结构化 `review_scope`
2. 每次 implementation review 都能输出最小 `review_coverage`
3. `review_scope` 不是单独 gate
4. repo-index 不再定义 implementation authority scope
5. 没有新增独立 planner file / planner checkpoint / planner agent
