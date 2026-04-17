# Flow

Flow 是一个围绕“同一时刻只处理一个活跃任务”构建的桌面任务系统。

它不是传统意义上的任务清单工具，而是把任务执行、上下文恢复、HUD 表达、AI 辅助和交付边界组织成一套一致的工作系统。用户在 CLI、daemon、HUD 和 Windows 入口里看到的，应当是同一套语义：当前在做什么、为什么停住、如何恢复、下一步是什么。

这个仓库承载 Flow 的主要实现、共享协议和路线图文档，适合下面三类访问者：

- 想快速理解 Flow 是什么的人
- 想本地安装、运行和验证 Flow 的人
- 想继续推进 backend、frontend、shared 或路线图的人

## 一眼看懂

- `backend/` 负责任务引擎、daemon、状态机、存储和 IPC。
- `frontend/` 负责 HUD runtime、插件系统和任务状态界面。
- `shared/` 负责后端与前端共用的 IPC V2 合约。
- `docs/` 负责路线图、日用文档、历史材料和流程说明。

## Flow 的北极星

`docs/roadmap/02-north-star.md` 定义了 Flow 的终局目标。简化来说，完整且优雅的 Flow 应该同时满足两件事。

### 用户层

- 录入和切换任务几乎没有摩擦。
- 系统始终把注意力压缩到一个当前任务。
- 恢复任务时，拿回的是工作现场，而不只是标题。
- HUD 像桌面空气一样存在，轻、准、克制，但足够表达状态。
- CLI、daemon、HUD 和 Windows 入口表达的是同一套产品语义。
- AI 是放大器，不是第二套复杂系统。

### 系统层

- 有稳定且可验证的任务流主链。
- 有产品级的上下文捕获、存储、恢复和轨迹系统。
- 有可组合、可扩展、线程安全的 HUD runtime。
- 有可降级、可替换 provider 的 AI 边界。
- 有真正接入产品流的插件生态。
- 有稳定可维护的跨端交付路径。

这里的“优雅”不是视觉装饰，而是结构上的克制。

- 对用户，复杂度被收敛，而不是被暴露。
- 对交互，HUD 轻量存在，而不是抢占工作。
- 对恢复，回到工作现场比记录状态更重要。
- 对扩展，新能力应优先接入既有边界，而不是另起一套系统。

## 这套路线图在解决什么

`docs/roadmap/README.md` 把整个项目拆成一条主线和六道阶段门。它的前提很明确：不要把愿景当现状，也不要把局部底座误写成完整产品。

Flow 的路线图关注的不是“做更多功能”，而是按顺序补齐这几件关键能力：

- Core Task Loop：把单任务主链做稳
- Context Recovery：把上下文恢复做成真正能力
- HUD Experience：把 MVP HUD 推到产品化
- AI Assistance：把 AI 变成受约束的增强器
- Plugin Surfaces：把插件做成真实产品能力
- Delivery, IPC And Independence：把交付和独立性收拢成可维护路径
- Reports, Trails And External Gateways：把轨迹、复盘和外围入口纳入同一系统

## 当前实现和未来目标的关系

`docs/roadmap/01-current-state.md` 负责说明今天已经被代码和测试证实的内容，`02-north-star.md` 负责定义终局，`10-execution-program.md` 负责说明从当前基线走到终局的阶段门。

| 文档 | 角色 |
| --- | --- |
| `01-current-state.md` | 现在有什么 |
| `02-north-star.md` | 最终要成为什么 |
| `10-execution-program.md` | 中间怎么走 |

如果你只关心当前实现，不要从愿景文档倒推；如果你只关心产品终局，不要把当前基线当成最终设计。

## 核心工作流主轴

`docs/roadmap/03-workstreams.md` 按产品主轴拆分路线。当前最关键的三条主轴是：

1. Core Task Loop
2. Context Recovery
3. HUD Experience

原因很直接：它们已经构成当前代码里最接近产品闭环的部分。

### Core Task Loop

这条主轴关注的是任务主链本身：

- `add -> start -> pause -> block -> resume -> done -> status`
- 本地调用与 daemon 调用的语义一致
- 失败路径可解释，而不是只暴露底层异常

### Context Recovery

这条主轴关注的是任务切换时能不能拿回工作现场：

- snapshot 模型不只靠少量字段和 `extra`
- capture / restore 的时机要明确
- 显式挂载和隐式捕获要分开
- 恢复失败要优雅降级

### HUD Experience

这条主轴关注的是 HUD 能否从 MVP 卡片变成真正的桌面产品：

- 不只是显示当前任务
- 还能表达状态、压力和轻量建议
- 交互增强仍然挂在现有 runtime 上

