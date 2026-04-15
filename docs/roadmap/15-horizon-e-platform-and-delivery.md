# 15. Horizon E 执行手册

状态基线：2026-04-15

目标：

**把插件、交付路径和长期独立性从“有底座”推进到“可维护、可扩展、可交付”。**

## 一. 阶段目标

Horizon E 完成时，至少应做到：

- 有一批真实可用的第一方参考插件
- launcher / 交付规则不再只是口口相传经验
- 长期协议治理有清楚触发条件

## 二. 当前前置

今天已经有：

- backend / frontend plugin registry
- plugin / admin context
- HUD lifecycle runtime
- 本地 operator launcher 样本
- IPC V2 契约

今天还没有：

- 第一方插件矩阵
- repo 内交付工具
- 通用分发能力
- 协议独立工程的明确触发门

## 三. 这一步不做什么

- 不把 operator-local launcher 直接包装成通用分发
- 不在没有参考插件前先讲开放生态
- 不为长期洁癖而抢跑协议拆仓

## 四. 顺序步骤

### Step E1：定义第一方参考插件集合

目标：

- 先证明插件是现实生产能力，而不是抽象框架。

要做的事：

- 列出最值得优先第一方插件化的能力。
- 每个候选都回答：
  - 为什么适合插件
  - 为什么不应继续留在主 runtime

验证：

- 现有锚点：
  - `frontend/flow_hud/runtime.py`
  - `frontend/flow_hud/core/app.py`
  - `frontend/tests/hud/test_widget_runtime.py`
- 新增验证：
  - 第一方插件候选评估表
  - 每个候选的 runtime-owned / plugin-owned 边界检查
- 真实运行验证：
  - 选出至少一个参考插件候选并走完一次接入评审

完成门槛：

- 有清楚的第一方插件优先级表。

### Step E2：补齐插件产品级验证

目标：

- 让插件从“能 setup”升级成“能长期维护”。

要做的事：

- 固定 `manifest.requires` 使用方式
- 固定 setup / teardown / cleanup 验证矩阵
- 固定失败隔离策略

验证：

- 现有锚点：
  - `frontend/tests/hud/test_ipc_client_plugin.py`
  - `frontend/tests/hud/test_widget_runtime.py`
  - `frontend/tests/hud/test_runtime_profiles.py`
- 新增验证：
  - `manifest.requires` 依赖矩阵测试
  - setup / teardown / cleanup 失败隔离测试
- 真实运行验证：
  - 人为制造插件 setup 失败与 teardown 异常，确认宿主仍可解释、可恢复

完成门槛：

- 插件失败不再造成宿主行为不确定。

### Step E3：把 launcher 经验制度化

目标：

- 把当前已核实的本地 launcher 经验变成可重复规则。

要做的事：

- 明确薄包装原则
- 明确脚本职责边界
- 明确 UTF-8 无 BOM、双环境、真实桌面验证等规则
- 明确哪些部分仍是机器绑定项

验证：

- 现有锚点：
  - `C:\\Users\\27866\\Desktop\\flow-hud-control.cmd`
  - `C:\\Users\\27866\\Desktop\\flow-hud-control.ps1`
  - `docs/past/windows-launcher-postmortem.md`
- 新增验证：
  - launcher 规则清单
  - Windows / WSL 双环境启动检查表
- 真实运行验证：
  - 按规则执行一次 `sync / start / status / stop`，确认经验已被文档化而非口头化

完成门槛：

- 交付规则已经清楚，但仍不冒充“通用分发已完成”。

### Step E4：收敛机器绑定项

目标：

- 把当前 launcher 里的硬编码变成显式配置面。

要做的事：

- 收敛 distro 名
- 收敛 repo 路径
- 收敛 target 路径
- 收敛端口与 runtime 参数

验证：

- 现有锚点：
  - `C:\\Users\\27866\\Desktop\\flow-hud-control.ps1`
  - `frontend/flow_hud/core/config.py`
  - `backend/flow_engine/config.py`
- 新增验证：
  - 机器绑定项参数表
  - 配置来源优先级检查
- 真实运行验证：
  - 用显式配置覆盖当前 launcher 硬编码项，确认链路仍可启动

完成门槛：

- operator-local 启动链路不再强绑定单一机器常量。

### Step E5：定义协议独立工程触发门

目标：

- 避免协议治理工程因为抽象冲动而抢跑。

要做的事：

- 固定触发条件：
  - 第二个非 Python 消费端
  - 共享 runtime 明显拖住发布节奏
  - 业务层开始外溢边界 import
- 固定未触发前的约束：
  - 不复制协议模型
  - 不在业务层拼裸帧

验证：

- 现有锚点：
  - `docs/past/ipc-protocol-v2.md`
  - `docs/past/ipc-product-first-guardrails.md`
  - `backend/tests/test_ipc_v2_server.py`
- 新增验证：
  - 协议独立触发门检查表
  - 业务层边界 import 审计规则
- 真实运行验证：
  - 以当前代码库跑一次触发门复查，确认在尚未到拆仓时机时仍能维持纪律

完成门槛：

- 长期治理已被制度化，而不是依赖临场判断。

## 五. Horizon E 的阶段门

只有同时满足下面这些条件，才算通过 Gate E：

- 第一方参考插件集合已明确
- 插件验证矩阵已存在
- launcher 规则已制度化
- 机器绑定收敛方案已存在
- 协议独立触发门已固定

## 六. 进入 Horizon F 前必须确认的事

- 交付与扩展已经足够稳，不会拖垮外围入口和前沿能力
