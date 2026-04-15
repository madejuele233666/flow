# Flow

[English](#english)

Flow 是一个围绕“同一时刻只做一个活跃任务”构建的桌面任务系统。

当前仓库里已经落地的核心部分是：

- 后端主任务流 runtime
- 后端与 HUD 之间的 IPC V2 边界
- 面向 Windows 的 HUD runtime，以及一个受测的 `task-status` MVP

它还不是终局产品。上下文恢复、HUD 产品化、AI 辅助、交付与生态扩展都还在推进中。

## 当前状态

截至 2026-04-15，代码、测试和现行文档可以支撑这些判断：

- `TaskFlowRuntime` 是后端主生命周期的真相面
  - `add -> start -> pause -> block -> resume -> done -> status`
- 本地调用与 daemon 调用共享同一套任务流语义
- IPC V2 已实现，并且有前后端测试覆盖
- Windows HUD 已有真实产品路径
  - 当前建立在 `ipc-client + task-status` 上
- 上下文 capture / restore 已有基础能力
  - 但还不是完整的上下文恢复产品

如果你要看代码约束下的完整现状，请先读：

- [docs/roadmap/01-current-state.md](./docs/roadmap/01-current-state.md)

## 仓库结构

当前仓库有三个 active workspaces：

- `backend/`
  - Flow Engine 后端包 `flow_engine`
- `frontend/`
  - Flow HUD 前端包 `flow_hud`
- `shared/`
  - 共享 IPC 合约包 `flow_ipc`

根目录下的非 package 资产包括：

- `docs/`
  - 路线图、审计文档、归档源文档
- `openspec/`
  - 工作流规格、schema、change artifacts
- `.agent/`
  - 本地 agent 相关项目资产

## 阅读入口

- 当前实现状态：
  [docs/roadmap/01-current-state.md](./docs/roadmap/01-current-state.md)
- 终局产品定义：
  [docs/roadmap/02-north-star.md](./docs/roadmap/02-north-star.md)
- 从现状到终局的执行总图：
  [docs/roadmap/10-execution-program.md](./docs/roadmap/10-execution-program.md)
- 路线图总入口：
  [docs/roadmap/README.md](./docs/roadmap/README.md)
- 历史文档与原始资料入口：
  [docs/past/README.md](./docs/past/README.md)

原始长篇产品愿景已经归档到：

- [docs/past/aim.md](./docs/past/aim.md)

## 快速开始

### Backend

```bash
cd backend
pip install -e ".[dev]"
flow --help
```

### Frontend

```bash
cd frontend
pip install -e ".[dev,gui]"
python -m flow_hud.main
```

Windows-oriented HUD 入口：

```bash
cd frontend
python -m flow_hud.windows_main
```

## 验证

```bash
cd backend
pytest -q

cd ../frontend
pytest -q
```

## 说明

- HUD 的目标运行环境是 Windows，即使日常开发可能发生在 WSL。
- 当前确实存在一条 machine-local 的 Windows launcher 路径，但它还不是通用分发方案。
- 需要当前判断时优先看 `docs/roadmap/`，需要历史来源时再看 `docs/past/`。

## English

Flow is a desktop task system built around a strict single-active-task model.

What exists today:

- a backend task-flow runtime
- an IPC V2 boundary between backend and HUD
- a Windows-oriented HUD runtime with a tested `task-status` MVP

What does not exist yet as a finished product:

- full context recovery
- HUD productization beyond the MVP path
- production AI assistance
- general delivery/distribution surfaces

Start here:

- Current implementation status:
  [docs/roadmap/01-current-state.md](./docs/roadmap/01-current-state.md)
- Product target:
  [docs/roadmap/02-north-star.md](./docs/roadmap/02-north-star.md)
- Execution roadmap:
  [docs/roadmap/10-execution-program.md](./docs/roadmap/10-execution-program.md)
- Roadmap index:
  [docs/roadmap/README.md](./docs/roadmap/README.md)

Repository layout:

- `backend/`: `flow_engine`
- `frontend/`: `flow_hud`
- `shared/`: `flow_ipc`

Quick start:

```bash
cd backend
pip install -e ".[dev]"
flow --help

cd ../frontend
pip install -e ".[dev,gui]"
python -m flow_hud.main
```
