# 13. Horizon C 执行手册

状态基线：2026-04-15

目标：

**在不推翻现有 HUD runtime 的前提下，把 task-status MVP 升级成真正的桌面产品界面。**

## 一. 阶段目标

Horizon C 完成时，HUD 至少应做到：

- 不再只是显示当前任务标题
- 能表达状态、压力、建议和轻量交互
- 所有增强仍然走 `HudApp` 主路径

## 二. 当前前置

今天已经有：

- `windows` runtime profile
- `HudApp`
- transition runtime
- widget runtime
- task-status controller / widget

今天还没有：

- hover-to-interact
- 截止时间视觉表达
- Flowtime 提醒
- 更成熟的布局与状态层

## 三. 这一步不做什么

- 不重写 HUD 宿主
- 不把状态机塞回单个 widget
- 不在 UI 层直接解释 raw IPC
- 不为了炫技先做复杂动效系统

## 四. 顺序步骤

### Step C1：把 task-status 从 MVP 变成扩展基座

目标：

- 先让现有 task-status 卡片具备继续生长的空间。

要做的事：

- 把当前状态展示分成明确的子区域：
  - 当前任务
  - 状态标签
  - 时间信息
  - 建议区
- 明确哪些信息来自 backend status，哪些来自 HUD 内部推导。

交付物：

- 一份 task-status 信息结构表
- 对应的 widget 渲染约定

验证：

- 现有锚点：
  - `frontend/tests/hud/test_task_status_controller.py`
  - `frontend/tests/hud/test_task_status_plugin.py`
- 新增验证：
  - task-status 信息结构到 widget 子区域的映射测试
  - `active / empty / offline` 三态在新布局上的渲染稳定性检查
- 真实运行验证：
  - Windows HUD 中逐一切换 `active / empty / offline`，确认卡片布局不塌陷

完成门槛：

- 后续交互和视觉增强不需要重写整个 widget。

### Step C2：先补状态表达，再补复杂交互

目标：

- 先让 HUD 说清楚“现在发生了什么”，再让它“更会动”。

要做的事：

- 细化以下状态层：
  - active
  - empty
  - offline
  - break suggested
  - deadline pressure
- 明确每个状态至少需要哪些视觉信号。

验证：

- 现有锚点：
  - `frontend/tests/hud/test_task_status_controller.py`
  - `frontend/tests/hud/test_task_status_plugin.py`
- 新增验证：
  - 状态表达映射测试，覆盖 `break suggested` 与 `deadline pressure`
  - 不同状态组合下的信息优先级测试
- 真实运行验证：
  - 在真实 HUD 中注入上述状态，确认用户无需猜测就能读懂当前状态

完成门槛：

- HUD 的信息表达已经足够清晰，不靠用户猜。

### Step C3：把 hover-to-interact 接到现有 runtime

目标：

- 让 hover 成为 runtime 能力，而不是 widget 内偷做的行为。

要做的事：

- 先定义 hover 行为状态机。
- 明确 hover 只影响什么：
  - 可交互性
  - 透明度
  - 焦点获取
- 明确 hover 不影响什么：
  - 任务主语义
  - IPC 主路径
  - widget 注册语义

交付物：

- 一份 hover interaction contract

验证：

- 现有锚点：
  - `frontend/tests/hud/test_transition_runtime.py`
  - `frontend/tests/hud/test_widget_runtime.py`
- 新增验证：
  - hover 状态机测试
  - 鼠标穿透 / 焦点获取 / hover 超时阈值的交互 smoke
- 真实运行验证：
  - 在 Windows 桌面上验证 hover 前后透明度、交互性和焦点切换

完成门槛：

- hover 已是 HUD 宿主能力，而不是脆弱的 UI 偶发逻辑。

### Step C4：引入压力表达与柔性提醒

目标：

- 把 `aim` 中最有价值的两种 HUD 体验落成产品能力：
  - 截止时间压迫感视觉化
  - 柔性 Flowtime 提醒

要做的事：

- 定义 deadline pressure 输入来源。
- 定义 flowtime break 建议输入来源。
- 把这两类能力作为单独的状态输入，而不是塞进 task title 字符串。

验证：

- 现有锚点：
  - `frontend/tests/hud/test_task_status_controller.py`
  - `frontend/tests/hud/test_task_status_plugin.py`
- 新增验证：
  - deadline pressure 输入映射测试
  - flowtime break suggestion 定时与降级测试
- 真实运行验证：
  - 在真实桌面路径中确认 DDL 压力表达和休息提醒不会劫持用户输入

完成门槛：

- HUD 已能表达“该休息了”和“DDL 正在逼近”，但不劫持用户。

### Step C5：形成 HUD 组件规则

目标：

- 防止 HUD 继续边做边散。

要做的事：

- 固定 widget slot 设计规则。
- 固定哪些信息适合中心卡片，哪些适合边缘提示。
- 固定动画、输入监听、状态机和 IPC 的边界。

交付物：

- 一份 HUD composition rulebook

验证：

- 现有锚点：
  - `frontend/tests/hud/test_widget_runtime.py`
  - `frontend/tests/hud/test_runtime_profiles.py`
- 新增验证：
  - widget slot 组合规则 smoke
  - 动画 / 输入监听 / 状态机 / IPC 边界不串层检查
- 真实运行验证：
  - 在真实桌面上挂载多种 HUD 组件，确认布局规则与交互规则保持稳定

完成门槛：

- 后续任何 HUD 能力都知道应该挂在哪一层。

## 五. Horizon C 的阶段门

只有同时满足下面这些条件，才算通过 Gate C：

- task-status 已是扩展基座，不再只是一次性 MVP
- HUD 状态表达清楚
- hover-to-interact 已有宿主级契约
- pressure / break suggestion 已有产品语义
- HUD 组件规则已经固定

## 六. 进入 Horizon D 前必须确认的事

- HUD 已经具备足够产品感
- AI 接入后只是在放大体验，不是在替代缺失体验
