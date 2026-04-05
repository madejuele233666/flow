## Context

当前项目已经有三块相关资产，但它们还没有形成一套真正通用的协作协议。

第一块是 `2026-03-08-ai-arch-postmortem` 沉淀出来的架构防呆经验。这些经验非常有价值，但其表达方式强绑定当前项目里的 Python 形态，例如 `Protocol`、`@dataclass(frozen=True)`、`entry_points`、插件双层 context 等，导致规则更像“本项目架构风格守则”，而不是“跨工程的 AI 协作协议”。

第二块是当前的 `ai-enforced-workflow` schema 骨架。它虽然已经存在，但本质上仍然是 `ai-postmortem-workflow` 的复制体，没有完成真正的抽象，也没有把 workflow 和 skills 的职责边界梳理清楚。

第三块是现有 skills 集合。官方 skills 覆盖 explore、new、continue、apply、verify-change、sync、archive，但缺少两个关键闭环：一是在实现前验证 `proposal/specs/design/tasks` 是否靠谱，二是在 verify 发现问题后，如何结构化地回流修正。当前的 `openspec-architect` 也同时承担了对标、设计、审计三种职责，已经不适合新工作流。

## Goals / Non-Goals

**Goals:**
- 把 `ai-enforced-workflow` 重构为通用工作流，明确它是“artifact contract + phase gates + skill orchestration”，而不是只是一套模板。
- 建立风险分级模型 `LIGHT / STANDARD / STRICT`，用于调节 artifacts、skills 和门禁强度。
- 建立 artifact 级验证能力，在实现前审查 `proposal/specs/design/tasks` 的完整性、一致性、可执行性。
- 建立 repair loop，保证 verify 发现的问题能够路由回正确层级，而不是默认只修代码。
- 重写 `openspec-architect` 的职责边界，使其聚焦架构推演，而把对标与审计分别交给 `openspec-align` 和 `openspec-artifact-verify`。
- 将现有 `ai-architecture-guidelines` 从 Python 特定硬规则升级为语言无关、证据导向的指导能力。

**Non-Goals:**
- 不在本次 change 中实现新的 CLI 子命令或 OpenSpec 引擎层自动调度。
- 不要求所有轻量变更都走最严格的双闭环；风险分级本身就是为了避免流程过重。
- 不把 schema 写成“伪 skill”。具体的推理、抽证、审计、修正动作仍由 skills 承担。

## Decisions

### Decision 1: 将新工作流定义为“结果约束 + 过程约束”的组合

`ai-enforced-workflow` 将明确区分 schema 与 skill 的职责：

- schema 负责定义必须存在的 artifacts、阶段门禁和阻断规则
- skills 负责执行探索、对标、架构推演、artifact 审计、实现、实现验证和修正

这样可以避免两种极端：

- 只有 workflow，没有 skills，最终变成机械填表
- 只有 skills，没有 workflow，最终变成临场发挥

备选方案是继续沿用当前思路，把更多操作细节塞进 schema instruction。放弃该方案的原因是 schema 会快速膨胀成不可维护的“文字版 skill”，既不稳定，也不利于后续分工。

### Decision 2: 建立双闭环，而不是单次直线流程

完整流程应分成两个串联闭环：

```text
Artifact 闭环:
continue -> artifact-verify -> repair-change -> continue

Implementation 闭环:
apply -> verify-change -> repair-change -> verify-change
```

第一个闭环用于回答“计划本身是否靠谱”；第二个闭环用于回答“实现是否符合计划”。这样可以把“文档失真”和“代码偏离”区分开来，避免 verify 后一律只改代码。

备选方案是维持官方单一 verify 流程。放弃原因是它只能在实现后发现问题，无法防止低质量 design/tasks 把实现阶段带偏。

### Decision 3: 引入三档风险分级模型驱动门禁强度

工作流将引入 `LIGHT / STANDARD / STRICT` 三档风险等级。

