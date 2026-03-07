## Context

在 HUD V2 架构重构设计中，AI 助手被要求"参考 `flow_engine` 主程序后端的成功解耦模式"来设计新架构。AI 生成了完整的 `proposal.md`、`design.md` 和 `tasks.md`，文档结构完整、术语运用"老练"。然而，当人类工程师逐层对照主引擎的实际代码结构后，发现文档与代码现实之间存在 **7 个严重偏差**。

这不是一次"偶然的马虎"，而是 AI 在处理复杂系统架构任务时的**结构性失败**。本设计旨在深度剖析失败的全链路根因，并产出可执行的防御体系。

## Goals / Non-Goals

**Goals:**
*   建立 AI 架构设计失败的 **5 种反模式分类学**，附带从 HUD V2 实际案例中提取的精确 Before/After 对照。
*   提炼一份 **可逐项打勾的架构审计检查清单 (Architecture Audit Checklist)**，嵌入未来的 AI 架构协作流程。
*   固化 **"对标法 (Alignment Protocol)"标准操作流程**：当 AI 需要参照已有系统设计新模块时，如何确保精度不衰减。
*   同时沉淀 **正面经验**：明确哪些做法是正确的、应被保留的。

**Non-Goals:**
*   不涉及 HUD 业务特性的二次设计。此文档专供"如何让 AI 产出工程级架构契约"。
*   不追求覆盖所有可能的 AI 失败场景——聚焦于本次实际暴露的模式。

## Decisions

### Decision 1: 建立 5 种 AI 架构失败模式分类学

基于 HUD V2 设计审计的实际发现，将 AI 的失败行为归纳为 5 种可识别、可防御的反模式：

| # | 反模式 | 定义 | HUD V2 实例 |
|---|---|---|---|
| 1 | **词霸本能 (Consultant-Speak)** | 用高级术语替代工程精度 | 说"建立 EventBus 进行解耦"但不定义载荷类型，不区分同步/异步路径 |
| 2 | **精度衰减 (Precision Decay)** | 参照物的架构层级越深，AI 的复刻精度越低 | 将主引擎的 5 策略 HookManager + HookBreaker 降级为 "try-catch wrapper" |
| 3 | **扁平化偷懒 (Flattening Shortcut)** | 将精心设计的多层结构压平为单层 | 双层权限沙盒 (PluginContext + AdminContext) 被压平为一个模糊的 Context |
| 4 | **选择性失明 (Selective Blindness)** | 忽略需要深入代码才能发现的底层契约 | 完全无视 Port Contract 防泄漏、BackgroundEventWorker 重试/死信、PluginManifest |
| 5 | **乐观假设 (Optimistic Assumption)** | "提到概念 = 实现了概念" | 写下"插件化"但不设计 manifest、不实现 entry_points 自动发现 |

**设计要点**：这 5 种模式不是独立的，它们形成一个**衰减链 (Decay Chain)**：
```
词霸本能 → 精度衰减 → 扁平化偷懒 → 选择性失明 → 乐观假设
(用大词替代)  (降低层级)  (压平结构)   (跳过细节)   (默认完成)
```

### Decision 2: 收录完整的 7 项 Before/After 差距矩阵

这是本 postmortem 的**核心资产**。没有具体对照就没有可复现的教训。

