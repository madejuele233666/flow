# 12B. Horizon B2 执行手册

状态基线：2026-04-22

目标：

**在不破坏 Gate B 语义模型的前提下，把“恢复报告”升级成真正的执行式恢复能力。Horizon B2 的第一责任不是做更丰富的 HUD，而是在 backend context 层补齐恢复执行边界、MVP 支持矩阵和可降级的动作报告。**

这一步位于 Horizon B 和 Horizon C 之间。
Horizon B 解决的是“恢复语义如何定义”，Horizon B2 解决的是“哪些语义会被真正执行恢复，以及如何优雅降级”。

相关的 browser/AW 单机实机验证记录见：

- [verification/aw-browser-capture-validation.md](./verification/aw-browser-capture-validation.md)

但这份记录只说明链路在样本机器上可行，不等于当前接入代码已经达到最终产品要求。
后续正式实现仍应重构成更解耦、更优雅、更泛用的形态。

## 一. 阶段目标

Horizon B2 完成时，系统至少应做到：

- 已存在一条独立于 HUD 的恢复执行边界
- `TaskFlowRuntime` 不直接承载应用特定恢复逻辑
- 已固定第一版可执行恢复支持矩阵
- `start / resume` 的恢复结果能区分：
  - 已执行恢复
  - 跳过恢复
  - 不支持恢复
  - 执行失败但已降级
- 恢复失败仍不破坏主任务流

## 二. 当前前置

今天已经有：

- semantic snapshot model
- declarative capture / restore policy
- 显式挂载与被动轨迹
- `RestoreResult` 与 `restore_report`
- `start_task` / `resume_task` 上的恢复调用点

今天还没有：

- 真正执行式恢复的 backend boundary
- 应用特定恢复 adapter / executor
- 固定的 MVP 支持矩阵
- 动作级恢复报告
- 对“不支持恢复”的稳定产品语义

## 三. 这一步不做什么

- 不把应用特定恢复逻辑塞进 `TaskFlowRuntime`
- 不在 HUD 内实现真正恢复
- 不把显式挂载和被动轨迹重新混回 snapshot
- 不承诺完整桌面回放
- 不承诺任意应用都可恢复
- 不为了追求覆盖率而破坏可解释降级

## 四. 顺序步骤

### Step B2.1：定义恢复执行边界

目标：

- 把“恢复计划”和“恢复执行”从 runtime 主流程中拆出来，形成单一可替换边界。

要做的事：

- 定义恢复动作的最小抽象：
  - 恢复目标
  - 动作类型
  - 优先级
  - 支持状态
  - 执行结果
- 明确 runtime 只负责：
  - 读取 snapshot
  - 生成恢复计划
  - 调用 executor boundary
  - 吸收失败并返回报告
- 明确 app-specific adapter 只负责真正调用系统或应用恢复。

交付物：

- 一份 recovery execution contract
- 一份 planning / execution boundary 表

验证：

- 恢复计划到执行边界的映射测试
- runtime 不直接依赖应用特定恢复实现的边界检查

完成门槛：

- 后续新增恢复能力不需要把逻辑散回 `TaskFlowRuntime`。

### Step B2.2：固定 MVP 支持矩阵

目标：

- 先明确“第一版真正恢复什么”，而不是模糊承诺完整工作现场恢复。

建议第一版只覆盖：

- `active_url`
- 有界的 `open_tabs` browser session restore
- `active_file`
- `active_workspace`
- 有限的 `active_window` 聚焦

这里要额外固定一条 browser-specific 要求：

- 对浏览器场景来说，只恢复一个 `active_url` 不能算“网页恢复已可用”。
- 第一版必须支持有界的多页面恢复，而不是无限制承诺“全量 tab 回放”。
- browser restore field contract 需要先固定成三层：
  - `active_url`
    - 含义：任务被 capture 时的主活动页
    - 责任：表达“切回任务后首先应该回到哪里”
    - 恢复要求：优先恢复，失败也要单独报出
  - `open_tabs`
    - 含义：同一浏览器 session 中计划参与恢复的附加页面集合
    - 责任：表达“这次工作现场除了主页面之外还要一起回来什么”
    - 恢复要求：做 bounded session restore，可按上限裁剪，但不能静默丢失语义
  - `recent_tabs`
    - 含义：最近切换过、但不承诺恢复的浏览历史片段
    - 责任：服务回看、提示与 fallback，不直接等同于 restore set
    - 恢复要求：默认不作为强恢复集合，除非后续策略显式提升
