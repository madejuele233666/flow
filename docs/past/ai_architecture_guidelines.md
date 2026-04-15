# AI 架构协作指引白皮书

> 本白皮书源自 HUD V2 架构重构中暴露的 AI 系统性失败，将其转化为可执行的工程规范。
> 适用范围：所有涉及核心模块拆分、系统重构、框架底层构建的 AI 协作架构设计任务。

---

## 第一章：AI 架构设计的 5 种失败模式

AI 在辅助复杂系统架构时，会必然触发一组互相关联的反模式，它们形成一条**衰减链 (Decay Chain)**：

```
词霸本能 → 精度衰减 → 扁平化偷懒 → 选择性失明 → 乐观假设
(用大词替代)  (降低层级)  (压平结构)   (跳过细节)   (默认完成)
```

### 模式 1：词霸本能 (Consultant-Speak Instinct)

**定义**：用高级术语替代工程精度。说了概念，但不定义数据结构、不约束类型、不明确边界。

**HUD V2 实例**：
```
❌ Before: "建立 EventBus 进行解耦"
✅ After:  定义 emit()/emit_background() 双路径 + BackgroundEventWorker(重试/死信)
           + 所有事件使用 @dataclass(frozen=True) 载荷
```

**识别信号**：设计文档中出现"DI"、"EventBus"、"插件化"但无任何 `class`/`dataclass`/`Protocol` 代码定义。

---

### 模式 2：精度衰减 (Precision Decay)

**定义**：参照物的架构层级越深，AI 的复刻精度越低。被给予准确的参照文件，仍在落地时大幅降级。

**HUD V2 实例**：
```
参照: flow_engine/hooks.py
  - HookStrategy: PARALLEL / WATERFALL / BAIL / BAIL_VETO / COLLECT
  - HookBreaker: 失败阈值 + 超时 + 三态(CLOSED/OPEN/HALF_OPEN) + 恢复窗口
  - HookManager: register() / call() / safe_mode / dev_mode

❌ Before: "引入 hooks.py，提供基础错误隔离（try-catch wrapper）"
✅ After:  完整复刻 HookStrategy 五策略 + HookBreaker 熔断器
```

**识别信号**：参照了某个模块，但输出比参照系统少了一半以上的子组件。

---

### 模式 3：扁平化偷懒 (Flattening Shortcut)

**定义**：将精心设计的多层结构压平为单层，以最简单的单个类替代分层体系。

**HUD V2 实例**：
```
参照: flow_engine/plugins/context.py
  - PluginContext: 普通沙盒，只暴露注册 API
  - AdminContext(PluginContext): 高权沙盒，只读 @property 暴露底层引用
  - 白名单机制分级授权

❌ Before: "构建 PluginContext 和接口，确保 UI、雷达和 IPC 可以作为独立插件挂载"
✅ After:  HudPluginContext(普通) + HudAdminContext(高权，@property 只读 + 白名单)
```

**识别信号**：多层权限/多层沙盒系统被描述为单个通用 Context 类。

---

### 模式 4：选择性失明 (Selective Blindness)

**定义**：AI "只看到"参照系统中容易描述的高层概念，对需要深入代码才能发现的底层契约视而不见。

**HUD V2 实例**：

| 被忽视的底层契约 | 参照文件 | 实际包含内容 |
|---|---|---|
| 端口契约防泄漏 | `client.py` | `FlowClient Protocol`：入参只允许基础类型，返回只允许 `dict` |
| 后台消费策略 | `events.py` | `BackgroundEventWorker`：异步 Queue + 重试 + 死信队列 |
| 声明式元数据 | `plugins/registry.py` | `PluginManifest`：name/version/requires/config_schema + `entry_points` |
| 强类型载荷系统 | `events_payload.py` | 每个事件对应 `@dataclass(frozen=True)` 载荷 |

**识别信号**：与参照系统对比时，缺少需要阅读超过 2 个文件才能发现的设计模式。

---

### 模式 5：乐观假设 (Optimistic Assumption)

**定义**："提到概念 = 实现了概念"。写下了术语，但没有定义任何具体的接口、数据结构或行为约束。

**HUD V2 实例**：
```
❌ Before: "插件化"  → 没有 manifest、没有 discover()、没有 entry_points
❌ Before: "依赖注入" → 没有配置驱动的工厂方法、没有 config.toml 加载
✅ After:
  - HudPluginManifest(name, version, requires, config_schema)
  - HudPluginRegistry.discover() → entry_points(group="flow_hud.plugins")
  - HudConfig → 驱动 HudApp 的工厂方法，决定加载哪些插件/谁获 Admin 权
```

**识别信号**：任务列表中出现"建立 X 机制"而非"实现 `XxxClass` 数据类/接口"。

