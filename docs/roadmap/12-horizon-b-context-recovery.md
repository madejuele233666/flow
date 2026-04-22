# 12. Horizon B 执行手册

状态基线：2026-04-20

目标：

**把 snapshot 底座升级成真正的 Context Recovery 能力。这个目标已经完成，Gate B baseline 已形成。**

这一步是 Flow 与普通任务管理器拉开差距的第一处关键门槛。

## 一. 阶段结果

Horizon B 现在已经具备：

- 分层的 semantic snapshot model，并带 `schema_version`
- declarative capture / restore policy 与明确的生命周期触发规则
- 与快照解耦的显式挂载能力
- 纳入主 context path 的 passive context trail
- 结构化恢复结果、恢复优先级和分级降级策略

## 二. 当前落点

当前已经落地：

- `Snapshot` 已按 Active / Restorable / Record-Only 三层建模，核心字段不再靠 `extra` 承载。
- `CaptureRestorePolicy` 已成为 capture / restore 时机的单一事实来源，`done_task` 也会 capture。
- `MountService` 与 CLI `flow mount / unmount / mounts` 已把显式挂载从 snapshot 中拆开。
- `TrailStore` / `TrailCollector` 已提供 task-bound passive context trail，`ActivityWatchPlugin` 是默认 collector。
- `RestoreResult`、`RecoveryPriority` 和四级 degradation chain 已形成；`start_task` 会返回 `restore_report`，恢复失败不会阻塞状态迁移。
- ActivityWatch browser capture 现在已经能稳定记录时间序列上的 `active_url` 与页面切换，但 `open_tabs` / `recent_tabs` 还没有固定成 canonical snapshot contract。
- 对应的单机实机验证记录见：
  - [verification/aw-browser-capture-validation.md](./verification/aw-browser-capture-validation.md)

当前不再缺少模型与策略本身；下一阶段缺的是把这些语义真正用进 HUD、报表和后续 AI 能力。

## 三. 这一步不做什么

- 不把 Horizon B 的完成误写成“上下文产品面已经完成”
- 不在 HUD 层重做一套 mount / trail / recovery schema
- 不先做 AI 驱动恢复建议
- 不先做外部消息入口

## 四. 已完成步骤

### Step B1：snapshot 语义模型已落地

结果：

- `Snapshot` 已从“少量字段 + extra”进化成可持续扩展的数据模型。
- Active Context、Restorable Context、Record-Only Context 已有明确字段归类。
- `schema_version` 已用于向后兼容旧快照加载。

对应规格：

- `openspec/specs/context-semantic-model/spec.md`

### Step B2：capture / restore 时机已固定

结果：

- `CaptureRestorePolicy` 已把 start、pause、resume、block、done、auto-pause、manual 等触发条件收口到同一声明式策略。
- `TaskFlowRuntime` 负责委托给策略，而不是把合法路径写死在流程分支里。
- `done_task` 现在也会生成最终 snapshot。

对应规格：

- `openspec/specs/capture-restore-policy/spec.md`

### Step B3：显式挂载与隐式捕获已解耦

结果：

- `MountService` 已提供 file / URL / note 三类持久挂载。
- 挂载数据存储在独立目录，不与 snapshots 混写。
- CLI 已暴露 `flow mount`、`flow unmount`、`flow mounts`，并预留了 HUD 后续 IPC action 名称。

对应规格：

- `openspec/specs/explicit-mount/spec.md`

### Step B4：passive context trail 已纳入主模型

结果：

- `TrailStore` 已把 trail 作为独立于 snapshot 的时间序列事件存储。
- `TrailCollector` 已提供开放接口，默认由 `ActivityWatchPlugin` 产出 trail events。
- trail 仍由 capture cycle 驱动，但存储与 snapshot 成败解耦。

对应规格：

- `openspec/specs/passive-context-trail/spec.md`

### Step B5：恢复优先级与降级策略已形成

结果：

- `RecoveryPriority` 已把语义字段划分为 `MUST_RESTORE`、`BEST_EFFORT`、`DISPLAY_ONLY`。
- `RestoreResult` 已统一表达 restored / degraded / failed / user_message。
- full / partial / display-only / empty 四级降级已固定，通知行为不阻塞状态迁移。

对应规格：

- `openspec/specs/recovery-degradation-strategy/spec.md`

## 五. Horizon B 的阶段门

Gate B 已通过，且同时满足下面这些条件：

- snapshot 模型已扩清
- capture / restore 时机已固定
- 显式挂载与隐式捕获已分开
- passive trail 已有最小模型
- 恢复优先级与降级策略已存在

验证证据已归档于：

- `openspec/changes/archive/2026-04-20-horizon-b-context-recovery/`
- `openspec/changes/archive/2026-04-20-horizon-b-context-recovery/verification/artifact/`

## 六. 进入 Horizon B2 前必须确认的事

- 执行式恢复仍应建立在现有 `restore_report`、mounts、trails 语义之上，而不是另起一套上下文定义。
- 新增上下文能力仍然挂在 `TaskFlowRuntime` / `ContextService` 路径上。
- Horizon B2 要做的是补齐恢复执行边界，而不是回头重做 Gate B。