- `LIGHT`: 范围窄、边界简单、无高风险迁移与核心基础设施影响。允许轻量流程。
- `STANDARD`: 多模块改动、有行为变更和集成复杂度，但不是底层重构。需要常规 design 与 artifact verify。
- `STRICT`: 涉及核心基础设施、公共接口、复杂迁移、并发状态、显式参考对标等高风险因素。需要最严格的 gate。

风险等级不会是装饰性标签，而是直接驱动：

- `design.md` 是否必须存在
- `openspec-align` 是否为必选
- `openspec-architect` 是否建议或要求参与
- `artifact-verify` 是否采用阻断模式
- `repair-change` 是否需要支持全层回流

备选方案是统一使用一套严格流程。放弃原因是简单变更会承受过高的流程成本，反而导致使用者绕开工作流。

### Decision 4: 拆分 `openspec-architect` 的三合一职责

现有 `openspec-architect` 同时承担：

- 对标提取
- 架构设计
- 架构审计

新体系下将其拆分为：

- `openspec-align`: 对标、契约提取、映射覆盖
- `openspec-architect`: 架构推演、方案比较、设计决策支持
- `openspec-artifact-verify`: artifact 质量审计与阻断

这样可以让每个 skill 保持单一职责，并避免“设计者同时是审计者、也是对标证据提供者”的角色冲突。

备选方案是保留现有 `openspec-architect`，只做少量文字更新。放弃原因是它仍然会和新 skills 严重重叠，并继续把 Python 约束带入通用工作流。

### Decision 5: 定义统一 findings 协议，作为 verify 与 repair 的粘合层

`openspec-artifact-verify` 和 `openspec-verify-change` 都应输出统一结构的 findings，至少包含：

- `id`
- `severity` (`CRITICAL / WARNING / SUGGESTION`)
- `dimension` (`Completeness / Correctness / Coherence`)
- `artifact`
- `problem`
- `evidence`
- `recommendation`
- `redirect_layer`
- `blocking`

这样 `openspec-repair-change` 无需重新理解自然语言报告，而可以基于统一问题模型决定修 proposal、specs、design、tasks 还是 implementation。

备选方案是保留每个 verify skill 自己的自由文本输出。放弃原因是 repair loop 将无法稳定消费，也无法在未来形成半自动路由。

### Decision 6: 将 `ai-architecture-guidelines` 升级为通用“工程意图 + 证据”规则

现有 `ai-architecture-guidelines` 里的很多要求本质上是正确的，但表达层绑定了 Python 载体。新版本将把规则提升到语言无关的工程意图层，例如：

- `Protocol` -> 显式边界契约
- `@dataclass(frozen=True)` -> 结构化且默认不可变的消息模型
- `dict/list[dict]` -> 可序列化、稳定、低耦合的边界数据
- `entry_points` -> 声明式扩展发现机制

同时保留 postmortem 中真正可泛化的原则：

- 拒绝概念堆砌
- 强制实现级对标
- 要求 coverage report
- 要求 evidence
- 要求风险分级影响协作强度

备选方案是保留当前 guidelines，不做 capability 级修改，仅在 skill 文本里绕开。放弃原因是底层 spec 不改，上层 skill 永远会背着旧语义运行。

### Decision 7: 用“反抽象护栏”替代 Python 语法级锚点

去掉 Python 特定表达后，最大的风险不是规则变弱，而是 AI 会重新滑回“用大词伪装成已经完成设计”的旧习惯。因此，新工作流不能只要求 evidence，还必须要求每个抽象概念支付明确的落地成本。

工作流将引入六类反抽象护栏：

