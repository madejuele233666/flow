# 13. Horizon C 执行手册

状态基线：2026-04-22

目标：

**在不推翻现有 HUD runtime 的前提下，把 task-status MVP 升级成真正的桌面产品界面。Horizon C 的第一责任不是单纯做更漂亮的 HUD，而是把 Gate B / B2 的上下文语义与恢复执行结果变成用户可感知的产品表达。**

## 一. 阶段目标

Horizon C 完成时，HUD 至少应做到：

- 不再只是显示当前任务标题，而是能解释“现在发生了什么”
- 能把 `restore_report`、显式挂载、被动轨迹、节奏建议变成稳定可读的产品语义
- 能表达状态、压力、建议和轻量交互
- 所有增强仍然走 `HudApp` 主路径

## 二. HUD 输入面

Horizon C 不是直接消费原始 snapshot 文件，也不是在 HUD 里重新定义 context schema。
这一步应只消费下面五类稳定输入：

- `status`
  - 当前任务
  - 状态
  - 持续时长
  - `break_suggested`
- `restore_report`
  - `restored`
  - `degraded`
  - `failed`
  - `user_message`
  - action-level execution result
  - browser session restore summary
- `mount summary`
  - 挂载数量
  - 是否有 pinned 项
  - 首要挂载类型
- `trail summary`
  - 最近事件摘要
  - 最近活跃来源
  - 是否存在可回看轨迹
- HUD 内部推导状态
  - `offline`
  - `empty`
  - `restore_full`
  - `restore_degraded`
  - `restore_empty`
  - `deadline_pressure`

## 三. 当前前置

今天已经有：

- `windows` runtime profile
- `HudApp`
- transition runtime
- widget runtime
- task-status controller / widget
- `restore_report`
- 显式挂载与 `MountService`
- 被动轨迹与 `TrailStore`
- `break_suggested`

进入这一步前还应额外具备：

- B2 已提供执行式恢复边界
- 第一版 recovery support matrix 已固定
- `restore_report` 已能表达动作级恢复结果

今天还没有：

- 上下文恢复结果与执行结果的可见表达
- 挂载入口与最小 trail 回看入口
- hover-to-interact
- 截止时间视觉表达
- Flowtime 提醒
- 更成熟的布局与状态层

## 四. 这一步不做什么

- 不重写 HUD 宿主
- 不把状态机塞回单个 widget
- 不在 UI 层直接解释 raw IPC
- 不在 HUD 里重新定义 context schema
- 不直接消费原始 snapshot 字段替代 `restore_report`
- 不为了 hover 和动画延后上下文可见性
- 不把 mount / trail 做成第二套独立产品面
- 不为了炫技先做复杂动效系统

## 五. 顺序步骤

### Step C1：先把 task-status 从 MVP 变成上下文表达基座

目标：

- 先让现有 task-status 卡片具备继续生长的空间，并能容纳 Gate B / B2 已完成的输入。

要做的事：

- 把当前中心卡片固定成四个子区域：
  - 当前任务区
  - 恢复状态区
  - 时间 / 节奏区
  - 上下文入口区
- 明确每个区域的最小字段来源：
  - 当前任务区来自 `status`
  - 恢复状态区来自 `restore_report`
  - 时间 / 节奏区来自 `duration` 与 `break_suggested`
  - 上下文入口区来自 mount / trail summary
- 明确哪些信息来自 backend canonical payload，哪些来自 HUD 内部推导。
- 对浏览器恢复额外固定一条产品要求：
  - 恢复状态区不能只显示“已恢复 URL”
  - 当 backend 返回 browser session restore 结果时，HUD 要能表达：
    - 主活动页已恢复
    - 额外页面恢复了多少个
    - 是否存在部分降级
  - `recent_tabs` 不应伪装成“已恢复页面”，而应进入次级信息面：
    - 最近看过什么
    - 可回看但未恢复什么

交付物：

- 一份 HUD card information contract
- 一份字段到子区域映射表
- 一份 canonical payload 与 HUD derived state 边界表

验证：

- 现有锚点：
  - `frontend/tests/hud/test_task_status_controller.py`
  - `frontend/tests/hud/test_task_status_plugin.py`
- 新增验证：
  - `status`、`restore_report`、mount summary、trail summary 到 widget 子区域的映射测试
  - `active / empty / offline` 三态在新布局上的渲染稳定性检查
  - 恢复状态区和上下文入口区在缺字段时不塌陷的布局测试
  - browser multi-page restore summary 渲染测试
- 真实运行验证：
  - Windows HUD 中逐一切换 `active / empty / offline`
  - 在有恢复结果、有挂载、有 trail 的任务上确认卡片信息分区稳定
  - 在多页面恢复任务上确认 HUD 能表达 `已恢复 2/3 页面`，而不是退化成单 URL 提示

完成门槛：

- 后续交互和视觉增强不需要重写整个 widget。
- HUD 已经不再只消费 `status`。

### Step C2：先补上下文状态表达，再补复杂交互

目标：

- 先让 HUD 说清楚“上下文有没有回来、现在该注意什么”，再让它“更会动”。

要做的事：

- 细化以下状态层：
  - `active`
  - `empty`
  - `offline`
  - `restore_full`
  - `restore_degraded`
  - `restore_empty`
  - `break_suggested`
  - `deadline_pressure`
