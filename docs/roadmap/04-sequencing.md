# 推进顺序

这份文件回答的是“下一阶段怎么排”，不是“哪些模块更重要”。

这里的排序是路线判断，不是当前事实。

## 排序原则

当前排序遵守五条原则：

1. 先稳住已有主链，再叠加差异化能力。
2. 先做能直接改善日用体验的事情，再做外围生态。
3. 让新能力继续走现有 runtime / service / IPC 边界，不重开旁路。
4. 历史复盘里的教训可以当护栏，但不能当“已经完成”的证据。
5. 长期治理工程只能服务产品主线，不能反客为主。

## Horizon A：把当前主链做到可日用

### 目标

- 让后端主任务流、基本入口和 HUD task-status 路径形成稳定日用闭环。

### 当前依赖

- 这一步直接建立在当前已存在的 `TaskFlowRuntime`、IPC V2、Windows HUD runtime 上。

### 重点

- 默认配置
- CLI / daemon / HUD 的状态语义一致性
- 常见错误路径
- 日常启动与验证路径
  - 包括当前已存在的本地 launcher 链路，而不是只看 repo 内入口

### 为什么先做

如果这一步不够稳，后面的 context、HUD 强化、AI 都会建立在一个“能跑但不好用”的底座上。

## Horizon B：把 Context Recovery 做成差异化能力

### 目标

- 把现有 snapshot 底座升级成真正的任务恢复能力。

### 当前依赖

- 已有 `ContextService`、`SnapshotManager`、runtime-owned capture / restore。

### 重点

- snapshot 模型
- capture / restore 策略
- 显式挂载与隐式捕获的边界
- 恢复失败时的降级路径
- 被动 trail 与后续自动复盘所需的最小数据结构

### 为什么排第二

这是 Flow 和普通任务管理工具最容易拉开差距的地方，而且它已经有代码入口，不需要从零发明。

## Horizon C：把 HUD 从 MVP 做成产品

### 目标

- 在不破坏当前 runtime 的前提下，把 task-status MVP 升级成真正的桌面产品界面。

### 当前依赖

- 已有 `windows` runtime profile、`HudApp`、widget runtime、task-status controller。

### 重点

- 更成熟的状态表达
- 更清楚的离线、空态、活跃、休息建议反馈
- 轻量交互与视觉层次
- 保持 HUD runtime 的边界切分

### 为什么在 B 之后发力

HUD 现在已经能显示状态，但差异化体验最终要依赖更强的 context 语义。

### 并行说明

- B 和 C 可以部分并行。
- 但 C 不应先于 B 大规模扩写交互故事，否则很容易把 HUD 做成“漂亮但空”的状态面板。

## Horizon D：把 AI 作为增强器接进来

### 目标

- 让 AI 先解决一个清晰问题，而不是泛化为第二套系统。

### 当前依赖

- 已有 `AIConfig` 和 `breakdown_task` 入口。
- 当前仍没有真实 provider 实现。

### 重点

- `flow breakdown`
- provider boundary
- 超时、重试、错误分类
- 输出格式约束
- breakdown 之后再考虑 next-hop advisor

### 为什么不更早

AI 太早接入，会把主产品不稳定的问题伪装成“能力不足”。

## Horizon E：插件产品化与长期独立性

### 目标

- 用参考插件、边界治理和必要时的协议独立工程支撑长期演进。

### 当前依赖

- backend / frontend 的插件底座都已存在，但还没有形成丰富产品面。
- 当前也已有一条可用的机器特定 launcher 路径，可作为交付规则沉淀的现实样本。

### 重点

- 第一方参考插件
- 插件矩阵验证
- 交付规则沉淀
- 仅在条件成立时推进更重的协议独立工程

### 为什么排在后段

这部分重要，但当前用户价值最强的路径仍然是主任务流、context、HUD。

## Horizon F：外围入口与前沿放大器

### 目标

- 在主产品已经成立之后，再把 `docs/past/aim.md` 里的外围入口和前沿自动化能力接进来。

### 当前依赖

- 依赖前面各阶段已经收口：
  - task-flow semantics
  - context model
  - HUD product path
  - provider boundary
  - plugin surfaces

### 重点

- 消息网关接入
- 自动复盘与被动上下文轨迹
- MCP server 化
- 本地 RAG 记忆胶囊
- 主动条件轮询

### 为什么放最后

这些方向可以形成护城河，但如果主产品没先做稳，它们只会把系统推向更复杂的未完成态。

## 推荐顺序

更接近当前代码现实的顺序是：

```text
Horizon A
  -> Horizon B
  -> Horizon C（与 B 局部并行）
  -> Horizon D
  -> Horizon E
  -> Horizon F
```

## 当前最合理的下一步

如果只抓一个阶段目标，建议是：

**先把 Horizon A 做稳，再让 Horizon B 和 Horizon C 形成第一版真正有差异化的产品闭环。**

## 现在不该抢跑的事情

- 把当前这条本地 launcher 路径直接写成通用分发能力
- 没有真实 provider 之前同时做多种 AI 供应商特性
- 在缺少参考插件时过早讲开放生态
- 为了“长期优雅”先启动大规模协议/架构重抽象