| # | 主引擎契约 | 对标文件 | 原版 HUD V2 文档 (Before) | 重写后 (After) |
|---|---|---|---|---|
| 1 | `FlowClient Protocol` — 端口防泄漏 | `client.py` | ❌ 完全缺失。插件直接拿 EventBus 实例和 QWidget 引用 | ✅ `HudServiceProtocol` — 入参只允许 `str/int/dict`，返回只允许 `dict/list[dict]` |
| 2 | `EventBus` — 双路径执行 + `BackgroundEventWorker` | `events.py` | ⚠️ 提到 EventBus 但无后台消费和双路径 | ✅ `emit()` 同步 + `emit_background()` 异步 + Worker(重试+死信) |
| 3 | `events_payload.py` + `hooks_payload.py` — 强类型载荷 | `events_payload.py` | ❌ 完全缺失。事件传字典 | ✅ 全部 `@dataclass(frozen=True)` 载荷 |
| 4 | `HookManager` — 5 策略 + `HookBreaker` 熔断器 | `hooks.py` | ⚠️ 降级为 "try-catch wrapper" | ✅ PARALLEL/WATERFALL/BAIL/BAIL_VETO/COLLECT + HookBreaker(阈值/超时/三态) |
| 5 | `PluginContext` + `AdminContext` — 双层权限沙盒 | `plugins/context.py` | ❌ 压平为单个模糊 Context | ✅ `HudPluginContext`(受限) + `HudAdminContext`(高权，白名单授权) |
| 6 | `PluginManifest` + `PluginRegistry.discover()` — 声明式元数据+自动发现 | `plugins/registry.py` | ❌ 只有基类，无 manifest/discover | ✅ `HudPluginManifest` + `entry_points` 自动发现 |
| 7 | `FlowApp` — 配置驱动 DI 工厂 | `app.py` | ⚠️ 描述为"握 EventBus 空壳" | ✅ `HudConfig` 驱动 + 工厂方法 + 全生命周期管理 |

### Decision 3: 分析根因链 (Root Cause Chain)

失败不是因为 AI "不知道"这些概念。根因链如下：

```
用户指令层面                      AI 执行层面
┌─────────────────┐            ┌───────────────────────────────────┐
│ "参考主引擎的    │ ───────→  │ AI 读取高层描述 (architecture.md)  │
│  架构经验"       │            │ 但不深入阅读实际源码文件           │
└─────────────────┘            └─────────────┬─────────────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────────────┐
                               │ 产出基于"印象"而非"代码"的设计    │
                               │ → 只复制了概念名词,遗失了实现精度   │
                               └─────────────┬─────────────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────────────┐
                               │ 5 种反模式依次触发 (Decay Chain)    │
                               └───────────────────────────────────┘
```

**根因 1: 上下文深度不足**
AI 收到的参照是概念性描述 (`architecture.md`)，而非主引擎的具体代码文件 (`events.py`, `hooks.py`, `client.py`, `plugins/context.py` 等)。概念性描述本身就已经经历了一次精度衰减（从代码到文档），AI 在此基础上再次衰减，导致双重精度损失。

**根因 2: 缺少逐文件对标清单**
用户说"参考主引擎"，但没有给出"具体对标哪些文件的哪些接口"的清单。AI 被允许自行选择参考粒度，自然选择了最省力的高层概念。

**根因 3: 缺少 Before/After 验证环节**
文档输出后没有经过"逐层对照验证"的流程。如果在 AI 首次输出后就要求它逐个文件对比，偏差可以在当时被捕获。

### Decision 4: 固化"对标法 (Alignment Protocol)" SOP

基于本次成功的人类审计路径，固化为标准操作流程：

```
步骤 1: 锁定参照系 (Lock Reference)
  → 列出参照系统中需要对标的每一个源码文件
  → 例: events.py, hooks.py, client.py, plugins/context.py, plugins/registry.py, app.py

步骤 2: 逐文件提取契约 (Extract Contracts)
  → 对每个参照文件,提取其核心类、方法签名、数据结构
  → 明确其设计决策(如: 为什么用 frozen dataclass? 为什么双层 Context?)

步骤 3: 建立映射表 (Build Mapping Table)
  → 参照模块 A → 新系统模块 A'
  → 参照模块 B → 新系统模块 B'
  → 标注哪些需要原样复刻,哪些需要适配(如: EventBus 底层从 asyncio 改为 Qt Signal)

步骤 4: 生成设计文档 (Generate Design)
  → 每个 Decision 必须标注对标来源文件和具体类名
  → 必须包含对标代码示例

步骤 5: 逐层差距验证 (Gap Verification)
  → 完成设计后,逐行对照映射表,检查每个契约是否被覆盖
  → 标记 ✅ (已覆盖) / ❌ (遗漏) / ⚠️ (部分覆盖)
  → 任何 ❌ 必须回到步骤 4 补完
```

### Decision 5: 提炼可执行的架构审计检查清单

将防御措施从"原则"转化为"可打勾的检测点"：

