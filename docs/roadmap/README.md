# Flow 路线图总览

状态基线：2026-04-17

这个目录是当前文档真相面，但其中只有一部分内容是在陈述“今天已经实现了什么”。

这里的内容分三类：

- 已验证事实
  - 只写代码、测试、现行规格能直接支撑的内容
- 历史经验
  - 来自 `docs/past/` 的复盘或长期护栏
- 路线判断
  - 面向终局产品的推进建议，不冒充已实现现状

## 这套文件怎么读

如果你要先看代码已证实的现状，看：

- [01-current-state.md](./01-current-state.md)

如果你要对齐“完整且优雅的产品”定义，看：

- [02-north-star.md](./02-north-star.md)

如果你要看原始愿景文档已经如何被拆成可执行能力地图，看：

- [09-capability-decomposition.md](./09-capability-decomposition.md)

如果你要看按产品主轴拆开的路线，看：

- [03-workstreams.md](./03-workstreams.md)

如果你要看依赖顺序和阶段推进，看：

- [04-sequencing.md](./04-sequencing.md)

如果你要看“从现状一步步做到终局”的执行层总图，看：

- [10-execution-program.md](./10-execution-program.md)

如果你要按阶段逐步照做，看：

- [11-horizon-a-day-use.md](./11-horizon-a-day-use.md)
- [12-horizon-b-context-recovery.md](./12-horizon-b-context-recovery.md)
- [13-horizon-c-hud-productization.md](./13-horizon-c-hud-productization.md)
- [14-horizon-d-ai-assistance.md](./14-horizon-d-ai-assistance.md)
- [15-horizon-e-platform-and-delivery.md](./15-horizon-e-platform-and-delivery.md)
- [16-horizon-f-frontier-capabilities.md](./16-horizon-f-frontier-capabilities.md)

如果你要看现有文档体系和归属，看：

- [05-document-map.md](./05-document-map.md)
- 如果你要看 Gate A 的 repo-owned 日用操作面，看：
  [docs/day-use/README.md](../day-use/README.md)

如果你要看后续设计应继续依赖哪些结构锚点，看：

- [06-architecture-anchors.md](./06-architecture-anchors.md)

如果你要看推进过程中不能踩穿的边界，看：

- [07-guardrails.md](./07-guardrails.md)

如果你要看 `docs/past/` 中哪些还能当来源、哪些只能当历史材料，看：

- [08-doc-freshness-audit.md](./08-doc-freshness-audit.md)

## 当前总判断

按代码和测试看，Flow 已经完成了三件关键事情：

- 仓库与运行边界已经拆清
  - `backend/`、`frontend/`、`shared/` 各自承担明确职责
- 后端主任务流已经收口到单一 runtime
  - `TaskFlowRuntime` 已承载任务生命周期主链，并有 local/daemon parity 测试
- Windows HUD 已有受测的产品运行路径
  - `windows` runtime profile 固定装配 `ipc-client + task-status`
- Gate A 的 day-use contract、baseline、runbook 和 smoke gate 已经发布并经过实现验证

按同一标准看，Flow 还没有到终局产品：

- 上下文恢复还停留在快照基础能力
- HUD 目前仍是 task-status MVP
- AI 仍是配置位与 stub
- 插件和交付路径都已有底座
  - Windows 侧也已有一条经核实的本地 launcher 链路
- 但这些还不是完整、通用的产品交付面
  - Gate A 已经不再是“待补文档”的阶段，而是已发布的单机日用闭环基线

## 使用规则

- `01-current-state.md` 只写今天已核实的实现状态。
- `02-north-star.md` 只写终局产品定义。
- `03-workstreams.md` 和 `04-sequencing.md` 可以给出路线判断，但必须明确那是判断，不是现状。
- `06-architecture-anchors.md` 只保留能在当前代码里找到落点的结构锚点。
- `07-guardrails.md` 可以吸收历史文档经验，但要标明哪些是历史教训、哪些是当前实现约束。
- `docs/past/` 中的原文档默认不是当前事实来源，除非 `08-doc-freshness-audit.md` 明确说明仍然有效。
