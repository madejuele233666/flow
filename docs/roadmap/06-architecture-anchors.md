# 06. 架构锚点

这份文件不再把“层次图”当当前事实硬写。
它只保留能在现有代码中直接找到落点的结构锚点。

## 一. 当前可依赖的五个结构锚点

### 1. 端口安全的调用边界

当前可以直接指认的边界有：

- backend 的 `FlowClient`
- frontend 的 `HudLocalService`
- HUD 侧的 IPC plugin request boundary

这些边界的共同特征是：

- 输入输出保持基础类型或 `dict`
- 不向外泄漏内部 runtime 对象
- 便于本地调用和远程调用保持一致语义

### 2. canonical orchestrator 必须拥有产品语义

当前两个最关键的 orchestrator 是：

- backend 的 `TaskFlowRuntime`
- frontend 的 `HudApp`

后续所有产品语义都应尽量挂在这类入口上，例如：

- 任务生命周期
- snapshot capture / restore
- state transition
- widget registration
- plugin setup / shutdown

### 3. 防御型基础设施已经存在，不能绕开

当前代码里已经存在的防御机制包括：

- backend `EventBus` / `HookManager`
- frontend `HudEventBus` / `HudHookManager`
- thread-aware HUD runtime thread checks
- owner-scoped cleanup
- setup failure / teardown failure 隔离

新能力如果绕开这些东西，系统很容易重新长回高耦合状态。

### 4. 上下文与插件扩展面已经形成，但仍需产品化

当前已有：

- backend `ContextService` / `SnapshotManager`
- backend `PluginContext` / `AdminContext` / `PluginRegistry`
- frontend `HudPluginContext` / `HudAdminContext` / `HudPluginRegistry`

这意味着扩展面已经存在。
但“有扩展面”不等于“已经有成熟生态”，这点必须区分。

### 5. IPC 是明确边界，不是可随意穿透的工具层

当前可依赖的边界事实是：

- IPC V2 已经是前后端通信主边界
- transport、role、hello、limits、push/rpc 都已进入受测契约
- HUD 产品路径通过 `ipc-client` 插件消费这个边界

所以 IPC 应继续是边界，而不是让业务代码到处直接碰线协议细节。

## 二. 后续设计应继续遵守的结构判断

### 1. 外部入口继续走边界，不走内部对象

不要让 CLI、HUD、未来入口直接拿内部 repo、state machine、widget 树做业务。

### 2. 编排继续归 runtime / service 所有

不要把产品逻辑塞回：

- CLI 表现层
- launcher
- raw IPC handler
- 单个 widget 回调

### 3. 扩展点继续通过 context / registry / hook 暴露

不要为了临时提速，绕开 plugin context 或 owner-aware cleanup 直接把对象互相传透。

## 三. 各条主轴应优先落在哪些锚点

### Core Task Loop

- `FlowClient`
- `TaskFlowRuntime`
- backend 事件、钩子、存储

### Context Recovery

- `TaskFlowRuntime`
- `ContextService`
- `SnapshotManager`

### HUD Experience

- `windows` runtime profile
- `HudApp`
- task-status controller / widget runtime

### AI Assistance

- `FlowClient.breakdown_task`
- 未来 provider boundary
- backend runtime 降级路径

### Plugin Surfaces

- backend / frontend plugin registry
- plugin/admin context
- owner-aware lifecycle

### Delivery / IPC / Independence

- IPC V2 contract
- Windows HUD 入口
- 受控的 launcher / orchestration 边界
  - 包括当前已核实的本地 `flow-hud-control` 启动链路

## 四. 现在允许继续长的方向

- 在 `TaskFlowRuntime` 上继续强化主任务流
- 在 context 层扩充 snapshot 模型与恢复策略
- 在 `HudApp` 和 task-status 路径上继续做 HUD 产品化
- 在受限 plugin context 内补真实扩展点
- 在 IPC V2 边界内继续增强互通与验证

## 五. 现在仍然危险的方向

- UI 直接解释或拼装 raw IPC frame
- launcher 承担任务语义或 HUD 产品逻辑
- 业务层到处扩散 `flow_ipc` 细节
- 前后端复制一套协议模型
- 用“重写一遍”替代在现有 runtime 上迭代

## 六. 一句话锚点

后续工作应继续沿着“端口安全边界 + canonical orchestrator + 防御型基础设施 + 受控扩展面 + 明确 IPC 边界”这条线生长。
