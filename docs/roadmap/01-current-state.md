# 当前状态

状态基线：2026-04-15

这份文件只记录代码、测试和现行规格已经能支撑的结论。

## 一句话判断

Flow 已经有了可验证的后端主任务流、可用的 IPC V2 边界，以及 Windows HUD 的 task-status MVP；但上下文恢复、HUD 产品化、AI、分发与生态都还没有完成。

## 已验证事实

### 1. 仓库和运行边界已经拆清

- 仓库当前按 `backend/`、`frontend/`、`shared/` 分工。
- 后端工作区包含独立包、CLI、daemon、IPC、任务流 runtime。
- 前端工作区包含 HUD runtime 和 Windows 入口。
- `shared/flow_ipc` 仍是当前共享边界层的一部分，但路线图不再把它描述成最终形态。

这部分说明项目已经脱离早期混合原型状态。

### 2. 后端主任务流已经收口到单一 runtime

基于 `backend/flow_engine/task_flow_runtime.py` 和 `backend/tests/test_task_flow_contract.py`，现在可以确认：

- `add -> start -> pause -> block -> resume -> done -> status` 这条链由 `TaskFlowRuntime` 统一编排。
- `LocalClient` 和 `RemoteClient` 共享同一套任务流语义，而不是两套业务真相。
- 单一活跃任务约束是运行时规则，不是文档约定。
- 非法 start / resume、veto、并发 start 等场景都被测试覆盖。
- 上下文 capture 已接入 `pause` 路径，以及 `start / resume` 中的 auto-pause 场景；restore 当前发生在 `start / resume`，失败时会降级，不会打断主任务流。

这意味着后端已经有了继续叠加产品能力的主底盘。

### 3. 核心状态模型已经具备八维定义，但日用入口只覆盖其中一部分

基于 `backend/flow_engine/state/machine.py`，现在可以确认：

- 核心领域状态已经定义为：
  - `Draft`
  - `Ready`
  - `Scheduled`
  - `In Progress`
  - `Paused`
  - `Blocked`
  - `Done`
  - `Canceled`
- 单一 `In Progress` 的排他约束，与原始愿景文档里的“单一独占协议”方向一致。

今天还要保持克制的地方是：

- 当前日用主链真正稳定暴露给用户的，主要还是 `Ready / In Progress / Paused / Blocked / Done` 这一组路径。
- “八维状态模型已定义”不等于“八维产品体验已经全部完成”。

### 4. 上下文系统已经接入主链，但范围仍然有限

基于 `backend/flow_engine/app.py`、`backend/flow_engine/context/base_plugin.py`、`backend/flow_engine/context/aw_plugin.py`，现在可以确认：

- `FlowApp` 会在 context 启用时注册 `ActivityWatchPlugin`。
- `ContextService` 是 capture 的统一入口。
- `SnapshotManager` 已负责快照落盘与恢复。
- 当前快照模型仍然很小，核心字段只有 `active_window`、`active_url` 和 `extra`。

这说明“快照底座”已存在，但“完整工作现场恢复”还没有实现。

### 5. Git 持久化底座已经存在，但自动复盘与轨迹还没产品化

基于 `backend/flow_engine/storage/git_ledger.py`、`backend/flow_engine/app.py` 和 `backend/tests/test_task_flow_contract.py`，现在可以确认：

- `GitLedger` 已经是后端的版本控制实现。
- `FlowApp` 会把它接入主应用。
- 启用 git auto-commit 时，状态变更已经可以被自动提交验证覆盖。

今天还不能声称的是：

- 自动心流报表已经存在
- 被动上下文轨迹已经形成产品能力
- Git 账本已经等于完整的数据层体验

### 6. IPC V2 已实现并有跨端测试面

基于 `backend/tests/test_ipc_v2_server.py` 和 `frontend/tests/hud/test_ipc_client_plugin.py`，现在可以确认：

- 后端支持 `unix` 和 `tcp` 两种 transport。
- `session.hello`、角色区分、结构化错误、limits、heartbeat、`session.bye`、session closing push 都有测试。
- 前端 `ipc-client` 插件已经按 V2 边界发起 RPC 和 push 通道连接。
- HUD 侧已验证协议不匹配、daemon offline、超时、request id mismatch、重连等场景。

这意味着前后端之间已经有受测的稳定通信边界。

### 7. Windows HUD 已有明确的产品运行路径

基于 `frontend/flow_hud/runtime.py`、`frontend/flow_hud/windows_main.py`、`frontend/flow_hud/core/app.py`、相关 HUD 测试，当前可以确认：

- runtime profile 已区分 `desktop` 和 `windows`。
- `windows_main.py` 固定使用 `windows` profile。
- `windows` profile 当前装配的是 `ipc-client` 和 `task-status` 两个 repo-owned plugin。
- `HudApp` 已收口 transition、widget registration、plugin setup/shutdown、owner cleanup。
- transition runtime、widget runtime、service contract、runtime profile 都有专门测试。

