# 12. Horizon B 执行手册

状态基线：2026-04-15

目标：

**把今天的 snapshot 底座升级成真正的 Context Recovery 能力。**

这一步是 Flow 与普通任务管理器拉开差距的第一处关键门槛。

## 一. 阶段目标

Horizon B 完成时，系统应至少具备：

- 更清楚的 snapshot 数据模型
- 明确的 capture / restore 触发规则
- 显式挂载与隐式捕获的边界
- 恢复失败时的优雅降级

## 二. 当前前置

今天已经有：

- `ContextService`
- `SnapshotManager`
- `ActivityWatchPlugin`
- `TaskFlowRuntime` 中的 capture / restore 调用点

今天还没有：

- 足够丰富的数据模型
- 挂载能力
- 被动轨迹
- 恢复优先级策略

## 三. 这一步不做什么

- 不先做漂亮的上下文 UI
- 不先做 AI 驱动恢复建议
- 不先做外部消息入口
- 不把被动轨迹单独做成第二套系统

## 四. 顺序步骤

### Step B1：定义 snapshot 语义模型

目标：

- 让 snapshot 从“少量字段 + extra”进化成可持续扩展的数据模型。

要做的事：

- 把上下文分成至少三类：
  - 当前活动上下文
  - 可恢复上下文
  - 仅记录不恢复的上下文
- 明确哪些字段属于核心模型，哪些仍可放在扩展字段。

直接锚点：

- `backend/flow_engine/context/base_plugin.py`
- `backend/flow_engine/task_flow_runtime.py`

交付物：

- 一份 snapshot 字段表
- 一份字段分类规则

验证：

- 新模型不破坏现有 capture / restore 路径

完成门槛：

- snapshot 的核心字段不再只靠 `extra` 承载。

### Step B2：明确 capture / restore 时机

目标：

- 避免“什么时候抓、什么时候恢复”继续隐含在实现里。

要做的事：

- 明确下列场景的行为：
  - start
  - pause
  - resume
  - block
  - auto-pause
  - 非法 start / veto
- 明确哪些场景只 capture，哪些场景 capture + restore，哪些场景什么都不做。

直接锚点：

- `backend/flow_engine/task_flow_runtime.py`
- `backend/tests/test_task_flow_contract.py`

交付物：

- 一份 capture / restore 决策表

验证：

- 既有 snapshot degrade 测试
- 新增时机覆盖测试

完成门槛：

- 再没有“这个场景到底该不该抓快照”的歧义。

### Step B3：拆开显式挂载和隐式捕获

目标：

- 把用户主动绑定的资料，与系统自动记录的上下文分开建模。

要做的事：

- 定义显式挂载对象最小模型：
  - 路径
  - URL
  - 备注
  - 排序 / pin 语义
- 定义隐式捕获对象最小模型：
  - 来源
  - 时间
  - 恢复价值

交付物：

- 一份 mount model
- 一份 implicit capture model

验证：

- 二者不会混成一个不可解释的大字段

完成门槛：

- 用户主动保存的东西和系统被动记录的东西，在模型层已经分开。

### Step B4：引入 passive context trail

目标：

- 把 `aim` 里的“被动上下文轨迹”落成最小可用能力。

要做的事：

- 明确 trail 的最小采样粒度。
- 明确 trail 与 snapshot 的关系。
- 明确 trail 只记录什么，不负责什么。

建议先只做：

- 记录事件
- 与任务关联
- 时间序列可回看

先不做：

- 智能摘要
- AI 检索
- 富交互展示

完成门槛：

- 系统已经能说清“这个任务执行过程中接触过哪些上下文”。

### Step B5：定义恢复策略和降级策略

目标：

- 避免“恢复失败时行为不确定”。

要做的事：

- 定义恢复优先级：
  - 必须恢复
  - 尽量恢复
  - 只展示不恢复
- 定义失败降级：
  - 记录日志
  - 告诉用户可恢复信息缺失
  - 不破坏主任务流

交付物：

- 一份恢复优先级表
- 一份失败降级表

验证：

- 现有 degrade 测试
- 新增恢复优先级测试

完成门槛：

- 恢复失败时仍然是产品语义，不是技术事故。

## 五. Horizon B 的阶段门

只有同时满足下面这些条件，才算通过 Gate B：

- snapshot 模型已扩清
- capture / restore 时机已固定
- 显式挂载与隐式捕获已分开
- passive trail 已有最小模型
- 恢复优先级与降级策略已存在

## 六. 进入 Horizon C 前必须确认的事

- HUD 后续要展示的不是空洞状态，而是真实的上下文语义
- 新增上下文能力仍然挂在 `TaskFlowRuntime` / `ContextService` 路径上
