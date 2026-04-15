# 工作流主轴

这份文件按产品主轴拆分路线，不按历史时间线拆分。

其中每条主轴都分成三部分：

- 当前代码基线
- 下一阶段里程碑
- 退出标准

## Workstream A：Core Task Loop

### 当前代码基线

- `TaskFlowRuntime` 已统一承载任务主生命周期。
- `LocalClient` / `RemoteClient` parity 已有测试。
- 单一活跃任务约束、veto、并发 start、snapshot 降级都在测试面内。
- 核心领域里已经存在八维状态模型定义，但当前稳定日用主链只覆盖其中一部分。

### 下一阶段里程碑

- 把默认配置、错误表达、CLI/daemon 操作体验压实到“第一次使用也可靠”。
- 补齐日用层缺口，而不是继续在主链外侧加旁路。
- 让 HUD 与后端主链的用户语义对齐到同一份 status / task-flow 契约。
- 让“八维状态模型”逐步从领域定义变成真正被产品使用的能力，而不是只停在 enum 层。

### 退出标准

- 主任务流不再依赖“懂内部结构的人”才能稳定使用。
- 常见失败路径可以被解释，而不是只暴露底层异常。

## Workstream B：Context Recovery

### 当前代码基线

- `ContextService`、`SnapshotManager`、`ActivityWatchPlugin` 已接入。
- `TaskFlowRuntime` 当前会在 `pause` 与 `start / resume` 的 auto-pause 场景执行 capture，并在 `start / resume` 路径执行 restore。
- 当前快照模型仍偏基础，只覆盖少量上下文字段。

### 下一阶段里程碑

- 扩充 snapshot 数据模型，而不是继续依赖宽泛的 `extra`。
- 明确 capture / restore 在 start、pause、resume、auto-pause 下的行为。
- 明确“显式挂载内容”和“隐式捕获内容”的边界。
- 逐步把 passive trail 这类能力纳入上下文系统，而不是单独再造第二套记录系统。

### 退出标准

- 切回任务时，系统恢复的不只是任务标题，而是核心工作现场。
- 恢复失败时能清楚降级，不会污染主任务流。

## Workstream C：HUD Experience

### 当前代码基线

- `windows` runtime profile 当前装配 `ipc-client + task-status`。
- `HudApp` 已收口 transition、widget registration、plugin setup / teardown。
- `TaskStatusController` 已能稳定表达 `active / empty / offline`。
- HUD V1 的失败教训和几项关键技术结论都有历史复盘可用。

### 下一阶段里程碑

- 在现有 runtime 上继续做产品化，而不是另起一套 HUD 架构。
- 扩展 task-status 的状态表达、布局和交互，而不是只堆更多控件。
- 把 hover、提醒、轻量控制这类交互能力挂在既有 event / widget / state runtime 上。
- 逐步引入来自原始愿景文档的目标体验：
  - hover-to-interact
  - 截止时间压迫感视觉化
  - 柔性 Flowtime 提醒

### 退出标准

- HUD 看起来不再像技术验证件，而像可交付产品。
- 视觉与交互增强没有把状态机、IPC、动画、输入监听重新搅回一个模块。

## Workstream D：AI Assistance

### 当前代码基线

- `AIConfig` 已存在。
- `FlowClient.breakdown_task()` 已暴露任务拆解入口。
- `TaskBreaker` / `NextHopAdvisor` 仍是接口，默认实现仍是 stub。

### 下一阶段里程碑

- 先把 `flow breakdown` 做成一个真实可用的能力。
- 为 provider 接入定义清楚的超时、重试、错误分类和输出约束。
- 保证 AI 只增强任务流，不重新发明第二套任务系统。
- 下一跳建议应视为 breakdown 之后的第二阶段能力，而不是和第一阶段并发泛化。

### 路线判断

这里不把“某种 provider 方案”写成当前事实。
更合理的路线判断是：

- 先做程序内 provider boundary
- 先解决一个明确问题
- 先保证失败可降级

### 退出标准

- AI 失败不会破坏核心任务流。
- AI 输出可以被系统稳定消费，而不是只适合手工参考。

## Workstream E：Plugin Surfaces

### 当前代码基线

- backend 已有 `PluginRegistry`、`PluginContext`、`AdminContext`。
- frontend 已有 `HudPluginRegistry`、owner-aware context、runtime-owned lifecycle。
- HUD runtime 对 setup 顺序、admin routing、teardown cleanup、service contract 都有测试。
- 当前真实产品路径仍主要依赖 repo-owned plugins，而不是一个成熟的开放生态。

### 下一阶段里程碑

- 增加第一方参考插件，而不是先写生态宣言。
- 明确哪些能力适合插件化，哪些仍应留在主 runtime。
- 补齐 `manifest.requires`、依赖关系、失败隔离和测试矩阵的产品层使用案例。
- 让“第一方基础插件包 + 第三方扩展 API”成为真正的产品叙事，而不是只有抽象框架。

### 退出标准

- 插件不再只是“框架可扩展”，而是已经承载真实产品能力。
- 新能力能通过扩展点接入，而不是持续侵入核心编排层。

## Workstream F：Delivery, IPC And Independence

### 当前代码基线

- IPC V2 已是当前前后端联动边界。
- Windows HUD 入口已经存在。
- `shared/flow_ipc` 仍是当前接受中的共享边界层。
- 当前已核实存在一条本地 launcher 路径：
  - `flow-hud-control.cmd` 只是薄包装
  - `flow-hud-control.ps1` 承担 `sync / start / restart / stop / status`
  - 它会同步工作区、准备 Windows/WSL 环境、生成 runtime 配置并启动前后端
  - 它仍硬编码了 distro、repo root、target root 和连接参数
- 这条 launcher 路径属于当前现实，但仍不应被误写成通用分发事实。

### 下一阶段里程碑

- 稳住当前 Windows HUD + backend 的真实运行链路。
- 把当前 launcher 中已经被验证的 orchestration 规则沉淀成固定规则，但不把 launcher 变成产品逻辑层。
- 只在触发条件真正出现时，再推进更重的协议独立工程。

### 退出标准

- 交付路径可维护、可验证。
- 当前 launcher 中的硬编码和机器绑定项有明确收敛路径。
- 协议演进不再被共享运行时代码严重牵制。

## Workstream G：Reports, Trails And External Gateways

### 当前代码基线

- `GitLedger` 已存在，并已接入后端。
- 当前还没有自动心流报表、被动上下文轨迹或消息网关的直接实现。
- 可复用的底座主要是：
  - 任务流 runtime
  - context system
  - git ledger
  - CLI / IPC boundary

### 下一阶段里程碑

- 把 passive context trail 放进主产品数据模型。
- 定义零点击复盘所需的最小数据面，而不是先做漂亮报表。
- 评估消息网关接入，但让它复用既有 task-flow / IPC / service semantics，而不是另起控制面。

### 路线判断

这条主轴吸收了 `docs/past/aim.md` 中两类重要方向：

- 自动复盘与轨迹
- 低摩擦外部入口

它们都重要，但都不应早于 Core Loop、Context Recovery 和 HUD Experience。

### 退出标准

- 历史轨迹、自动复盘和外部入口不再依赖单独的第二套系统。
- 外部采集或远程触发仍然服从同一套任务流语义。

## 当前最关键的三条主轴

现在最值得优先投入的仍然是：

1. Core Task Loop
2. Context Recovery
3. HUD Experience

原因不是概念上更漂亮，而是这三条主轴已经构成当前代码里最接近产品闭环的部分。
