# 原则与边界

## 目标函数

这套方案优化的唯一主目标是：

```text
更早发现更多真实代码缺陷
```

不是：
- 更完整地证明流程存在
- 更细地记录每次 rerun
- 更快地产出新的协议对象

## 为什么必须分层

如果把以下能力一次性全部做成主路径硬依赖：
- artifact approval
- review planner
- review coverage
- finding ledger
- variant analysis

系统会摆脱旧的 index-first 偏差，却重新落入新的机制堆叠。

因此必须分层：
- 主路径只放“没有它就做不对 review”的能力
- 旁路层只放“能增强 review，但不该阻塞 review”的能力

## 四条核心简化原则

### 1. 先保证闭环，再追求聪明

先把下面这条链做稳：

```text
artifact review
  -> implementation review
  -> repair loop
  -> challenger pass
```

只有在这条链已经稳定的前提下，才允许加入更聪明的能力。

### 2. 任何新能力都必须支持降级

降级规则：
- cache 缺失，回 source-first review
- tracked findings 失败，仍保留 pass-level findings
- variant analysis 失败，不影响 checkpoint closure
- Gemini 不触发时，challenger pass 仍可完成 closure

### 3. 旁路能力不得自封 authority

以下能力默认不是 authority：
- repo-index
- lightweight scope summary
- tracked findings
- variant analysis

authority 只来自：
- 当前 review pass 的 machine-readable findings
- 当前 review pass 的 verifier evidence
- fresh challenger pass 的最终确认

### 4. 复杂度必须后置

越容易做错、越容易制造噪声的能力，越应该晚做：
- fingerprint
- ledger
- variant analysis
- contract hardening

## 永远不能被接受的退化

### 退化 1：review planner 长成新 Stage 0

以下行为一律禁止：
- planner 自己变成单独 gate
- planner 自己要求 spawn verifier 之外的 agent 才能继续
- planner 因为信息不完美而阻塞 review 启动
- planner 自己产出新的 checkpoint

### 退化 2：repo-index 改名不改性

以下行为一律禁止：
- repo-index 缺失时阻塞 implementation review
- repo-index 继续定义 implementation review 的 authority scope
- 用新字段替换 `required_paths`，但本质仍做旧 gate

### 退化 3：ledger 变成全量噪声池

以下行为一律禁止：
- 所有 finding 都强制进入 ledger
- 所有 finding 都要求稳定 fingerprint
- 仅因 severity/dimension 漂移就新建条目

### 退化 4：variant analysis 扩大阻塞面

以下行为一律禁止：
- variant analysis 参与 closure authority
- candidate variant 自动变 blocker
- 一个 confirmed finding 自动扩成整仓 mandatory scope

## 主路径与旁路能力的边界

### 主路径能力

这些能力必须进入主路径：
- artifact review
- implementation review
- working reviewer
- challenger pass
- 最小 evidence 输出

### 旁路能力

这些能力默认只做增强：
- repo-index cache
- lightweight scope summary
- tracked findings
- variant analysis
- Gemini

## 最小主路径状态机

```text
artifact review
  -> blocked
  -> or approved

approved
  -> implementation review (working)
  -> repair rerun (working, same session)
  -> zero findings
  -> challenger pass
  -> pass or reopen
```

## 复杂度预算原则

如果某层引入的新文件、schema、状态机、工件明显多于它直接减少的审查成本，
就说明这一层设计过重，必须回退。

## 这一组文档如何使用

阅读时按以下顺序决策：
- 先用 `02-layered-rollout-overview.md` 确定当前要落哪一层
- 再读对应层的细则文件
- 最后用 `08-migration-validation-and-stop-rules.md` 执行和验收
