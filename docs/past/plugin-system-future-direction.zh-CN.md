# 插件系统未来方向（翻译件）

原文档：[`plugin-system-future-direction.md`](./plugin-system-future-direction.md)

说明：本文件为翻译件，内容与原文档一致。若存在任何歧义、差异或需要确认的地方，请以原文档为准，并优先阅读原文档。

Date: 2026-04-06

## 目的

本文重新审视当前后端/前端插件系统，并将这份评估转化为项目下一阶段的实际方向。

重点不是单独判断插件抽象看起来是否干净。
真正的问题是：

- 插件是否已经接入真实的产品控制流？
- 后续功能是否可以通过扩展插件边界来实现，而不是重写核心模块？
- 哪些缺失项属于结构性阻塞，而不是可选的打磨？

## 执行摘要

简短结论：

- 后端插件基础可用。
- 前端插件基础只能算部分可用。
- 代码库尚未形成一个在前后端两侧都统一强健的插件平台。

更精确的判断：

- `backend/` 已经有真实的插件集成面，连接到状态迁移、hooks、通知、导出器、模板和排名因子。
- `frontend/` 具备不错的插件形状抽象，并且有一条强的、与生产相关的插件路径（`ipc-client`），但 HUD 插件系统还没有完全接到真实的 HUD 状态流和组件组合流上。

因此：

- 对于后端驱动的功能工作，当前基础已经足够继续；
- 对于 HUD 重型功能工作，当前基础还不够强；
- 下一阶段的架构优先级应该是补齐前端插件运行时路径，而不是重设计后端插件或进一步抽象 IPC。

## 当前状态图

```text
Backend
  FlowApp
    -> PluginRegistry
    -> PluginContext / AdminContext
    -> HookManager
    -> TransitionEngine
    -> real state transition lifecycle

Frontend
  HudApp
    -> HudPluginRegistry
    -> HudPluginContext / HudAdminContext
    -> HudHookManager
    -> runtime profiles
    -> IPC plugin works
    -> HUD state/widget lifecycle not fully wired
```

## 分侧评估

### 后端：作为扩展基础已经足够强

现有能力：

- 已存在基于 Manifest 的插件模型：`FlowPlugin` + `PluginManifest`。
- 已存在发现模型：`entry_points` 分组 `flow_engine.plugins`。
- 已存在隔离上下文：标准 `PluginContext` 和特权 `AdminContext`。
- 主机扩展点是真实且有意义的，不是装饰性的：
  - `register_hook(...)`
  - `register_notifier(...)`
  - `register_exporter(...)`
  - `register_factor(...)`
  - `register_template(...)`
- 插件 hooks 已通过 `TransitionEngine` 接入真实的迁移流程。
- Hook 执行具备真实的运行保护：
  - 超时
  - 每个处理器的熔断器
  - 多种执行策略
  - 安全模式和开发模式

这很重要，因为：

- 后端插件已经可以在不绕过核心边界的情况下影响真实系统行为；
- 未来的后端功能可以通过扩展来增加，而不是侵入式修改。

当前仍缺少的内容：

- 仓库里还没有真正使用这套系统端到端的第一方后端插件；
- 针对插件注册器/上下文生命周期本身的后端测试覆盖几乎没有；
- `manifest.requires` 里的插件依赖语义只是元数据存在，并未被主动强制；
- teardown 顺序不是反向顺序，而一旦插件之间存在依赖，这点可能很关键。

判断：

- 后端插件系统是一个有效基础；
- 但它还不是一个经过实战验证的插件生态。

### 前端：结构有前景，运行时现实不完整

已经做得不错的部分：

- HUD 插件基类、manifest、registry 和双上下文模型都已存在。
- IPC client 是一个真实插件，而不只是概念示例。
- 基于 runtime profile 的组合是很好的设计：
  - `desktop` profile
  - `windows` profile
- 前端 hooks 和 payload 完整性规则比一般原型更严谨。
- 前端插件面已经分成：
  - 普通插件
  - 管理/运行时插件

这点很重要，因为：

- 项目已经有了一条可信的前端插件路径，可以覆盖传输/会话相关问题；
- runtime profiles 为按环境进行产品装配提供了良好基础。

但关键 HUD 流程还没有完全接通：

1. HUD 状态迁移没有经过一个真正支持插件的编排器。

- `HudLocalService.transition_to(...)` 直接调用 `state_machine.transition(...)`。
- hook 系统定义了 `before_state_transition`。
- `HudApp` 期望 `STATE_TRANSITIONED` 驱动 `on_after_state_transition`。
- 但当前流程没有建立一个单一、规范的迁移管线来完成这些事。

结果：

- 前端插件无法可靠地参与 HUD 最重要的生命周期事件：状态变化。

2. 组件注册还不是一个真正的组合管线。

- `HudPluginContext.register_widget(...)` 只是把组件存到内部字典里。
- `HudCanvas.mount_widget(...)` 当前只是把组件追加到一个 `QVBoxLayout`。
- `before_widget_register` 作为 hook 概念已经存在。
- `WidgetRegisteredPayload` 作为事件 payload 概念已经存在。
- 但当前运行时并不是一个可 hook、支持 slot 感知的组件组合管线。

结果：

- 当前 HUD 插件系统支持的是“挂载一个演示组件”；
- 还不支持“通过路由、拦截和布局策略组合多个视觉插件”。

3. 服务契约在一定程度上仍是表征性的，而不是运行性的。

- `HudLocalService.register_widget(...)` 返回的是一个成功形状的 dict。
- 它并没有真正参与 slot 预留或组件组合路径。

结果：

