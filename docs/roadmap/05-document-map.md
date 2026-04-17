# 文档地图

这份文件把当前仓库的文档体系分层，避免“愿景、现实、规范、复盘、治理”混成一锅。

## A. 愿景层

这些文档定义目标上限，不代表当前已经实现：

- `docs/past/aim.md`
  - 角色：原始终局产品白皮书
  - 状态：已归档，作为愿景源文档保留
  - 当前拆解入口：`docs/roadmap/02-north-star.md`、`docs/roadmap/09-capability-decomposition.md`
  - 支持：Horizon B / C / D / E / F

## B. 现实入口层

这些文档定义今天怎么安装、运行、验证：

- `README.md`
  - 角色：仓库导航
- `backend/README.md`
  - 角色：后端工作区入口
- `frontend/README.md`
  - 角色：前端工作区入口
- `docs/day-use/README.md`
  - 角色：Gate A 单机日用操作面
- `docs/day-use/task-flow-contract.md`
  - 角色：Gate A 任务流契约参考
- `docs/day-use/single-machine-baseline.md`
  - 角色：Gate A 单机基线
- `docs/day-use/operator-runbook.md`
  - 角色：Gate A 运维手册
- `docs/day-use/gate-a-smoke.md`
  - 角色：Gate A smoke gate

它们主要支持：

- Horizon A

## C. 现行路线图层

这是当前应该优先维护的文档面：

- `docs/roadmap/README.md`
- `docs/roadmap/01-current-state.md`
- `docs/roadmap/02-north-star.md`
- `docs/roadmap/03-workstreams.md`
- `docs/roadmap/04-sequencing.md`
- `docs/roadmap/05-document-map.md`
- `docs/roadmap/06-architecture-anchors.md`
- `docs/roadmap/07-guardrails.md`
- `docs/roadmap/08-doc-freshness-audit.md`
- `docs/roadmap/09-capability-decomposition.md`
- `docs/roadmap/10-execution-program.md`
- `docs/roadmap/11-horizon-a-day-use.md`
- `docs/roadmap/12-horizon-b-context-recovery.md`
- `docs/roadmap/13-horizon-c-hud-productization.md`
- `docs/roadmap/14-horizon-d-ai-assistance.md`
- `docs/roadmap/15-horizon-e-platform-and-delivery.md`
- `docs/roadmap/16-horizon-f-frontier-capabilities.md`

它们共同承担：

- 当前事实
- 终局定义
- 推进顺序
- 架构锚点
- 执行护栏
- 文档审计
- 愿景能力拆解
- 执行层总图
- 分阶段 playbook

## D. 历史原文档层

这些文档不再作为现行真相面维护，而是保留为原始资料和历史上下文。
它们内部有些内容仍然有价值，但必须先经过代码核对或 `08-doc-freshness-audit.md` 分类后，才能重新进入 roadmap 正文。

- `docs/past/architecture.md`
- `docs/past/ipc-protocol-v2.md`
- `docs/past/plugin-system-future-direction.md`
- `docs/past/plugin-system-future-direction.zh-CN.md`
- `docs/past/ai_model_invocation_guide.md`
- `docs/past/ipc-independent-dev-playbook.md`
- `docs/past/ipc-product-first-guardrails.md`
- `docs/past/hud-v1-postmortem.md`
- `docs/past/windows-launcher-postmortem.md`
- `docs/past/ai_architecture_guidelines.md`
- `docs/past/aim.md`
- `docs/past/unified-roadmap.md`

这些文档的用途是：

- 提供原始上下文
- 保留历史判断
- 保留完整长文细节
- 允许后续核对“这个判断是从哪里来的”

## E. OpenSpec 规格层

这些规格是“必须满足的约束”，不是随意参考：

### 仓库与打包

- `repo-frontend-backend-layout`
- `backend-standalone-package`
- `hud-standalone-package`

### 后端主链

- `task-flow-runtime`
- `tcp-ipc-transport`
- `ipc-protocol-v2-contract`

### 前端主链

- `ipc-client`
- `hud-plugin-runtime-lifecycle`
- `hud-widget-composition-runtime`
- `hud-transition-runtime`
- `hud-task-status-mvp`
- `plugin-system`
- `hud-payload-integrity`
- `hud-plugin-sandbox-typed`
- `hud-service-contract`

### 治理与文档

- `architecture-documentation`
- `ai-architecture-guidelines`
- `artifact-verification`
- `ai-enforced-workflow`
- `change-repair-loop`

## F. Archive Change 时间线

这些 archive change 解释“项目实际上是怎么走到今天的”：

- `2026-03-06-document-architecture`
- `2026-03-07-hud-prototype`
- `2026-03-07-hud-reset`
- `2026-03-07-hud-separation`
- `2026-03-08-ai-arch-postmortem`
- `2026-03-08-hud-contract-and-sandbox-hardening`
- `2026-03-08-hud-typed-hook-registrar`
- `2026-03-08-hud-v2-architecture`
- `2026-03-09-ipc-client-plugin`
- `2026-03-11-redesign-ai-enforced-workflow`
- `2026-03-18-add-gemini-independent-verify-to-ai-enforced-workflow`
- `2026-04-05-separate-frontend-backend-projects`
- `2026-04-06-refactor-ipc-protocol-v2`
- `2026-04-12-harden-hud-plugin-runtime`
- `2026-04-14-frontend-mvp-task-hud`
- `2026-04-14-stabilize-core-task-flow`

## G. 使用规则

以后新增文档时，先判断它属于哪一层：

1. 愿景
2. 现实入口
3. 现行路线图
4. 历史原文档
5. 规格
6. 变更历史

如果层级没想清楚，就先不要把它并进路线图。

## H. 已经吸收到路线图目录的内容

下面这些历史原文档不只是“被引用”，而是它们的部分有效内容已经被重新组织到 roadmap 目录正文里。
这里的“吸收”不等于“照抄原判断”，而是指：

- 先核对代码和测试
- 再吸收仍然成立的部分
- 过时部分只作为历史背景保留

- `docs/past/architecture.md`
  - 已吸收到：`06-architecture-anchors.md`
- `docs/past/plugin-system-future-direction.md`
  - 已吸收到：`01-current-state.md`、`03-workstreams.md`
- `docs/past/hud-v1-postmortem.md`
  - 已吸收到：`03-workstreams.md`、`07-guardrails.md`
- `docs/past/ipc-product-first-guardrails.md`
  - 已吸收到：`04-sequencing.md`、`07-guardrails.md`
- `docs/past/windows-launcher-postmortem.md`
  - 已吸收到：`04-sequencing.md`、`07-guardrails.md`
- `docs/past/ai_architecture_guidelines.md`
  - 已吸收到：`07-guardrails.md`
- `docs/past/ai_model_invocation_guide.md`
  - 已吸收到：`03-workstreams.md`、`07-guardrails.md`
- `docs/past/aim.md`
  - 已吸收到：`02-north-star.md`、`03-workstreams.md`、`04-sequencing.md`、`09-capability-decomposition.md`
- `docs/day-use/*.md`
  - 已吸收到：`11-horizon-a-day-use.md` 的执行入口与 `10-execution-program.md` 的 Gate A 阶段门说明

原文档仍保留为历史依据和上下文来源，但现行真相应以 roadmap 目录和实际代码为准。