---

## 第二章：HUD V2 案例 — 7 项 Before/After 差距矩阵

> 每项均附参照主引擎源文件路径，可直接查阅验证。

### 差距 1：端口契约防泄漏

**参照文件**：`flow_engine/client.py` → `FlowClient` Protocol

```python
# ❌ Before (HUD V2 原版)
# 无端口契约。插件直接拿 EventBus 实例和 QWidget 引用：
class HudPlugin:
    def setup(self, event_bus: HudEventBus, canvas: QWidget): ...  # 领域对象直接泄漏

# ✅ After (重写后)
class HudServiceProtocol(Protocol):
    """HUD 对外暴露的唯一操控契约。
    所有方法返回纯 dict，不暴露领域对象。"""
    def get_hud_state(self) -> dict: ...            # 返回 {"state": "ghost", ...}
    def transition_to(self, target: str) -> dict: ... # 入参为 str，非 HudState 枚举
    def list_plugins(self) -> list[dict]: ...
```

---

### 差距 2：EventBus 双路径 + 后台消费

**参照文件**：`flow_engine/events.py` → `EventBus` + `BackgroundEventWorker`

```python
# ❌ Before (HUD V2 原版)
# "利用 Qt Signal/Slot 机制封装的线程安全 EventBus" — 无双路径、无后台 Worker

# ✅ After (重写后)
class HudBackgroundEventWorker:
    """后台事件消费器 — 带重试和死信队列。"""
    def enqueue(self, event, handlers): ...   # 非阻塞投入
    def _execute_with_retry(self, ...): ...   # 最多 max_retries 次重试
    def _default_dead_letter(self, entry): ... # 死信记录

class HudEventBus(QObject):
    def emit(self, event_type, payload): ...            # 前台同步路径
    def emit_background(self, event_type, payload): ... # 后台异步路径 → Worker
```

---

### 差距 3：强类型事件和钩子载荷

**参照文件**：`flow_engine/events_payload.py` + `flow_engine/hooks_payload.py`

```python
# ❌ Before (HUD V2 原版)
# 无强类型载荷定义。事件传字典，钩子无载荷规范。

# ✅ After (重写后)
# flow_hud/core/events_payload.py
@dataclass(frozen=True)
class MouseMovePayload:
    x: int
    y: int
    screen_index: int = 0

@dataclass(frozen=True)
class StateTransitionedPayload:
    old_state: str
    new_state: str

# flow_hud/core/hooks_payload.py
@dataclass            # 可变 — Waterfall 钩子，插件可原地修改
class BeforeTransitionPayload:
    current_state: str
    target_state: str   # 插件可修改此字段以改变目标状态

@dataclass(frozen=True)  # 不可变 — BAIL_VETO 钩子
class VetoTransitionPayload:
    current_state: str
    target_state: str
```

---

### 差距 4：HookManager 多策略 + HookBreaker 熔断器

**参照文件**：`flow_engine/hooks.py` → `HookStrategy` + `HookBreaker` + `HookManager`

```python
# ❌ Before (HUD V2 原版)
# "创建一个提供基础错误隔联和日志记录的机制，哪怕是使用非常简练的 try-catch Wrapper"

# ✅ After (重写后)
class HudHookStrategy(str, Enum):
    PARALLEL = "parallel"    # 并发执行全部 handlers
    WATERFALL = "waterfall"  # 瀑布传导，原地修改 payload
    BAIL = "bail"            # 第一个非 None 结果立即短路
    BAIL_VETO = "bail_veto"  # 一票否决投票
    COLLECT = "collect"      # 收集所有返回值

class HookBreaker:           # 每个 handler 绑定独立熔断器
    def __init__(self, failure_threshold: int, recovery_timeout: float): ...
    # 三态: CLOSED → OPEN → HALF_OPEN → CLOSED
    def is_open(self) -> bool: ...
    def record_success(self): ...
    def record_failure(self): ...
```

---

### 差距 5：双层权限沙盒

**参照文件**：`flow_engine/plugins/context.py` → `PluginContext` + `AdminContext`

```python
# ❌ Before (HUD V2 原版)
# "构建模块化的 PluginContext 和接口" — 单层，无权限分级

# ✅ After (重写后)
class HudPluginContext:
    """普通插件沙盒 — 只暴露注册型 API。"""
    def subscribe_event(self, event_type, handler): ...
    def register_widget(self, name: str, widget: Any): ...
    def register_hook(self, implementor: object): ...
    def get_extension_config(self, plugin_name: str) -> dict: ...

class HudAdminContext(HudPluginContext):
    """高权限沙盒 — 白名单授权，只读 @property 暴露底层引用。"""
    @property
    def state_machine(self) -> Any: ...   # 只读，类型用 Any 避免强运行时依赖
    @property
    def event_bus(self) -> Any: ...
    @property
    def hook_manager(self) -> Any: ...
```