- **Stack Equivalent**: 任何工程意图都必须指出其在当前技术栈中的等价构造。例如“边界契约”必须落到 interface、schema、trait、DTO、service contract 等技术栈等价物之一，而不能只停留在抽象名词。
- **Named Deliverables**: 设计和 tasks 必须锚定命名实体，而不是“建立机制”“增强能力”之类的抽象动作。实体可以是接口、消息模型、状态表、manifest、lifecycle contract、capability matrix 等。
- **Failure Semantics**: 每个关键机制必须定义正常路径之外的失败路径、降级路径或恢复路径，避免只描述 happy path。
- **Boundary Examples**: 每个关键边界至少给出 1 个具体样例，说明调用方、边界载荷、禁止泄漏物和返回形式。
- **Contrast Structure**: 关键设计必须通过“当前 vs 目标”“方案 A vs 方案 B”“允许 vs 禁止”“复刻 vs 适配”等对照结构说明取舍，而不是只写单点结论。
- **Verification Hook**: 每个关键声明都必须说明未来如何验证，例如静态检查、结构审计、测试场景、日志验证、配置检查或流程演练。

这六类护栏的目标，是保留 Python 绑定规则曾经提供的“低歧义锚点”，但把它们提升为跨技术栈可复用的约束形式。这样既不退回纯抽象，也不再把某一种语言的语法形态当作唯一合法答案。

在流程上的落点是：

- `openspec-architect` 负责在设计阶段补足 stack equivalent、对照结构和关键取舍
- `openspec-artifact-verify` 负责检查 named deliverables、boundary examples、failure semantics、verification hooks 是否存在
- `ai-enforced-workflow` schema 负责把这些项变成 design/tasks 的显式门槛

备选方案是仅增加“要求 evidence”这一条通用规则。放弃原因是 evidence 本身仍然可能过于宽泛，无法单独阻止 AI 用模糊证据包装抽象结论。

## Risks / Trade-offs

- [Risk] 工作流过重，简单 change 也被迫经过重型审计
  → Mitigation: 用风险分级控制门禁强度，默认只对 `STRICT` 变更启用最严格闭环。

- [Risk] skill 职责重新划分后，用户短期内会混淆 `align`、`architect`、`artifact-verify`
  → Mitigation: 在 schema 和 skill 描述里显式写出触发条件、输入输出与边界。

- [Risk] findings 协议如果定义得太松，repair loop 仍然会退化成人工理解自由文本
  → Mitigation: 把 evidence、redirect layer、severity 作为强制字段，而不是建议字段。

- [Risk] 通用化以后丢失本项目中已经验证有效的 Python 工程精度
  → Mitigation: 将 Python 经验下沉为 stack-specific hints 或 examples，并用 stack equivalent、named deliverables、failure semantics 等反抽象护栏补回低歧义约束。

- [Risk] 反抽象护栏过多，导致 design 文档变得机械、冗长
  → Mitigation: 由风险分级决定护栏密度；`LIGHT` 变更只要求最小集合，`STRICT` 变更才要求完整护栏。

## Migration Plan

1. 先更新 workflow 和相关 specs，明确风险分级、phase gates、findings 协议、反抽象护栏与 skill 分工。
2. 重写 `openspec-architect`，将其职责收缩到架构推演与方案比较，并显式输出 stack equivalent、方案对照和关键取舍。
3. 新增 `openspec-align`、`openspec-artifact-verify`、`openspec-repair-change`。
4. 更新 `ai-enforced-workflow` schema，使其表达 skill 协同、阻断规则以及对 named deliverables、boundary examples、verification hooks 的要求。
5. 用一个测试 change 演练完整流程，验证 artifact 闭环和 implementation 闭环都能工作，并检查反抽象护栏能否有效阻止空泛设计。

## Open Questions

- 风险等级是仅由人工指定，还是允许 skill 根据触发器自动建议默认等级？
- `artifact-verify` 的 `WARNING` 是否一律允许进入 apply，还是在 `STRICT` 变更里需要用户显式确认？
- findings 协议最终是只作为 skill 输出约定，还是未来写入 OpenSpec CLI 的机器可读格式？