- 最小要求应是：
  - 能持久化当前活动页之外的额外页面集合
  - 能在恢复时批量 reopen 多个页面
  - 能区分主活动页恢复与附加页面恢复
  - 能对超出上限的页面做稳定降级
- 这一步要求的是 bounded session restore，不是完整浏览器状态克隆。

这一步暂不承诺：

- 全量 `open_windows`
- 无上限的 `open_tabs`
- 全量 `open_files`
- 任意第三方应用内部状态重建

交付物：

- 一份 recovery support matrix
- 一份 supported / unsupported / best-effort 字段表

验证：

- 支持矩阵驱动测试
- 对不支持字段返回稳定降级结果的测试

完成门槛：

- 再没有“到底哪些字段会被真正恢复”的歧义。
- browser session restore 已明确不是“只 reopen 一个 URL”。
- `active_url`、`open_tabs`、`recent_tabs` 的职责边界已经固定，不再混用。

### Step B2.3：实现 executor registry 与 MVP adapter

目标：

- 把执行式恢复落成可运行的最小能力，而不是只停在 contract。

要做的事：

- 定义 executor registry
- 为不同动作类型接入独立 adapter
- 先实现最有价值的最小恢复器：
  - active URL opener
  - bounded tab session opener
  - file opener
  - workspace opener
  - window focus best-effort adapter
- 对浏览器恢复明确 action 拆分：
  - 恢复主活动页
  - 恢复附加页面集合
  - 对超过上限或不支持的页面返回 degrade / unsupported，而不是静默丢弃
- `recent_tabs` 默认不进入 executor 主路径，只进入：
  - fallback 提示
  - trail / history surface
  - 后续可选的“补开最近页面”交互

验证：

- fake adapter 测试
- 不同 adapter 的失败隔离测试
- operator 级恢复 smoke
- browser multi-page restore smoke：
  - 2 个页面可被稳定 reopen
  - 部分页面失败时主任务流不被阻断
  - 恢复报告能表达 `restored 1/N`、`restored N/N`、`restored active only`

完成门槛：

- 至少一组真实恢复动作已经能在主流程中被执行。
- 浏览器恢复至少已覆盖 bounded multi-page reopen，而不是停留在单 URL reopen。

### Step B2.4：把 `restore_report` 升级成动作级恢复报告

目标：

- 避免“语义上说恢复了，但实际上并没有执行动作”。

要做的事：

- 在现有 `restore_report` 基础上增加动作级结果表达：
  - planned
  - executed
  - skipped
  - unsupported
  - failed
- 明确哪些字段仍只保留语义层结果，哪些字段要求动作级结果。
- 保持 start / resume payload 可消费且可降级。
- 对 browser session restore，报告至少要能表达：
  - 主活动页是否已恢复
  - 附加页面计划恢复多少个
  - 实际恢复多少个
  - 哪些页面被降级 / 跳过 / 失败
  - `recent_tabs` 是否仅作为回看信息存在，而未进入恢复计划

交付物：

- 一份 restore report contract v2

验证：

- `start_task` / `resume_task` payload contract 测试
- action-level report 渲染前置测试

完成门槛：

- 上层已经能分清“只是有语义”和“真的执行过恢复”。

### Step B2.5：固定降级与 fallback 语义

目标：

- 让执行式恢复失败时仍然保持产品语义，而不是退回技术事故。

要做的事：

- 明确 unsupported 的表现
- 明确 adapter failure 的表现
- 明确 mounts / trails 在恢复失败时的 fallback 位置
- 明确通知与日志边界

验证：

- unsupported action 测试
- executor failure 不阻断状态迁移测试
- mounts / trails fallback 语义测试

完成门槛：

- 真实恢复失败时，用户仍能获得稳定 fallback，而不是只看到异常碎片。

## 五. Horizon B2 的阶段门

只有同时满足下面这些条件，才算通过 Gate B2：

- 恢复执行边界已经独立存在
- MVP 支持矩阵已经固定
- 至少一组真实恢复动作已经可运行
- `restore_report` 已能表达动作级结果
- 恢复失败与不支持场景有稳定降级
- browser recovery 已支持 bounded multi-page restore，而不是只恢复 `active_url`

## 六. 进入 Horizon C 前必须确认的事

- HUD 要消费的是 B2 之后的恢复执行结果，而不是继续只看语义层 snapshot
- HUD 不应重新解释恢复支持矩阵
- 不支持或失败的恢复动作，仍要在 HUD 中有稳定表达
- HUD 需要能表达“恢复了 1 个页面”与“恢复了 3 个页面中的 2 个”的差别
- Horizon C 的职责是把这些结果做成产品面，而不是代替 backend 执行恢复
