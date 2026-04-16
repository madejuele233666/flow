# Layer 3：受控 Tracked Findings

## 目标

只对白名单 bug family 引入跨 rerun 连续性。

这一层故意不做：
- 全量 ledger
- 所有 finding 都 fingerprint
- defect database

## 为什么这一层必须受控

finding fingerprint 是最容易做错的部分之一。

如果一开始就全量追踪：
- 同一问题可能因表达方式变化而分裂成多个条目
- 不同问题可能因归一化不足而被错误合并
- ledger 会迅速退化成新的噪声源

所以 Layer 3 只做：

```text
tracked findings for selected repeatable families
```

## 受控对象

只允许以下 family 进入 tracked set：
- `missing-permission-check`
- `missing-error-handling`
- `missing-cleanup`
- `missing-state-guard`

任何不在白名单内的 finding：
- 仍然保留在 pass-level `findings.json`
- 不进入 tracked store

## 存储文件

使用：
- `openspec/changes/<change>/verification/tracked-findings.json`

不要命名为全量 `finding-ledger.json`。

写入规则：
- 只有在当前 change 已实际出现至少一个白名单 tracked family 时，才创建该文件
- 如果没有任何白名单 tracked finding，不要创建空 `tracked-findings.json`
- 不允许为了维持“机制存在感”而生成空 store

## 最小 tracked entry

```json
{
  "fingerprint": "sha256:<hex>",
  "family": "missing-permission-check",
  "status": "open|fixed_pending_confirmation|closed_verified|regressed",
  "primary_path": "src/api/user.ts",
  "primary_symbol": "updateUser",
  "first_seen_at": "2026-04-11T10:00:00Z",
  "last_seen_at": "2026-04-11T11:00:00Z",
  "linked_attempts": ["checkpoint-2/attempt-1"]
}
```

## fingerprint 规则

只对 tracked family 计算 fingerprint。

组成建议：
- family
- normalized primary path
- normalized primary symbol
- normalized bug shape

禁止：
- raw line number
- free-form evidence prose
- timestamp
- attempt id

## `normalized_bug_shape` 的最小约束

必须使用短结构标签，不允许使用完整句子。

首批样例：
- `write-operation-without-authz-guard`
- `missing-error-return-after-failed-call`
- `resource-open-without-finally-cleanup`
- `state-transition-without-precondition-check`

如果后续要扩大 family，必须先补样例再实现。

具体要求：
- 每个新 family 在启用前必须提供 canonical positive examples
- 每个新 family 在启用前必须提供 canonical negative examples
- examples 必须能说明哪些 case 应共享同一 `normalized_bug_shape`
- examples 必须能说明哪些相近 case 不应被错误合并
- 没有 examples，不得把新 family 加入 tracked set

## 状态机

只允许以下状态：
- `open`
- `fixed_pending_confirmation`
- `closed_verified`
- `regressed`

状态转换：

```text
new tracked finding
  -> open

working reviewer no longer reproduces
  -> fixed_pending_confirmation

challenger confirms absence
  -> closed_verified

same fingerprint reappears later
  -> regressed
```

不支持：
- `accepted_risk`
- `false_positive`
- 复杂 drift 分类

## 这一层与主路径的关系

tracked findings 只是增强，不是 authority。

authority 仍然来自：
- 当前 pass 的 `findings.json`
- 当前 pass 的 `verifier-evidence.json`
- challenger pass

如果 tracked store 写入失败：
- 当前 review 仍可继续
- 但要在 evidence 中记录 degradation

## 必改文件

- `.codex/agents/verify-reviewer.toml`
- `openspec-verify-change`
- `openspec-repair-change`
- `openspec-apply-change`

## 验收标准

1. 白名单 family 在重复 rerun 中不会重复裂变成多个新 finding
2. challenger pass 能把 `fixed_pending_confirmation -> closed_verified`
3. tracked store 失败不会阻塞 review
4. 非白名单 family 不会被硬塞进 tracked store
