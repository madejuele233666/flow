# 14. Horizon D 执行手册

状态基线：2026-04-17

目标：

**先把 AI 做成一个稳定的任务压缩器，再逐步扩到下一跳建议。**

## 一. 阶段目标

Horizon D 完成时，至少应做到：

- `flow breakdown` 已是真实能力
- provider boundary 清楚
- AI 失败时不会破坏主任务流

## 二. 当前前置

今天已经有：

- `AIConfig`
- `FlowClient.breakdown_task()`
- `TaskBreaker` / `NextHopAdvisor`
- `StubBreaker` / `StubAdvisor`

今天还没有：

- 真实 provider
- 输出协议
- 错误分类
- 稳定 next-hop advisor

## 三. 这一步不做什么

- 不同时支持大量 provider 特性
- 不把 AI 做成新的主任务系统
- 不在 breakdown 没稳定前急着做 advisor

## 四. 顺序步骤

### Step D1：锁定 AI 第一问题

目标：

- 明确第一阶段只解决一件事：任务拆解。

要做的事：

- 明确 breakdown 的输入。
- 明确 breakdown 的输出。
- 明确 output 允许的复杂度上限。

验证：

- 现有锚点：
  - `backend/flow_engine/client.py`
  - `backend/flow_engine/config.py`
- 新增验证：
  - breakdown 输入输出契约测试
  - 最大步骤数和字段上限测试
- 真实运行验证：
  - 通过 `flow breakdown` 跑一条真实任务拆解路径，确认第一阶段只解决拆解问题

完成门槛：

- 再没有“AI 先做拆解还是先做建议”的摇摆。

### Step D2：定义 provider boundary

目标：

- 让 AI 调用路径可替换、可测试、可降级。

要做的事：

- 定义 provider 调用接口。
- 定义 config 到 provider 的映射方式。
- 定义同步 / 异步调用边界。

直接锚点：

- `backend/flow_engine/config.py`
- `backend/flow_engine/scheduler/gravity.py`
- `backend/flow_engine/client.py`

验证：

- 现有锚点：
  - `backend/flow_engine/config.py`
  - `backend/flow_engine/client.py`
  - `backend/flow_engine/scheduler/gravity.py`
- 新增验证：
  - provider 适配层 contract test
  - config 到 provider 映射测试
  - 调用超时 / 取消 / 同步异步边界测试
- 真实运行验证：
  - 切换至少两组 provider 配置，确认上层 task-flow 语义不变

完成门槛：

- 后续接真实模型时，不需要改动上层 task-flow 语义。

### Step D3：定义 breakdown 输出协议

目标：

- 避免 AI 输出变成自由文本垃圾桶。

要做的事：

- 固定 breakdown 输出最小 schema。
- 固定最大步骤数、字段规则和失败回退。

验证：

- 现有锚点：
  - `backend/flow_engine/client.py`
  - `backend/flow_engine/config.py`
- 新增验证：
  - breakdown 输出 schema 校验测试
  - 非法输出到降级路径的恢复测试
- 真实运行验证：
  - 用真实 provider 或 stub 输出多组结果，确认系统都能稳定消费或降级

完成门槛：

- 系统能稳定消费 breakdown 结果。

### Step D4：补齐失败处理

目标：

- 让 AI 成为增强器，而不是脆弱点。

要做的事：

- 定义超时
- 定义重试
- 定义 provider 错误分类
- 定义降级回 stub / 手工路径

验证：

- 现有锚点：
  - `backend/flow_engine/client.py`
  - `backend/flow_engine/config.py`
- 新增验证：
  - timeout / retry / 错误分类测试
  - provider 失败回 stub / 手工路径测试
- 真实运行验证：
  - 人为制造 provider 超时和错误响应，确认主任务流仍然可用

完成门槛：

- AI 调用失败时，主任务流照常可用。

### Step D5：第二阶段再做 next-hop advisor

目标：

- 在 breakdown 已经稳定之后，再引入建议能力。

要做的事：

- 明确 advisor 的输入：
  - 任务集
  - 当前上下文
  - 时间窗口
- 明确 advisor 的输出必须受约束。

验证：

- 现有锚点：
  - `backend/flow_engine/client.py`
  - `backend/flow_engine/scheduler/gravity.py`
- 新增验证：
  - advisor 输入约束测试
  - advisor 输出约束和失败降级测试
- 真实运行验证：
  - 在 breakdown 已稳定的前提下试跑 advisor，确认它不会退化成泛化聊天入口

完成门槛：

- advisor 不会成为一个“什么都能说”的泛化聊天接口。

## 五. Horizon D 的阶段门

只有同时满足下面这些条件，才算通过 Gate D：

- breakdown 已是可用能力
- provider boundary 已稳定
- 输出协议已固定
- 错误与降级已清楚
- advisor 进入第二阶段，而不是抢跑第一阶段

## 六. 进入 Horizon E 前必须确认的事

- AI 不会反向污染核心任务流
- 产品主线不是靠 AI 勉强补起来的