这意味着 HUD 不再是“只靠手工演示的框架”，而是已经有一条清晰、可测试的产品路径。

### 8. task-status MVP 已具备最小产品语义

基于 `frontend/flow_hud/task_status/controller.py`、`frontend/flow_hud/task_status/models.py`、`frontend/tests/hud/test_task_status_controller.py`、`frontend/tests/hud/test_task_status_plugin.py`，当前可以确认：

- task-status 状态模型明确区分 `active / empty / offline`。
- controller 会把后端 `status` 响应与 IPC push 统一归一成 UI snapshot。
- 连接建立、连接丢失、timer tick、空任务、离线降级都有测试。
- HUD 当前真正面向用户的产品表达，主要就是这条 task-status 路径。

## 已有底座，但还不能写成“已经完成”

### 1. 上下文恢复还不是完整产品能力

今天已经有的是：

- capture / restore 入口
- ActivityWatch 集成
- 快照落盘
- 主链降级处理

今天还不能声称的是：

- 完整桌面现场恢复
- 稳定的恢复优先级策略
- 丰富的快照语义模型
- 显式/隐式挂载已经形成成熟产品体验
- 被动轨迹与回放产品体验

### 2. HUD 还是 MVP，不是终局界面

今天已经有的是：

- runtime profile
- canonical transition / widget runtime
- task-status widget
- IPC 驱动的在线状态刷新

今天还不能声称的是：

- hover-to-interact 已经成熟
- 多层视觉状态系统
- 完整压迫感/提醒产品体验
- 通用 HUD 插件平台

### 3. AI 仍是 stub

基于 `backend/flow_engine/config.py`、`backend/flow_engine/scheduler/gravity.py`、`backend/flow_engine/client.py`，现在可以确认：

- 已有 `AIConfig`。
- `FlowClient.breakdown_task()` 已有调用入口。
- `TaskBreaker` / `NextHopAdvisor` 仍是接口。
- 当前默认实现仍是 `StubBreaker` 和 `StubAdvisor`。

这部分只能算预留边界，不能算已接入产品能力。

### 4. 插件底座存在，但生态还没有形成

今天已经有的是：

- backend 有 `PluginRegistry`、`PluginContext`、`AdminContext`
- frontend 有 `HudPluginRegistry`、受限 plugin/admin context、host-owned lifecycle 管线
- HUD runtime 对 setup、teardown、owner cleanup、admin routing 有测试

今天还不能声称的是：

- 已经有丰富的第一方参考插件集
- 已经适合对外讲完整第三方生态
- 前端已经完全插件驱动

### 5. Windows 入口存在，但通用分发仍未成立

今天已经有的是：

- Windows HUD 入口 `python -m flow_hud.windows_main`
- 一个经核实的本地 launcher：
  - `C:\Users\27866\Desktop\flow-hud-control.cmd`
  - 实际语义由同目录 `flow-hud-control.ps1` 承载
- 这条 launcher 当前支持 `menu / status / start / restart / stop-frontend / stop-backend / stop-all / sync`
- 这条 launcher 会：
  - 把 `frontend/` 与 `shared/` 同步到 Windows 目标目录
  - 准备 Windows venv 与 WSL backend 环境
  - 生成 `hud_config.toml`
  - 通过 `flow daemon start` 启动 WSL backend
  - 通过 `python -m flow_hud.windows_main` 启动 Windows frontend
- 这条 launcher 与前端当前配置加载逻辑是对齐的：
  - launcher 设置 `HUD_DATA_DIR`
  - `HudConfig.load()` 会从该目录读取 `hud_config.toml`
- 历史 launcher 复盘文档

今天还不能声称的是：

- 通用交付方案已经完成
- 任意机器都能按同一路径稳定启动
- 当前 launcher 已经 repo 化、参数化并摆脱机器绑定
  - 当前脚本仍硬编码了 distro、WSL repo 路径、Windows target 路径和连接端口

更准确的现状表述是：

- 现在确实存在一条真实可用的本地 Windows/WSL 启动链路
- 但它仍是 operator-local launcher，不是通用分发方案

## 明确仍属于未来目标的部分

- 完整上下文恢复
- 显式/隐式挂载能力
- 更成熟的 HUD 交互与视觉系统
- 柔性 Flowtime 提醒
- 时间压迫感视觉化 HUD
- 自动心流报表与被动上下文轨迹
- AI 任务拆解与下一跳建议
- 参考插件矩阵与对外生态叙事
- 外部消息网关接入
- MCP / 本地 RAG / 主动轮询
- 稳定的 Windows/跨端交付方案

## 当前阶段结论

如果把阶段分成三层：

1. 有主链
2. 可日用
3. 有完整产品感

Flow 现在已经明确拥有第 1 层的大部分关键件，正在逼近第 2 层，但还没有进入第 3 层。