## 六道阶段门

`docs/roadmap/10-execution-program.md` 把整条路线拆成六个阶段门。每一门都建立在前一门已成立的前提上。

```text
当前代码基线
  -> Gate A: 单机日用闭环
  -> Gate B: 上下文恢复成形
  -> Gate C: HUD 产品化
  -> Gate D: AI 增强接入
  -> Gate E: 插件与交付稳固
  -> Gate F: 外围入口与前沿能力
  -> 北极星产品
```

### Gate A: 单机日用闭环

目标是把现有后端主任务流、IPC 边界、Windows HUD MVP 和本地 launcher 路径收口成一个真正可日用的闭环。

它要解决的是“第一次使用也可靠”，而不是继续在主链外侧加旁路。

### Gate B: 上下文恢复成形

目标是把今天的 snapshot 底座升级成真正的 Context Recovery 能力。

这一步的重点不是花哨 UI，而是：

- 更清楚的 snapshot 数据模型
- 明确的 capture / restore 触发规则
- 显式挂载与隐式捕获边界
- 恢复失败时的优雅降级

### Gate C: HUD 产品化

目标是在不推翻现有 HUD runtime 的前提下，把 task-status MVP 升级成真正的桌面产品界面。

这一步关心的是 HUD 能否表达状态、压力、建议和轻量交互，而不是继续堆验证壳。

### Gate D: AI 增强接入

目标是先把 AI 做成一个稳定的任务压缩器，再逐步扩到下一跳建议。

这条路线明确要求 AI 只增强任务流，不重新发明一套任务系统。

### Gate E: 插件与交付稳固

目标是把插件、交付路径和长期独立性从“有底座”推进到“可维护、可扩展、可交付”。

这一步会把第一方参考插件、launcher 经验、机器绑定项和协议治理门槛都收束清楚。

### Gate F: 外围入口与前沿能力

目标是在主产品已经成立之后，再把外围入口、自动复盘和前沿能力接进来。

这包括：

- 消息网关
- 自动心流报表
- 被动上下文轨迹的产品化
- MCP
- 本地 RAG
- 主动条件轮询

## 仓库结构

- [`backend/`](./backend/)：Flow Engine 后端工作区
- [`frontend/`](./frontend/)：Flow HUD 前端工作区
- [`shared/`](./shared/)：共享 IPC 合约包
- [`docs/`](./docs/)：路线图、日用文档、历史材料和流程说明

### backend

后端工作区包含：

- `flow_engine/`：核心包
- `tests/`：后端测试
- `pyproject.toml`：包元数据和依赖

本地入口通常是 CLI 和 daemon：

```bash
cd backend
pip install -e ".[dev]"
flow --help
flow daemon start
flow daemon status
flow tui
```

### frontend

前端工作区包含：

- `flow_hud/`：HUD 包
- `tests/`：前端测试
- `hud_config.example.toml`：示例配置
- `pyproject.toml`：包元数据和依赖

本地运行方式：

```bash
cd frontend
pip install -e ".[dev,gui]"
python -m flow_hud.main
```

Windows 目标运行入口：

```bash
cd frontend
python -m flow_hud.windows_main
```

### shared

`shared/` 只承担一件事：让 backend 和 frontend 使用同一套 IPC V2 合约和数据模型。

如果你在改跨进程消息、编码、协议边界，先看这里。

## 安装与验证

后端：

```bash
cd backend
pip install -e ".[dev]"
flow --help
pytest -q
```

前端：

```bash
cd frontend
pip install -e ".[dev,gui]"
python -m flow_hud.main
pytest -q
```

如果你只想验证 Windows HUD 路径：

```bash
cd frontend
python -m flow_hud.windows_main
```

## 文档导航

如果你第一次进入这个仓库，建议按这个顺序读：

1. [日用与运行文档](./docs/day-use/README.md)
2. [路线图总览](./docs/roadmap/README.md)
3. [历史资料](./docs/past/README.md)

按主题查找时可以直接跳到：

- [backend/README.md](./backend/README.md)
- [frontend/README.md](./frontend/README.md)
- [docs/day-use/README.md](./docs/day-use/README.md)
- [docs/roadmap/README.md](./docs/roadmap/README.md)
- [docs/past/README.md](./docs/past/README.md)
- [docs/review-flow/README.md](./docs/review-flow/README.md)

## 额外说明

- HUD 的目标运行环境是 Windows，即使开发环境可能在 WSL。
- `docs/roadmap/` 是当前事实、路线判断和阶段门的入口。
- `docs/past/` 保留历史材料，但不是默认真相面。
- 如果你只想先判断这个仓库值不值得继续看，从 `docs/day-use/README.md` 开始最快。