- 前端插件契约的一部分仍然停留在占位层级。

4. 前端插件成熟度不均衡。

- `ipc-client` 已通过有意义的测试得到验证。
- 通用 HUD 插件生命周期没有达到同等深度的测试覆盖。

判断：

- 前端插件系统在结构上有前景；
- 但作为完整 HUD 功能基础，它还不完整。

## 当前基础能支持什么

### 现在可以安全构建的内容

以下内容在当前基础上继续做是合理的：

- 后端任务生命周期扩展
- 后端 notifier/exporter/template/ranker 扩展
- 可以 veto 或重定向迁移的后端规则插件
- 保持在 `flow_hud/plugins/ipc/` 内的前端 IPC 演进
- 基于 runtime profile 的启动装配

### 现在构建有风险的内容

以下内容现在还不应被视为“只要写插件就行”：

- 复杂的、状态驱动的 HUD 行为插件
- 带有 slot/layout 组合的多个视觉 HUD 组件
- 依赖权威的 before/after 状态迁移 hooks 的前端插件
- 面向广泛第三方的 HUD 插件故事

### 现在还不能这样宣称

以下说法会夸大当前现实：

- “前后端插件系统都已经完整”
- “HUD 行为已经完全由插件驱动”
- “项目已经拥有一个可支撑任意未来 UI 功能的稳定插件平台”

## 核心方向

下一阶段的插件系统里程碑应该是：

**完成 HUD 插件运行时，让前端插件像后端插件一样参与真实的产品流。**

这意味着优先级不是：

- 更多抽象化的插件接口
- 更多关于插件哲学的文档
- 抽出一个独立的插件框架

优先级应该是：

- 让前端状态迁移接入 hooks 和 events；
- 让组件注册接入真实的 slot/layout 管线；
- 用几个第一方插件来证明这个模型。

## 推荐工作顺序

### 阶段 1：前端流程闭环

目标：
让 HUD 插件成为状态和组件生命周期中的一等参与者。

必须达成的结果：

- 引入一个单一、规范的 HUD 迁移路径；
- 在状态变化前运行 `before_state_transition`；
- 在状态变化成功后发出 `STATE_TRANSITIONED`；
- 让 `on_after_state_transition` 来自实际触发的事件，而不是仅仅依赖预期；
- 让组件注册通过真实的组合路径，而不是被动的字典存储。

具体完成标准：

- 一个有状态的 HUD 插件可以 veto 一次迁移；
- 一个有状态的 HUD 插件可以在迁移后做出响应；
- 一个视觉插件可以把组件注册到命名 slot；
- 运行时会按照 slot 策略挂载该组件。

### 阶段 2：前端组合契约加固

目标：
把当前 HUD 插件 API 从“仓库内部人员可用”变成“稳定的内部平台”。

必须达成的结果：

- 为 HUD 组件定义明确的 slot/layout 契约；
- 决定组件注册是事件驱动、直接调用驱动，还是混合模式；
- 移除服务层契约中的占位行为；
- 明确 runtime profile 组合和插件发现规则。

具体完成标准：

- 不再存在伪成功的组件注册路径；
- 组件放置语义有文档且可测试；
- runtime profile 行为和 admin 插件规则是确定性的。

### 阶段 3：参考插件

目标：
通过真实的第一方插件来证明平台，而不是只依赖框架层面的信心。

推荐参考集合：

- 一个后端策略插件
- 一个后端 notifier/exporter/template 插件
- 一个 HUD 状态行为插件
- 一个超出 `debug-text` 的 HUD 视觉组件插件

这一阶段的重要性在于：

- 没有真实插件的插件系统仍然只是理论；
- 参考插件会迫使缺失的生命周期语义变得明确。

### 阶段 4：插件测试矩阵

目标：
把插件平台当作基础设施来验证，而不只是通过偶然的功能测试来验证。

最低覆盖范围：

- registry 的重复处理
- 发现行为
- setup/teardown 顺序
- admin 与 standard 上下文路由
- 真实生命周期路径上的 hook 调用
- 组件组合路径
- 插件错误下的故障隔离和熔断行为

## 建议的战略立场

如果项目需要一句话来指导未来决策，可以这样写：

> 后端插件已经准备好承担真实扩展工作。前端插件还没有准备好承载下一代 HUD 功能，直到状态流和组件流都完全接通。

这个立场足以指导范围决策：

- 继续在插件基础上构建后端功能；
- 不要假设前端 HUD 功能可以“以后再插件化”，而不先补齐运行时路径；
- 把前端插件闭环视为启用型基础设施，而不是可选清理项。

## 推荐的下一项变更

如果把这份评估转成一个 OpenSpec 变更，最自然的下一项变更可以是：

- `harden-hud-plugin-runtime`

范围应包含：

- HUD 迁移的规范化编排
- HUD 状态变化的 hook/event 连接
- 真正的组件注册管线
- 支持 slot 的 canvas 组合
- 端到端证明生命周期的测试

后续再做一个变更可以针对：

- `backend-plugin-reference-pack`

该变更应该添加真实的后端插件和插件平台测试，而不是重新设计现有的后端基础。

## 最终判断

这个仓库确实有一个有意义的插件架构。

但它是不对称的：

- 后端插件架构已经在功能上完成集成；
- 前端插件架构只完成了部分集成。

所以，正确的未来方向不是“前后端两边都继续平均推进”。

正确的未来方向是：

1. 继续信任后端插件模型，把它当作可工作的扩展基础；
2. 完成前端插件运行时路径；
3. 然后用真实的参考插件验证两侧是否能够形成一个一致的长期平台。