---

### 差距 6：声明式元数据 + entry_points 自动发现

**参照文件**：`flow_engine/plugins/registry.py` → `PluginManifest` + `PluginRegistry`

```python
# ❌ Before (HUD V2 原版)
# "定义抽象基类 HudPlugin，其必须提供 setup(context) 与 teardown() 虚拟方法" — 无 manifest

# ✅ After (重写后)
@dataclass(frozen=True)
class HudPluginManifest:
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    requires: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)

ENTRY_POINT_GROUP = "flow_hud.plugins"

class HudPluginRegistry:
    def discover(self) -> list[str]:
        """扫描 entry_points 自动发现插件。
        第三方包通过 pyproject.toml 声明即可被发现。"""
        for ep in entry_points(group=ENTRY_POINT_GROUP): ...
```

---

### 差距 7：配置驱动 DI 工厂

**参照文件**：`flow_engine/app.py` → `FlowApp` + 工厂函数

```python
# ❌ Before (HUD V2 原版)
# "创建 HudApp，仅仅负责握着 EventBus，并声明管理生命周期的 start()/stop() 方法"

# ✅ After (重写后)
class HudApp:
    """配置驱动的 DI 编排器。"""
    def __init__(self, config: HudConfig | None = None):
        # 1. 从 hud_config.toml 加载配置
        # 2. 工厂方法创建所有核心模块（EventBus, HookManager, StateMachine）
        # 3. 构造 HudPluginContext 和 HudAdminContext
        # 4. registry.discover() + registry.setup_all(ctx, admin_ctx, admin_names)
        # 5. _wire_events() 连接跨模块事件处理器
        ...

    def shutdown(self):
        """优雅关闭：teardown_all() + 等待 BackgroundEventWorker 队列排空。"""
```

---

## 第三章：根因链分析

AI 的精度衰减不是因为"不知道"这些概念，而是**执行路径的系统性缺陷**：

```
用户指令层面                       AI 执行层面
┌──────────────────┐             ┌────────────────────────────────────┐
│ "参考主引擎的     │ ──────────→ │ AI 读取高层描述 (architecture.md)   │
│  架构经验"        │             │ 但不深入阅读实际源码文件            │
└──────────────────┘             └──────────────┬─────────────────────┘
                                                │ 双重精度损失
                                                ▼
                                 ┌────────────────────────────────────┐
                                 │ 产出基于"印象"而非"代码"的设计     │
                                 │ → 只复制了概念名词，遗失了实现精度  │
                                 └──────────────┬─────────────────────┘
                                                │
                                                ▼
                                 ┌────────────────────────────────────┐
                                 │ 5 种反模式依次触发 (Decay Chain)    │
                                 └────────────────────────────────────┘
```

**根因 1：上下文深度不足**
AI 收到的参照是概念性文档（如 `docs/architecture.md`），而非实际源码文件 (`events.py`, `hooks.py`, `client.py` 等)。概念性描述已经经历了一次精度衰减，AI 在此基础上再次衰减，形成双重损失。

**根因 2：缺少逐文件对标清单**
"参考主引擎"的指令没有给出"对标哪些文件的哪些接口"的清单。AI 被允许自行选择参考粒度，自然选择了最省力的高层概念。

**根因 3：缺少 Before/After 验证环节**
文档输出后没有经过"逐层对照验证"流程。如果在首次输出后立即要求 AI 对照源文件逐个比较，偏差可以在当时被捕获。

---

## 第四章：对标法 (Alignment Protocol) SOP

当 AI 需要参照已有系统设计新模块时，必须遵循以下 5 步流程：

### 步骤 1：锁定参照系 (Lock Reference)
- 列出参照系统中需要对标的**每一个源码文件**（不是概念文档）
- 例：`events.py`, `hooks.py`, `client.py`, `plugins/context.py`, `plugins/registry.py`, `app.py`

### 步骤 2：逐文件提取契约 (Extract Contracts)
- 对每个文件，提取其核心类、方法签名、数据结构
- 明确其设计决策（如：为什么用 `frozen=True`？为什么双层 Context？）

### 步骤 3：建立映射表 (Build Mapping Table)
- 参照模块 A → 新系统模块 A'
- 参照模块 B → 新系统模块 B'
- 标注"原样复刻"或"需要适配"（如：EventBus 底层从 asyncio 改为 Qt Signal）

### 步骤 4：生成设计文档 (Generate Design)
- 每个 Decision 必须标注对标来源文件和具体类名
- 必须包含对标代码示例

