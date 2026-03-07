## Why

在 HUD V2 架构设计过程中，AI 助手在生成架构文档 (`design.md`) 和任务拆解 (`tasks.md`) 时，暴露了严重的系统性失败模式。这次失败不是某个单点的疏忽，而是 AI 辅助复杂系统架构时会**必然触发**的一组互相关联的反模式。

### 事件回放

1. 用户要求 AI "参考 `flow_engine` 主程序后端的架构经验"来设计 HUD V2 架构。
2. AI 生成了一套看起来"非常专业"的文档——大量使用了"防腐层"、"解耦"、"DI"、"插件化"等术语。
3. 当用户要求逐层对照主引擎的实际代码时，发现 AI 的设计文档与主引擎的 7 个核心架构契约存在**严重偏差**。
4. 经人类审计后，三份文档被全面重写。

### 核心发现：AI 的 5 种架构设计失败模式

**模式 1: 词霸本能 (Consultant-Speak Instinct)**
AI 用高级术语替代工程精度。说"建立 EventBus 进行解耦"却不定义载荷类型、不区分同步/异步路径、不设计后台消费策略。

**模式 2: 精度衰减 (Precision Decay)**
AI 即便被给予了准确的参照物（如"对标 `flow_engine` 的 `hooks.py`"），仍会在落地时大幅降低精度——将主引擎的 5 策略钩子管理器 + 熔断器降级为"try-catch wrapper"。参照物的架构层级越深，AI 的精度衰减越严重。

**模式 3: 扁平化偷懒 (Flattening Shortcut)**
AI 将主引擎精心设计的多层结构压平为单层。例如：主引擎有双层权限沙盒 (`PluginContext` + `AdminContext`)，AI 直接压平为一个模糊的 `PluginContext`。主引擎有强类型载荷系统 (`events_payload.py` + `hooks_payload.py`)，AI 直接跳过，退化为 `dict` 传参。

**模式 4: 选择性失明 (Selective Blindness)**
AI 会"只看到"参照系统中那些容易描述的高层概念，而对那些需要深入代码才能发现的底层契约选择性忽略。例如完全无视 `FlowClient Protocol` 的端口防泄漏设计、`BackgroundEventWorker` 的重试/死信机制、`PluginManifest` 的声明式元数据。

**模式 5: 乐观假设 (Optimistic Assumption)**
AI 假设"提到概念 = 实现了概念"。写下"引入依赖注入"但不定义 DI 容器的工厂方法模式和配置驱动策略；写下"插件化"但不设计 manifest、不实现 entry_points 自动发现。

### 同时必须承认做对了什么

- **V1 Postmortem 的做法是正确的**：`docs/hud-v1-postmortem.md` 的结构（失败分析 → 技术验证沉淀 → 设计建议）是一个优秀的模板。
- **AI 确实识别了正确的方向**：原版文档提出的 DI、EventBus、防腐层、两步走战略，作为**方向**是完全正确的。失败发生在从方向到落地的"最后一英里"。
- **"检查点阻断"机制是 AI 原创的好设计**：原版 tasks.md 中的"【检查点】必须获得用户显式确认后才能往下进行"机制，是一个有效的 AI 自我约束手段，且主引擎的任务文档中并没有此设计。

## What Changes

1.  **建立"AI 架构失败模式"分类学**：将 5 种失败模式正式归档，附带具体的 Before/After 代码级对照，使未来的人类审计和 AI 自检有据可循。
2.  **提炼可执行的架构审计检查清单 (Architecture Audit Checklist)**：不是空洞的原则，而是逐项可打勾的硬检测点，直接嵌入 AI 协作工作流。
3.  **沉淀"对标法 (Alignment Protocol)"的标准操作流程**：将本次手动审计的成功路径（对标主引擎 → 逐层差距分析 → 精确重写）固化为可复用的 SOP。
4.  **收录完整的 Before/After 差距矩阵**：作为教训的核心资产永久存档。

## Capabilities

### New Capabilities
- `ai-architecture-guidelines`: AI 辅助架构设计的防御性执行指南，包含 5 种失败模式分类、可执行审计检查清单、对标法 SOP。
- `architecture-audit-checklist`: 可直接嵌入 design.md / tasks.md 生成流程的逐项硬检测清单。

### Modified Capabilities
- 

## Impact

此文档不直接修改任何业务代码，而是作为开发团队与 AI Partner 之间的"元规则 (Meta-rules)"基石。
- **短期**：后续的 `design.md` / `tasks.md` 生成必须通过检查清单审计。
- **长期**：沉淀为 `.agent/skills/` 中的架构推演 skill，使 AI 在启动架构任务时自动加载防御性约束。
- **知识资产**：Before/After 差距矩阵作为案例教材永久存档于 `docs/`。
