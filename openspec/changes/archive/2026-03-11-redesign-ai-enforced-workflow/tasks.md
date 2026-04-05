## 1. 更新工作流规格与全局指引

- [x] 1.1 更新 `openspec/specs/ai-architecture-guidelines/spec.md`，将 Python 特定硬规则改为语言无关的工程意图、证据要求与风险分级要求
- [x] 1.2 新增并完善 `ai-enforced-workflow`、`artifact-verification`、`change-repair-loop` 对应 specs，使其覆盖 phase gates、findings 协议、repair 回流路径与反抽象护栏
- [x] 1.3 校验 proposal、specs、design 之间的 capability 映射是否一致，确保没有遗漏的行为要求

## 2. 重构 ai-enforced-workflow schema

- [x] 2.1 更新 `openspec/schemas/ai-enforced-workflow/schema.yaml`，明确 workflow 是 artifact contract + phase gates + skill orchestration
- [x] 2.2 在 schema 中加入 `LIGHT / STANDARD / STRICT` 风险分级语义，并定义各等级对 design、align、artifact verify、repair loop 的门禁差异
- [x] 2.3 调整 schema instruction，使其强调 evidence、stack equivalent、named deliverables、failure semantics、boundary examples、verification hooks 与 blocking rules，而不是 Python 专属实现写法
- [x] 2.4 校验模板文件与 schema 说明保持一致，确保 proposal/spec/design/tasks 模板都能承载新的工作流语义

## 3. 重组相关 skills

- [x] 3.1 重写 `openspec-architect` 的职责边界，使其聚焦架构推演、方案比较、stack equivalent 输出与 design 决策支持
- [x] 3.2 新建 `openspec-align` skill，定义对标输入、契约提取、映射表与 coverage report 的输出格式
- [x] 3.3 新建 `openspec-artifact-verify` skill，定义对 `proposal/specs/design/tasks` 的 Completeness / Correctness / Coherence 审计流程，并检查反抽象护栏
- [x] 3.4 新建 `openspec-repair-change` skill，定义 findings 消费协议、问题分层和 proposal/specs/design/tasks/implementation 回流规则
- [x] 3.5 统一 verify 类 skill 的 findings 结构，至少包含 severity、dimension、evidence、recommendation、redirect_layer、blocking

## 4. 演练与验证闭环

- [x] 4.1 使用测试 change 演练 `explore -> new -> continue -> artifact-verify -> apply -> verify -> repair -> sync -> archive` 的完整路径
- [x] 4.2 分别验证 `LIGHT`、`STANDARD`、`STRICT` 三种风险等级下的门禁差异是否符合预期
- [x] 4.3 验证 `artifact-verify` 发现问题后，`repair-change` 能正确区分 artifact 层问题与 implementation 层问题，并能把缺失的设计锚点回流到正确 artifact
- [x] 4.4 记录残留问题、未决取舍和后续迭代建议，确保新工作流可以继续演进
