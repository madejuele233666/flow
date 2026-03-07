## 新增需求 (ADDED Requirements)

### 需求：异步 IPC 连接 (Asynchronous IPC Connection)
HUD 应通过 UNIX 套接字（或平台等效的 TCP）建立与中央心流引擎 (Flow Engine) 守护进程的异步 IPC 客户端连接，并使用 JSON-Lines 协议。

#### 场景：连接到引擎
- **当** HUD 应用程序启动时
- **则** 它成功连接到守护进程并开始监听事件推送

### 需求：任务状态同步 (Task State Synchronization)
HUD 应订阅并反映源自心流引擎的任务相关事件，特别是 `task.state_changed` 和 `timer.tick`，并将其映射到其 UI 可观测项。

#### 场景：接收计时器跳动
- **当** 心流引擎发出包含更新限制的 `timer.tick` 消息时
- **则** IPC 客户端解析该跳动并强制 UI 标签反映准确的剩余时间

### 需求：交互指令推送 (Interactive Commands Push)
HUD 应将用户对可操作 UI 组件的交互式点击转换为正确的 IPC 方法调用，并高效地分发给心流引擎。

#### 场景：完成任务
- **当** 用户在交互态 (Command Center Mode) 下点击明确的“完成”按钮时
- **则** HUD 分发一个 `task.done(task_id)` JSON-RPC 调用，并在收到成功确认后做出视觉反馈

