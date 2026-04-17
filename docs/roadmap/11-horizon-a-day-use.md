# 11. Horizon A 执行手册

状态基线：2026-04-17

目标：

**把今天已经存在的后端主任务流、IPC 边界、Windows HUD MVP 和本地 launcher 路径，收口成一个真正可日用的单机闭环。**

注：

- Gate A 对应的 repo-owned day-use contract、baseline、runbook、smoke gate 已经落地在 `docs/day-use/`。
- 下面的步骤仍保留为 Horizon A 的执行说明与回溯入口，但不再是“还没有文档”的状态描述。

这一步是整条路线的第一门。
如果这里没有做扎实，后面的 Context、HUD、AI 都只会叠在一个“不好用但能跑”的底座上。

## 一. 阶段目标

Horizon A 完成时，用户至少应满足下面三条：

- 能稳定完成日常任务的 add / start / pause / block / resume / done / status
- CLI、daemon、HUD 对“当前任务是什么”的表达一致
- Windows 路径和本地 operator launcher 可以重复验证

## 二. 当前前置

这一步已经具备的前置是：

- `TaskFlowRuntime`
- `FlowClient`
- IPC V2
- `windows` runtime profile
- task-status MVP
- 本地 `flow-hud-control` launcher 链路
- `docs/day-use/` 下的 Gate A contract、baseline、runbook、smoke gate

这一步不再缺少的是：

- 面向日用的默认配置标准已经发布并可验证
- 跨入口的一致错误表达已经冻结为 repo-owned contract
- 明确的 operator runbook 和 smoke gate 已经可执行

## 三. 这一步不做什么

- 不扩写 snapshot 语义
- 不做 hover HUD
- 不做 AI provider 接入
- 不做开放插件生态
- 不把本地 launcher 提前包装成通用分发

## 四. 顺序步骤

### Step A1：冻结主任务流真相面

目标：

- 明确今天真正可信的主链 payload 和状态语义，避免不同入口各说各话。

要做的事：

- 以 `TaskFlowRuntime` 为唯一主链真相整理任务生命周期返回值。
- 对齐 `LocalClient`、`RemoteClient`、HUD `status` 消费路径。
- 把“哪些字段是 canonical payload，哪些只是入口级显示字段”写清楚。

直接锚点：

- `backend/flow_engine/task_flow_runtime.py`
- `backend/flow_engine/client.py`
- `frontend/flow_hud/task_status/controller.py`
- `frontend/tests/hud/test_task_flow_contract.py`

交付物：

- 一份稳定的 task-flow payload 表
- 一份稳定的 status payload 表
- 与之对齐的跨入口文档说明

验证：

- `backend/tests/test_task_flow_contract.py`
- `frontend/tests/hud/test_task_flow_contract.py`

完成门槛：

- 再没有任何入口依赖“猜字段”工作。

### Step A2：统一错误表达和降级语义

目标：

- 让用户在 CLI、daemon、HUD 三处看到的失败都可解释。

要做的事：

- 梳理今天已经存在的错误类型：
  - 非法状态转移
  - 找不到任务
  - 多活跃任务
  - daemon offline
  - 协议不匹配
- 统一哪些错误应该暴露给用户，哪些只写日志。
- 统一“失败不破坏主链”的降级原则。

直接锚点：

- `backend/tests/test_task_flow_contract.py`
- `backend/tests/test_ipc_v2_server.py`
- `frontend/tests/hud/test_ipc_client_plugin.py`
- `frontend/flow_hud/task_status/controller.py`

交付物：

- 一份错误分类表
- 一份跨入口错误呈现规范

验证：

- 后端 parity 错误测试
- HUD offline / protocol mismatch 测试

完成门槛：

- 主要失败路径都能被解释成产品语言，而不是底层异常碎片。

### Step A3：固定单机日用配置基线

目标：

- 让第一次运行和重复运行都尽量走同一套最小配置。

要做的事：

- 确定 backend / frontend 默认配置中哪些值应被视为日用基线。
- 把当前 launcher 写入的关键运行参数整理成“当前本地 operator baseline”。
- 区分三类配置：
  - repo 默认值
  - operator-local 覆盖
  - 未来通用分发参数

直接锚点：

- `backend/flow_engine/config.py`
- `frontend/flow_hud/core/config.py`
- `C:\Users\27866\Desktop\flow-hud-control.ps1`

交付物：

- 一份单机运行配置说明
- 一份 operator-local launcher 参数说明

验证：

- clean config 启动
- HUD_DATA_DIR / `hud_config.toml` 读取一致

完成门槛：

- 不再需要靠口口相传记住启动参数。

### Step A4：稳定 operator runbook

目标：

- 把“会用的人脑内知识”变成可重复执行的 runbook。

要做的事：

- 写清 backend 单独启动路径。
- 写清 frontend 单独启动路径。
- 写清 launcher 路径的 `sync / start / restart / stop / status` 语义。
- 写清最小排障顺序：
  - backend 状态
  - frontend 状态
  - HUD 配置目录
  - IPC 连接状态

交付物：

- 一份单机 operator runbook
- 一份最小排障清单

验证：

- 按 runbook 从零执行一次
- 按 runbook 排查一次典型 offline 故障

完成门槛：

- 日用闭环不再依赖“问熟悉仓库的人”。

### Step A5：建立阶段 smoke 套件

目标：

- 让 Horizon A 有稳定的阶段通过标准。

要做的事：

- 明确 A 阶段最小测试集。
- 把“真实桌面入口验证”列成阶段 gate，而不是可选项。

最小测试集建议：

- backend:
  - `test_task_flow_contract.py`
  - `test_ipc_v2_server.py`
- frontend:
  - `test_task_flow_contract.py`
  - `test_task_status_controller.py`
  - `test_ipc_client_plugin.py`
  - `test_runtime_profiles.py`
- operator:
  - launcher `status`
  - launcher `start`
  - launcher `restart`
  - launcher `stop-all`

完成门槛：

- 每次进入下一个阶段前，都能先跑完这套 smoke。

## 五. Horizon A 的阶段门

只有同时满足下面这些条件，才算通过 Gate A：

- 主任务流 payload 已冻结
- 主要错误表达已统一
- 单机配置基线已清楚
- operator runbook 已存在
- smoke 套件已可重复执行

当前仓库状态：

- Gate A 的文档、配置收口、验证命令和手工证据已经到位。
- 这份文档现在更多承担路线回溯和后续阶段的前置引用作用。

## 六. 进入 Horizon B 前必须确认的事

- 当前主任务流没有未解释的语义分叉
- launcher 仍被视为 operator-local 工具，而不是通用分发
- HUD 目前仍只是 MVP，不提前承诺复杂交互
