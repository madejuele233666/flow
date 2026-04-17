# 09. 愿景能力拆解

状态基线：2026-04-17

这份文件把 `docs/past/aim.md` 拆成可执行能力地图。

目的不是复述愿景，而是回答四个问题：

- `docs/past/aim.md` 里哪些方向仍然有价值
- 当前代码已经有哪些底座
- 这些方向应该挂进 roadmap 的哪一层
- 哪些内容绝不能误写成“已经实现”

## 一. Context Recovery And Mounting

### 愿景保留

- 系统级快照与任务恢复
- 显式挂载与隐式捕获并存
- 第一方恢复插件包
- 第三方恢复扩展 API

### 当前已验证底座

- `ContextService`
- `SnapshotManager`
- `ActivityWatchPlugin`
- `TaskFlowRuntime` 中的 capture / restore orchestration

### 已并入 roadmap 的位置

- `02-north-star.md`
- `03-workstreams.md` 的 Context Recovery
- `04-sequencing.md` 的 Horizon B

### 还不能写成现状的部分

- 完整桌面排布恢复
- 丰富的 snapshot 语义
- 显式/隐式挂载产品体验
- 成熟的恢复插件生态

## 二. Single-Task Protocol And State Model

### 愿景保留

- 八维状态模型
- 单一 `In Progress` 排他约束
- 自动压栈与自动切换

### 当前已验证底座

- `TaskState` 八维状态定义
- `TaskFlowRuntime`
- 单一活跃任务约束测试
- local / daemon parity 测试

### 已并入 roadmap 的位置

- `01-current-state.md`
- `02-north-star.md`
- `03-workstreams.md` 的 Core Task Loop

### 还不能写成现状的部分

- 八维状态已经全部变成稳定产品体验
- 所有状态都已在日常入口中完整暴露

## 三. Immersive HUD And Flowtime

### 愿景保留

- hover-to-interact
- 截止时间压迫感视觉化
- 柔性 Flowtime 提醒
- 轻量、无感的桌面 HUD

### 当前已验证底座

- `windows` runtime profile
- `HudApp`
- `TaskStatusController`
- task-status `active / empty / offline` MVP

### 已并入 roadmap 的位置

- `02-north-star.md`
- `03-workstreams.md` 的 HUD Experience
- `04-sequencing.md` 的 Horizon C

### 还不能写成现状的部分

- hover-to-interact 已经完成
- 截止时间视觉系统已存在
- Flowtime 提醒产品体验已完成

## 四. Ledger, Reporting And Trails

### 愿景保留

- Git 驱动账本
- 零点击复盘
- 被动上下文轨迹

### 当前已验证底座

- `GitLedger`
- auto-commit 测试覆盖
- context capture 基础设施

### 已并入 roadmap 的位置

- `01-current-state.md`
- `03-workstreams.md` 的 Reports, Trails And External Gateways
- `04-sequencing.md` 的 Horizon B / F

### 还不能写成现状的部分

- 自动心流报表已经存在
- 被动轨迹已经形成产品能力
- Git 账本已经等于完整的数据层体验

## 五. AI Task Compression

### 愿景保留

- 任务拆解
- 下一跳建议
- BYOK / provider 可替换

### 当前已验证底座

- `AIConfig`
- `FlowClient.breakdown_task()`
- `TaskBreaker` / `NextHopAdvisor` 接口
- `StubBreaker` / `StubAdvisor`

### 已并入 roadmap 的位置

- `01-current-state.md`
- `02-north-star.md`
- `03-workstreams.md` 的 AI Assistance
- `04-sequencing.md` 的 Horizon D

### 还不能写成现状的部分

- 真实模型调用已经接入
- next-hop advisor 已可稳定使用
- 多 provider 兼容已经完成

## 六. First-Party Bundles And Third-Party APIs

### 愿景保留

- 第一方基础插件包
- 面向社区的第三方扩展接口

### 当前已验证底座

- backend plugin registry / contexts
- frontend plugin registry / contexts
- HUD lifecycle / teardown / admin routing 测试

### 已并入 roadmap 的位置

- `02-north-star.md`
- `03-workstreams.md` 的 Plugin Surfaces
- `04-sequencing.md` 的 Horizon E

### 还不能写成现状的部分

- 已有成熟第一方插件矩阵
- 已能对外讲完整第三方生态

## 七. Messenger Gateway And External Intake

### 愿景保留

- 通过现成消息网关做低摩擦任务输入
- 远端自然语言或素材输入直达本地引擎

### 当前已验证底座

- 当前没有直接实现
- 可复用底座主要是 CLI、IPC、task-flow semantics

### 已并入 roadmap 的位置

- `02-north-star.md`
- `03-workstreams.md` 的 Reports, Trails And External Gateways
- `04-sequencing.md` 的 Horizon F

### 还不能写成现状的部分

- 已有 Telegram / 微信 / 其他网关接入
- 外部入口已经形成稳定产品链路

## 八. Frontier Interfaces

### 愿景保留

- MCP server 化
- 本地 RAG 记忆胶囊
- 主动条件轮询

### 当前已验证底座

- 当前没有直接实现
- 相关基础只体现在已有 daemon、context、AI、IPC 边界

### 已并入 roadmap 的位置

- `02-north-star.md`
- `04-sequencing.md` 的 Horizon F

### 还不能写成现状的部分

- MCP server 已存在
- 本地 RAG 已接入
- Blocked 主动轮询已接入

## 九. 处理原则

以后继续吸收 `docs/past/aim.md` 或类似愿景文档时，统一按下面规则处理：

1. 愿景句子先拆成能力名词，再决定放到哪条 workstream。
2. 任何写着 “current” 的段落，都必须重新对照代码后才能进入现状层。
3. 没有代码证据的内容，只能进入北极星、阶段路线或前沿设想层。
4. 同一能力同时写清三件事：
   - 当前底座
   - 目标能力
   - 还不能宣称的部分