### 步骤 5：逐层差距验证 (Gap Verification)
- 完成设计后，逐行对照映射表，检查每个契约是否被覆盖
- 标记 ✅（已覆盖）/ ❌（遗漏）/ ⚠️（部分覆盖）
- 任何 ❌ 必须回到步骤 4 补完，不可带 ❌ 发布设计

---

## 第五章：架构审计检查清单 (20 项)

> 适用级别：`[CORE]` = 系统重构/核心模块/框架底层。`[EDGE]` = 边缘工具/简单功能可酌情降低。

### A. 数据契约检测 (Data Contract Checks)
- [ ] `[CORE]` 每个事件类型是否都有对应的 `@dataclass(frozen=True)` 载荷？
- [ ] `[CORE]` 每个钩子是否都有对应的强类型载荷（区分 frozen/mutable）？
- [ ] `[CORE]` 端口层方法的入参是否全部为基础类型 (`str`, `int`, `dict`)？
- [ ] `[CORE]` 端口层方法的返回值是否全部为 `dict` 或 `list[dict]`？

### B. 边界隔离检测 (Boundary Isolation Checks)
- [ ] `[CORE]` 是否存在端口契约层（`Protocol` 类）将内部对象与外部消费者隔离？
- [ ] `[CORE]` 插件 Context 是否区分了普通权限和高权限？权限分级是否通过白名单机制？
- [ ] `[CORE]` 底层引用是否通过只读 `@property` 暴露？是否使用 `Any` 避免强运行时依赖？
- [ ] `[CORE]` 核心文件中是否存在越层 import（如纯逻辑层 import 了 UI 框架）？

### C. 防御机制检测 (Defense Mechanism Checks)
- [ ] `[CORE]` EventBus 是否区分了前台同步路径和后台异步路径？
- [ ] `[CORE]` 后台路径是否有重试机制和死信记录？
- [ ] `[CORE]` 钩子系统是否支持多种执行策略（至少 PARALLEL + WATERFALL + BAIL_VETO）？
- [ ] `[CORE]` 每个 handler 是否绑定了独立的熔断器（含超时、失败阈值、恢复窗口）？

### D. 插件生态检测 (Plugin Ecosystem Checks)
- [ ] `[CORE]` 插件是否携带声明式元数据（`Manifest`：name, version, requires, config_schema）？
- [ ] `[EDGE]` 是否支持 `entry_points` 自动发现？
- [ ] `[CORE]` 编排器是否通过配置文件驱动插件加载和权限分配？
- [ ] `[CORE]` 生命周期管理是否完整（`setup()` / `teardown()` / 优雅关闭等待排空）？

### E. 任务清单防御检测 (Task List Defense Checks)
- [ ] `[CORE]` 高危核心步骤是否设有阻断检查点（必须获得用户确认才能继续）？
- [ ] `[CORE]` 是否存在物理防渗透规定（如"该文件严禁 import PySide6"）？
- [ ] `[CORE]` 任务是否以产出物为锚点（"实现 `XxxPayload` 数据类"），而非以流程为锚点（"建立事件机制"）？
- [ ] `[EDGE]` 是否对每个任务组使用 `[CORE]` / `[EDGE]` 标签区分适用级别？

---

## 第六章：正面经验沉淀

从这次事件中同样提炼出值得复用的正面实践：

| 做法 | 来源 | 为什么好 |
|---|---|---|
| **V1 Postmortem 结构**（失败分析 → 技术验证沉淀 → 设计建议） | `docs/hud-v1-postmortem.md` | 完整三段式总结，确保教训不只停在"我们失败了"，同时还保留了成功的技术验证资产 |
| **检查点阻断 (Checkpoint Block)** | 原版 HUD V2 `tasks.md` | AI 主动在高危步骤前设置用户确认关卡，有效防止 AI 一路冲撞到 GUI |
| **防腐规定 (Anti-Corruption Rule)** | 原版 HUD V2 `tasks.md` | 在自然语言中直接写出代码底线（如"严禁 import PySide6"），给 AI 加思想钢印 |
| **两步走战略 (Step A/B)** | 原版 HUD V2 `proposal.md` | 先骨架后填充，防止 AI 跳过接口设计直接编写业务代码 |
| **AI 方向判断基本正确** | 原版 HUD V2 文档 | DI、EventBus、防腐层、插件化作为方向均正确。失败发生在"最后一英里"的工程落地精度 |

---

*此白皮书由 `ai-arch-postmortem` 变更生成，对应 HUD V2 架构重构事件（2026-03-07）。*
*对标主引擎源码位置：`flow_engine/` 目录下的 `events.py`, `hooks.py`, `client.py`, `plugins/context.py`, `plugins/registry.py`, `app.py`。*