- 明确状态优先级：
  - `offline` 高于一切
  - `empty` 高于恢复态
  - `restore_degraded` 高于一般 active
  - `deadline_pressure` 与 `break_suggested` 不得淹没恢复告警
- 明确每个状态至少需要哪些视觉信号和文案强度。
- 对 browser multi-page restore 额外要求：
  - `restore_full` 包含“主页面 + 附加页面均恢复”
  - `restore_degraded` 包含“主页面已恢复，但附加页面仅部分恢复”
  - 不允许把“只恢复一个活动页”误显示成完整恢复
  - `recent_tabs` 的存在只能提升上下文丰富度，不能把 `restore_empty` 误判成 `restore_full`

验证：

- 现有锚点：
  - `frontend/tests/hud/test_task_status_controller.py`
  - `frontend/tests/hud/test_task_status_plugin.py`
- 新增验证：
  - 状态表达映射测试，覆盖 `restore_degraded`、`restore_empty`、`break_suggested` 与 `deadline_pressure`
  - 不同状态组合下的信息优先级测试
  - `restore_report.failed` / `restore_report.degraded` 驱动 warning / partial 状态的渲染测试
  - browser session `restored N/M` 到 `restore_full / restore_degraded` 的映射测试
- 真实运行验证：
  - 在真实 HUD 中注入上述状态，确认用户无需猜测就能读懂当前状态
  - 启动一个部分降级任务，确认 HUD 会表达“恢复不完整”而不是继续沉默

完成门槛：

- HUD 的信息表达已经足够清晰，不靠用户猜。
- 用户能在 HUD 中直接感知恢复成功、恢复降级和无可恢复上下文的差别。
- 用户能看懂“只回来一个页面”和“多页面工作现场大体回来”的区别。

### Step C3：给挂载与轨迹做最小产品入口

目标：

- 让用户知道“这个任务有上下文可用”，而不是让 mounts / trails 继续只存在于 backend。

要做的事：

- 先定义 mount summary 最小表达：
  - 数量
  - 是否有 pinned
  - 首要类型
- 先定义 trail summary 最小表达：
  - 最近事件存在性
  - 最近来源
  - 是否可回看
- 明确这一阶段只做入口提示，不急着做复杂浏览器式界面。

交付物：

- 一份 mount / trail minimal surface contract

验证：

- 现有锚点：
  - `frontend/tests/hud/test_task_status_plugin.py`
- 新增验证：
  - mount summary 渲染测试
  - trail summary 渲染测试
  - 有 mount 无 trail、有 trail 无 mount 时的入口表达测试
- 真实运行验证：
  - 在真实任务上确认用户能看见“有挂载 / 有轨迹”的入口提示

完成门槛：

- 用户已经知道当前任务是否带有可用上下文入口。

### Step C4：把 hover-to-interact 接到现有 runtime

目标：

- 让 hover 成为 runtime 能力，而不是 widget 内偷做的行为。

前置：

- C1-C3 已经完成，HUD 已具备稳定的上下文表达和入口层。

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

### Step C5：引入压力表达与柔性提醒

目标：

- 把 `aim` 中最有价值的两种 HUD 体验落成产品能力：
  - 截止时间压迫感视觉化
  - 柔性 Flowtime 提醒

前置：

- 恢复状态与上下文入口已经稳定可见，新增提醒不会淹没主语义。

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
  - 恢复状态与提醒并存时的信息优先级测试
- 真实运行验证：
  - 在真实桌面路径中确认 DDL 压力表达和休息提醒不会劫持用户输入

完成门槛：

- HUD 已能表达“该休息了”和“DDL 正在逼近”，但不劫持用户。

### Step C6：形成 HUD 组件规则

目标：

- 防止 HUD 继续边做边散。

要做的事：

- 固定 widget slot 设计规则。
- 固定哪些信息适合中心卡片，哪些适合边缘提示。
- 固定动画、输入监听、状态机和 IPC 的边界。
- 把恢复状态区和上下文入口区纳入固定构图约束，而不是按页面心情漂移。

交付物：

- 一份 HUD composition rulebook

验证：

- 现有锚点：
  - `frontend/tests/hud/test_widget_runtime.py`
  - `frontend/tests/hud/test_runtime_profiles.py`
- 新增验证：
  - widget slot 组合规则 smoke
  - 恢复状态区 / 上下文入口区位置约束测试
  - 动画 / 输入监听 / 状态机 / IPC 边界不串层检查
- 真实运行验证：
  - 在真实桌面上挂载多种 HUD 组件，确认布局规则与交互规则保持稳定

完成门槛：

- 后续任何 HUD 能力都知道应该挂在哪一层。

## 六. Horizon C 的阶段门

只有同时满足下面这些条件，才算通过 Gate C：

- task-status 已是上下文表达基座，不再只是一次性 MVP
- 用户能在 HUD 中看见恢复结果，而不必猜测上下文是否回来
- 用户能看见挂载与轨迹的最小入口提示
- HUD 状态表达清楚
- hover-to-interact 已有宿主级契约
- pressure / break suggestion 已有产品语义
- HUD 组件规则已经固定

## 七. 进入 Horizon D 前必须确认的事

- HUD 已经具备足够产品感
- 上下文语义已经被 HUD 消费，而不是仍然只停在 backend
- AI 接入后只是在放大体验，不是在替代缺失体验
