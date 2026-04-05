## Why

当前的 AI 协作工作流主要来自 `2026-03-08-ai-arch-postmortem` 的经验沉淀，能够有效约束本项目中的 Python 架构设计，但仍然过度绑定 `Protocol`、`@dataclass`、`entry_points` 等具体实现形态，难以推广到更广泛的工程。现在需要把这些经验抽象为跨技术栈、可分级、并能与 skills 协同工作的通用工作流。

## What Changes

- 新增一个通用的 `ai-enforced-workflow` 能力，将 schema 从“文档模板”升级为“artifact contract + phase gates + skill orchestration”。
- 新增 artifact 级验证能力，在实现前检查 `proposal/specs/design/tasks` 是否完整、一致、可执行。
- 新增 repair 闭环能力，在 verify 发现问题后，能够判断问题层级并回流修正 artifact 或实现。
- 引入风险分级模型（`LIGHT` / `STANDARD` / `STRICT`），按变更风险决定 design、align、artifact verify 与 repair loop 的强制程度。
- 引入“反抽象护栏”，要求 AI 在跨技术栈表达中仍然提供低歧义锚点，例如技术栈等价物、命名交付物、失败语义、边界实例、对照结构与验证钩子。
- **BREAKING**：更新现有 `ai-architecture-guidelines` 的要求，从 Python 特定写法切换为语言无关的工程意图与证据导向约束。
- 更新或重写 `openspec-architect` 的职责边界，使其不再独占对标与审计职责，而聚焦架构推演与方案比较。

## Capabilities

### New Capabilities
- `ai-enforced-workflow`: 定义通用 schema 的 artifact、阶段门禁、风险分级、反抽象护栏与 skill 协同规则。
- `artifact-verification`: 定义对 `proposal/specs/design/tasks` 的验证模型、问题等级、反抽象检查项与阻断规则。
- `change-repair-loop`: 定义 verify 后的结构化修正闭环，包括 findings 协议、问题分层与回流路径。

### Modified Capabilities
- `ai-architecture-guidelines`: 将当前偏 Python / 本项目架构的硬性规则，调整为跨工程适用的证据驱动、边界契约、对标覆盖与风险分级原则。

## Impact

- 影响 `openspec/schemas/ai-enforced-workflow/` 的 schema 与模板定义。
- 影响 `.codex/skills/` 下的工作流相关 skills，尤其是 `openspec-architect` 及新增的 `openspec-align`、`openspec-artifact-verify`、`openspec-repair-change`。
- 影响 `openspec/specs/ai-architecture-guidelines/spec.md` 以及新增工作流相关 specs。
- 会改变 AI 在创建、审查、修正 change artifacts 时的默认行为和门禁逻辑，并要求关键抽象声明提供更具体的落地与验证证据。
