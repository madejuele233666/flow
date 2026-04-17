# 16. Horizon F 执行手册

状态基线：2026-04-17

目标：

**只在主产品已经成立之后，再把外围入口、自动复盘和前沿能力接进来。**

## 一. 阶段目标

Horizon F 覆盖三类能力：

- 外围入口
  - 消息网关
- 复盘放大器
  - 自动心流报表
  - 被动上下文轨迹的产品化
- 前沿接口
  - MCP
  - 本地 RAG
  - 主动条件轮询

## 二. 当前前置

这一步默认要求前五个阶段已经通过。

如果下面任何一条还没成立，Horizon F 默认不开工：

- Core Loop 不够稳
- Context Recovery 还没成形
- HUD 还停留在 MVP
- AI 第一能力还没落地
- 交付和插件还不够稳

## 三. 这一步不做什么

- 不把前沿能力当成当前主产品补丁
- 不在没有稳定数据模型前先做花哨展示
- 不让外围入口发明第二套命令语义

## 四. 顺序步骤

### Step F1：先做被动轨迹的产品化出口

目标：

- 把 B 阶段形成的 trail 数据真正变成可回看的能力。

要做的事：

- 定义最小回看视图
- 定义最小自动摘要材料
- 不急着做复杂 AI 检索

验证：

- 现有锚点：
  - `backend/flow_engine/context/base_plugin.py`
  - `backend/flow_engine/storage/git_ledger.py`
- 新增验证：
  - passive trail 最小导出格式测试
  - trail 到回看视图的数据映射检查
- 真实运行验证：
  - 完成一条真实任务后回看 trail 输出，确认用户能看懂发生过什么

完成门槛：

- 用户可以看懂“这段任务过程中发生了什么”。

### Step F2：再做零点击复盘

目标：

- 让 Git ledger、trail、任务时长形成自动复盘材料。

要做的事：

- 先定义复盘输入面
- 再定义复盘输出格式
- 最后才决定是否需要 AI 摘要增强

验证：

- 现有锚点：
  - `backend/flow_engine/storage/git_ledger.py`
  - `backend/tests/test_task_flow_contract.py`
- 新增验证：
  - 自动复盘输入聚合测试
  - 复盘输出格式与缺失字段降级测试
- 真实运行验证：
  - 从真实任务记录生成一次零点击复盘，确认不依赖人工整理

完成门槛：

- 复盘已经能在没有人工整理的前提下成立。

### Step F3：接入消息网关

目标：

- 给 Flow 增加低摩擦远端入口。

要做的事：

- 先固定外部入口允许做的事：
  - add
  - block
  - attach
  - capture note
- 再定义它们如何映射到既有 task-flow semantics

验证：

- 现有锚点：
  - `backend/flow_engine/client.py`
  - `backend/flow_engine/task_flow_runtime.py`
- 新增验证：
  - 外围入口到 task-flow 语义映射测试
  - 非法命令与幂等行为测试
- 真实运行验证：
  - 用一个真实消息入口样本触发 `add / block / attach / capture note`，确认它只是新入口不是新系统

完成门槛：

- 外部入口只是新入口，不是新系统。

### Step F4：评估 MCP server 化

目标：

- 在边界稳定后，再把 Flow 变成其他 AI 的上下文提供者。

要做的事：

- 先列出可以暴露的只读能力
- 再列出未来可暴露的读写能力
- 最后才决定协议暴露方式

验证：

- 现有锚点：
  - `docs/roadmap/02-north-star.md`
  - `docs/roadmap/06-architecture-anchors.md`
- 新增验证：
  - MCP 只读能力清单
  - 读写能力风险分级检查
- 真实运行验证：
  - 用最小只读样本检查一次 MCP 暴露面，确认没有反向侵入内部编排

完成门槛：

- MCP 是对既有系统的放大，而不是对内部结构的侵入。

### Step F5：最后才看本地 RAG 和主动条件轮询

目标：

- 只在数据、上下文和恢复能力已足够成熟时，才接更重的自动化。

要做的事：

- 先定义哪些任务值得形成 memory capsule
- 先定义主动轮询的边界与安全规则
- 明确这些能力的资源上限和失败降级

验证：

- 现有锚点：
  - `docs/roadmap/12-horizon-b-context-recovery.md`
  - `docs/roadmap/14-horizon-d-ai-assistance.md`
- 新增验证：
  - memory capsule 候选筛选规则
  - 主动轮询资源预算与失败降级测试计划
- 真实运行验证：
  - 用最小样本试跑一次本地 RAG 或主动轮询预演，确认不会把系统拖回实验态

完成门槛：

- 前沿能力不会把系统拖回实验态。

## 五. Horizon F 的阶段门

只有同时满足下面这些条件，才算通过 Gate F：

- 被动轨迹已有产品出口
- 零点击复盘已形成
- 外围入口复用既有语义
- MCP / RAG / 主动轮询只在稳定边界上扩展

## 六. 终局前的最后检查

只有当下面这些条件同时成立，才能说系统接近 `02-north-star.md` 中的终局版本：

- 单机主链稳定
- 上下文恢复成形
- HUD 产品化成立
- AI 第一能力成立
- 插件与交付稳固
- 外围入口和前沿能力没有重新制造第二套系统