**A. 数据契约检测 (Data Contract Checks)**
- [ ] 每个事件类型是否都有对应的 `@dataclass(frozen=True)` 载荷？
- [ ] 每个钩子是否都有对应的强类型载荷（区分 frozen/mutable）？
- [ ] 端口层方法的入参是否全部为基础类型 (`str`, `int`, `dict`)？
- [ ] 端口层方法的返回值是否全部为 `dict` 或 `list[dict]`？

**B. 边界隔离检测 (Boundary Isolation Checks)**
- [ ] 是否存在端口契约层 (`Protocol` 类) 将内部对象与外部消费者隔离？
- [ ] 插件 Context 是否区分了普通权限和高权限？权限分级是否通过白名单机制？
- [ ] 底层引用是否通过只读 `@property` 暴露？是否使用 `Any` 避免强运行时依赖？
- [ ] 核心文件中是否存在越层 import（如纯逻辑层 import 了 UI 框架）？

**C. 防御机制检测 (Defense Mechanism Checks)**
- [ ] EventBus 是否区分了前台同步路径和后台异步路径？
- [ ] 后台路径是否有重试机制和死信记录？
- [ ] 钩子系统是否支持多种执行策略（至少 PARALLEL + WATERFALL + BAIL_VETO）？
- [ ] 每个 handler 是否绑定了独立的熔断器（含超时、失败阈值、恢复窗口）？

**D. 插件生态检测 (Plugin Ecosystem Checks)**
- [ ] 插件是否携带声明式元数据 (`Manifest`：name, version, requires, config_schema)？
- [ ] 是否支持 `entry_points` 自动发现？
- [ ] 编排器是否通过配置文件驱动插件加载和权限分配？
- [ ] 生命周期管理是否完整（`setup()` / `teardown()` / 优雅关闭等待排空）？

**E. 任务清单防御检测 (Task List Defense Checks)**
- [ ] 高危核心步骤是否设有阻断检查点（必须获得用户确认才能继续）？
- [ ] 是否存在物理防渗透规定（如"该文件严禁 import PySide6"）？
- [ ] 任务是否以产出物为锚点（"实现 `XxxPayload` 数据类"），而非以流程为锚点（"建立事件机制"）？

### Decision 6: 沉淀正面经验 — 应被保留的做法

从这次事件中同样提炼出值得复用的正面实践：

| 做法 | 来源 | 为什么好 |
|---|---|---|
| **V1 Postmortem 结构** (失败分析 → 技术沉淀 → 设计建议) | `docs/hud-v1-postmortem.md` | 完整的三段式总结，确保教训不只停在"我们失败了"，还保留了成功的技术验证 |
| **检查点阻断 (Checkpoint Block)** | 原版 `tasks.md` | AI 主动在高危步骤前设置用户确认关卡，有效防止 AI 一路冲撞 |
| **防腐规定 (Anti-Corruption Rule)** | 原版 `tasks.md` | 在自然语言中直接写出代码底线（如"严禁 import PySide6"），给 AI 加思想钢印 |
| **两步走战略 (Step A/B)** | 原版 `proposal.md` | 先骨架后填充，防止 AI 跳过接口设计直接编写业务代码 |

## Risks / Trade-offs

*   **Risk**: 过度严格的检查清单可能拖慢简单功能的开发速度。
    **Mitigation**: 检查清单默认适用于"系统重构"、"核心模块拆分"以及"框架底层构建"。对于边缘工具和简单单业务功能，可酌情降低要求。在任务文档中使用标签（如 `[CORE]` / `[EDGE]`）区分适用级别。
*   **Risk**: AI 可能机械地通过检查清单上的条目（形式合规但实质空洞）。
    **Mitigation**: 检查清单中的每一项都要求提供**具体的类名或代码示例**作为证据，不接受"已考虑"之类的纯文字声明。
*   **Risk**: "对标法"可能导致新系统被过度约束为参照系统的复制品，缺乏创新。
    **Mitigation**: 对标法的步骤 3 明确要求标注"哪些需要原样复刻，哪些需要适配"，允许在保持架构精度的前提下进行有针对性的变化。
