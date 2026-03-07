# 心流引擎 (Flow Engine) - 核心架构全景解析

本文档旨在提供一份极尽详细的心流引擎系统架构图与底层接口契约，供后续二开人员、开源社区贡献者，以及大模型 AI 系统（如 MCP 接入）作为终极指南使用。

## 目录
1. [系统整体拓扑 (Topology)](#1-系统整体拓扑-topology)
2. [第一层：接入与端口层 (Interface & Port Layer)](#2-第一层接入与端口层-interface--port-layer)
3. [第二层：状态与调度引擎 (State & Scheduler)](#3-第二层状态与调度引擎-state--scheduler)
4. [第三层：事件总线与钩子系统 (Events & Hooks)](#4-第三层事件总线与钩子系统-events--hooks)
5. [第四层：时间旅行与存储抽象 (Storage Layer)](#5-第四层时间旅行与存储抽象-storage-layer)
6. [第五层：物理扩展交互 (Plugins & Context)](#6-第五层物理扩展交互-plugins--context)
7. [第六层：双端 IPC 通信协议](#7-第六层双端-ipc-通信协议)
8. [第七层：未来的 AI 调度层](#8-第七层未来的-ai-调度层)

---

## 1. 系统整体拓扑 (Topology)

心流引擎遵循严格的**六边形架构 (Hexagonal Architecture)**，剥离外围的展现层与底层存储，将唯一的状态约束和领域逻辑封存至引擎中心。

```text
┌────────────────────────────────────────────────────────┐
│                        用户接口层                      │
│   [ CLI (`cli.py`) ]        [ TUI / HUD (规划/雏形) ]  │
└───────────┬────────────────────────────┬───────────────┘
            │                            │
            ▼ 统一通信协议 (`client.py`) ▼
┌────────────────────────────────────────────────────────┐
│             FlowClient Protocol (六边形端口)           │
│  ┌────────────────────┐          ┌──────────────────┐  │
│  │    LocalClient     │          │   RemoteClient   │  │
│  │ (进程内单机模式)   │◀ ─ ─ ─ ─▶│ (守护进程RPC模式)│  │
│  └─────────┬──────────┘  切换    └────────┬─────────┘  │
└────────────┼──────────────────────────────┼────────────┘
             │                              │   ▲
             ▼       ┌──────────────────┐   ▼   │
┌────────────────┐   │    IPC 服务端    ├───┘   │ TCP/UDS
│    FlowApp     │◀──│  (`daemon.py`)   │       │
│  (核心领域应用)│ 引擎└──────────────────┘       │
└──────┬─────────┘                              │
       │ 分发器                                 │
       │                                        │
       ▼ 强类型事件与钩子 (`events.py`, `hooks.py`)
┌────────────────┬───────────────┬──────────────┬────────┐
│   [ 状态机 ]   │  [ 调度器 ]   │  [ 存储层 ]  │ [ 插件 ] │
│  (`state/`)    │ (`scheduler/`)│ (`storage/`) │(Plugin)│
│ Draft->Ready   │  Gravity      │   Tasks.md   │ 现场快照 │
│ ->...->Done    │  Score 计算   │  + Git提交   │(activity)│
└────────────────┴───────────────┴──────────────┴────────┘
```

---

## 2. 第一层：接入与端口层 (Interface & Port Layer)

该层确保外部世界（无论是终端命令行，还是未来的 GUI）从不直接触摸领域模型。

### 核心契约：`FlowClient`

所有行为通过 `flow_engine/client.py` 中定义的纯净协议处理。输入参数为基础类型，输出永远为单纯的字典 `dict` 或列表，有效避免领域模型泄漏。

```python
class FlowClient(Protocol):
    # 核心读写逻辑 API
    def add_task(self, title: str, priority: int = 2, ddl: str = None, tags: list[str] = None, template_name: str = None) -> dict: ...
    def list_tasks(self, show_all: bool = False, filter_state: str = None, filter_tag: str = None, filter_priority: str = None) -> list[dict]: ...
    
    # 状态机流转控制 API (核心独占协议的触发入口)
    def start_task(self, task_id: int) -> dict: ...
    def pause_task(self) -> dict: ...
    def resume_task(self, task_id: int) -> dict: ...
    def done_task(self) -> dict: ...
    def block_task(self, task_id: int, reason: str = "") -> dict: ...

    # 查询评估 API
    def get_status(self) -> dict: ...
    def breakdown_task(self, task_id: int) -> list[str]: ...
```

系统运行时，底层会根据是否探测到幽灵守护进程而无缝切换 `LocalClient`（直接在当前进程执行 `FlowApp`）和 `RemoteClient`（通过 IPC 把请求派发给后台）。

---

## 3. 第二层：状态与调度引擎 (State & Scheduler)

位于 `flow_engine/state/machine.py`。严格落实 "Single-Tasking" 独占法则。

### 八维状态集合 `TaskState`
- **Draft**: 草稿阶段
- **Ready**: 就绪阶段
- **Scheduled**: 已排期
- **In Progress**: 【互斥锁】有且仅有一个任务可以在此时段占据此状态。
- **Paused**: 由于另一个任务强行开启被自动压栈
- **Blocked**: 依赖外部输入卡住
- **Done**: 已完成
- **Canceled**: 已取消

系统使用显式的 `TRANSITIONS` `dict` 白名单表来守门，任何违规的转移尝试都会抛出 `IllegalTransitionError` 熔断操作。

---

## 4. 第三层：事件总线与钩子系统 (Events & Hooks)

系统的绝对解耦枢纽，灵感源于 `pluggy` 及前端打包器的 Tapable。

### Event Bus (事件广播机制)
采用发后即忘（Fire-and-forget）模式，一旦某操作落盘（类似写请求结束），系统派发 Event：
- 具备同步前台路径 `emit()`，与完全非阻塞的 `emit_background()`，后者使用带重试和死信队列的安全守护线程 `BackgroundEventWorker`。

### Hook System (钩子拦截器)
钩子是可以改变原定流转的行为干涉者：
- **执行策略**：支持 `PARALLEL`（同步并发）、`WATERFALL`（瀑布处理传导）和 `BAIL_VETO`（有一个插件说不，整体流转立刻中止）。
- **熔断网关 (`HookBreaker`)**：一旦针对第三方插件的超时、异常次数达标，系统将自动进入断路保护，避免劣质扩展把主系统拖慢。

---

## 5. 第四层：时间旅行与存储抽象 (Storage Layer)

放弃僵硬的 SQL 数据表，投入极具极客风格的文件文本流。

### 纯面向对象抽象 `TaskRepository`
```python
class TaskRepository(ABC):
    async def load_all(self) -> list[Task]: ...
    async def save_all(self, tasks: list[Task]) -> None: ...
    async def get_by_state(self, state: TaskState) -> list[Task]: ...
```
系统通过依赖注入挂载了能够将 Markdown/Frontmatter 头解包再封装的特定实现。

### Git Ledger 持久化
在底层的 `VersionControl` 实现中，任何任务流转造成的变更，系统都会悄无声息地通过独立线程发起 `subprocess` 并行执行 `git commit`。为任务系统带入天然的时间机器，完美提供防灾容错和私有云端合并机制。

---

## 6. 第五层：物理扩展交互 (Plugins & Context)

不仅限于虚拟的任务打卡，心流引擎致力于锁定当前的“物理环境”。
包含一套独立的 Context 抓取协议（`plugins/context.py`）：
系统切断任务时，后台钩子瞬间启动第三方工具，捕获当前的浏览器 URL 集合、IDE 文件指针坐标，与任务自身一起被持久化到数据库中，并在任务重新唤起时再打回到用户屏幕上。

---

## 7. 第六层：双端 IPC 通信协议

极简却强悍的 JSON-Lines 协议。定义在 `ipc/protocol.py`。
- **Request (客户端 -> 后端)**: 带 UUID 的调用体，如 `{"method": "task.start", "params": {"task_id": 1}, "id": "uuid8"}`
- **Response (后端 -> 客户端)**: `{"id": "uuid8", "result": ...}`
- **Push (持续播报)**: 由后端的监控脚本主动向当前的前端推报数据，比如专注时钟跳动（`TimerTick`）或者建议喝水休息（`BreakSuggested`）。

---

## 8. 第七层：未来的 AI 调度层

架构在 `scheduler/` 内打下了桩基。引力排行榜（Gravity Score）依赖截止日期、优先级 P0-P3 和任务依赖进行分数测算，并暴露出以下面向大模型的接口：
```python
class TaskBreaker(ABC):
    @abstractmethod
    def breakdown(self, task: Task) -> list[str]: ... # 让AI大模型将大任务碎纸机般切分

class NextHopAdvisor(ABC):
    @abstractmethod
    def suggest(self, tasks: list[Task], available_minutes: int) -> Task | None: ...
```

---
此文档由系统 Agent 于探索阶段梳理并自动编纂，内容对齐当前 Flow Engine 生产层抽象代码。
