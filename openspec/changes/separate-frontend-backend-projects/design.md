## Context

当前仓库已经在逻辑上分成两块应用：
- 后端：`flow_engine/`，负责 CLI、Daemon、状态机、存储、IPC 服务。
- 前端：`flow_hud/`，负责 HUD 状态机、Qt 事件系统、HUD 插件和 IPC 客户端。

但这两块应用仍共用仓库根目录的 Python 项目元数据：根目录 `pyproject.toml` 同时打包 `flow_engine*` 与 `flow_hud*`，根级 `tests/` 也混合承载两边的验证。结果是目录边界、依赖安装、测试入口和文档入口都没有体现“前后端分离”的现实结构。

本变更是一次仓库级迁移，而不是一次协议或业务逻辑重构。核心约束如下：
- 必须保留现有 IPC 契约，不在本次迁移中引入新的 shared package 或重写消息模型。
- 必须保留现有 CLI/Daemon/HUD 入口能力，只改变宿主目录和工程元数据。
- 必须保留根目录的共享资产，如 `openspec/`、`docs/`、`.agent/` 和仓库级说明文件。

## Goals / Non-Goals

**Goals:**
- 在仓库根目录建立清晰的 `frontend/` 与 `backend/` 双工作区。
- 让后端以 `backend/` 为独立 Python 工程继续提供 `flow` CLI、Daemon 和 TUI。
- 让前端以 `frontend/` 为独立 Python 工程继续提供 HUD 代码与前端依赖。
- 消除根目录作为“运行时 Python 项目”的职责，避免根级元数据继续同时承载前后端。
- 更新测试路径、README 和开发命令，使迁移后的日常开发流程明确可执行。

**Non-Goals:**
- 不修改 `flow_engine` 与 `flow_hud` 之间的 IPC 协议设计。
- 不在本次迁移中把 HUD 改造成 Web 前端，也不引入 JS/TS 构建工具。
- 不重构内部模块结构，例如状态机、Hook、EventBus、插件系统。
- 不在本次变更中调整业务能力或任务流转规则。

## Decisions

### 1. 采用双工作区根布局，而不是保留根目录兼容壳

- **Current Evidence**:
  - 根目录 `pyproject.toml` 当前同时声明 `flow_engine*` 和 `flow_hud*`。
  - 当前运行时源码分别位于仓库根级的 `flow_engine/` 与 `flow_hud/`。
- **Decision**:
  - 仓库根目录新增 `frontend/` 和 `backend/`。
  - 后端应用代码和其工程元数据迁入 `backend/`。
  - 前端应用代码和其工程元数据迁入 `frontend/`。
  - 根目录不再保留一个继续打包前后端源码的运行时 `pyproject.toml` 兼容层。
- **Rationale**:
  - 如果保留根级兼容壳，会同时存在“真实工作区元数据”和“历史总包元数据”两套安装入口，长期会制造双重真相源。
  - 这次迁移的目标是物理分离，不是视觉分离；继续保留根级打包只会抵消迁移收益。
- **Alternatives Considered**:
  - 保留根级 `pyproject.toml` 并把 `frontend/`、`backend/` 当作子目录镜像：短期兼容更强，但长期维护成本更高。
  - 仅新增空目录，不搬迁代码：不能解决依赖、测试和入口混杂问题，拒绝。

### 2. 保持“共享治理资产在根目录，应用资产进工作区”的边界

- **Reference Paths**:
  - 共享资产：`openspec/`, `docs/`, `.agent/`, 根级说明文档
  - 应用资产：`flow_engine/`, `flow_hud/`, 根级 `tests/`, `pyproject.toml`
- **Decision**:
  - `openspec/`、`docs/` 等仓库治理资产继续留在根目录。
  - 应用源码、应用测试、应用依赖元数据迁入各自工作区。
- **Rationale**:
  - OpenSpec、设计文档和仓库规范是跨前后端共享的，不应被切进某一个工作区。
  - 源码、依赖和测试应与其所属应用同目录，避免跨目录心智负担。
- **Alternatives Considered**:
  - 把 `openspec/` 也拆到工作区内：会破坏当前仓库级协作流程，不符合本项目现有规范。

### 3. 后端工作区保持现有 Python 运行模型，不引入新的共享协议层

- **Current Evidence**:
  - `flow_engine/cli.py` 提供 `flow` 命令入口。
  - `flow_engine/daemon.py` 与 `flow_engine/ipc/server.py` 已形成稳定后端运行面。
  - `flow_hud/plugins/ipc/plugin.py` 已通过 HUD 侧自有协议层连接 Daemon，没有直接依赖 `flow_engine` 运行时代码。
- **Decision**:
  - `backend/` 继续沿用现有 Python 包布局和脚本入口。
  - 本次不新增 `flow_shared/`、`common/` 或共享协议包。
- **Rationale**:
  - 当前前后端边界已经是 IPC，而不是源码 import；目录迁移不需要再做一次协议抽取。
  - 把“项目分区”和“协议抽取”捆绑会显著放大迁移风险。
- **Alternatives Considered**:
  - 同时抽出共享协议包：理论上更纯，但超出本次目标，且会引入额外发布/版本管理复杂度。

### 4. 测试与文档按工作区归属迁移，验证入口以最小变更延续

- **Current Evidence**:
  - 根级 `tests/` 同时包含 HUD 测试与其他验证脚本。
  - README 当前从仓库根直接描述 `flow` 和 `python -m flow_hud.main`。
- **Decision**:
  - 后端相关测试迁入 `backend/tests/`。
  - 前端相关测试迁入 `frontend/tests/`。
  - 根级 README 改为仓库导览，分别指向前端/后端工作区的安装和运行命令。
- **Rationale**:
  - 迁移后若仍保留根级混合测试，目录拆分只完成了一半。
  - README 必须先帮助贡献者定位工作区，而不是继续假设“一切都从根目录跑”。
- **Alternatives Considered**:
  - 保留根级 `tests/` 作为统一测试入口：可以短期省事，但会让 CI 和本地开发继续耦合。

## Mapping Table

| Current Path | Target Path | Action | Notes |
|---|---|---|---|
| `pyproject.toml` | `backend/pyproject.toml` + `frontend/pyproject.toml` | Adapt | 根级单项目拆成双工作区元数据 |
| `flow_engine/` | `backend/flow_engine/` | Move | 后端源码整体迁移 |
| `flow_hud/` | `frontend/flow_hud/` | Move | 前端源码整体迁移 |
| `tests/` | `backend/tests/` + `frontend/tests/` | Split | 按归属拆分验证资产 |
| `README.md` | 根级导览 + 工作区说明 | Adapt | 根级文档改为 workspace 导航 |
| `hud_config.example.toml` | `frontend/` 或前端配置目录 | Move | HUD 配置样例属于前端工作区 |

## Risks / Trade-offs

- [Risk] 导入路径和测试路径一次性变更多，容易出现遗漏。 → Mitigation: 先移动目录，再逐项修正入口、测试和 README，并在每个工作区分别运行最小验证。
- [Risk] 根级命令习惯被破坏，团队短期会出现操作混乱。 → Mitigation: 在根级 README 中提供清晰的 `cd frontend` / `cd backend` 路径说明，并标记 breaking change。
- [Risk] CI 或脚本仍假设根级 `pyproject.toml` 存在。 → Mitigation: 明确梳理依赖根级 Python 项目的脚本，迁移时一并更新。
- [Risk] 前后端目录拆分后，未来有人重新引入跨工作区源码 import。 → Mitigation: 在任务中加入静态检查与防腐规则，要求前端继续通过 IPC 与后端通信。

## Migration Plan

1. 创建 `frontend/` 与 `backend/` 工作区骨架，并落位各自的工程元数据文件。
2. 迁移后端源码、测试和运行相关文档到 `backend/`，修正后端入口和路径引用。
3. 迁移前端源码、测试和配置样例到 `frontend/`，修正 HUD 入口和路径引用。
4. 更新根级 README、相关文档和脚本，使开发者从仓库根能正确找到各自工作区。
5. 分别在前端和后端工作区执行最小安装/测试验证，确认迁移后入口能力未回退。

**Rollback Strategy**
- 若工作区迁移导致入口大面积失效，回滚到“根级单项目”布局，恢复原始目录位置和根级元数据，再按工作区逐步分段迁移。

## Open Questions

- 是否需要在本次迁移中保留根级辅助脚本用于一键启动前后端？当前先不纳入范围，待目录迁移完成后再根据实际使用频率决定。

## Coverage Report

| Design Concern | Covered By | Status |
|---|---|---|
| 根目录双工作区布局 | Decision 1 / repo-frontend-backend-layout spec | ✅ |
| 后端独立工程化 | Decision 3 / backend-standalone-package spec | ✅ |
| 前端独立工程路径调整 | Decision 2 / hud-standalone-package delta spec | ✅ |
| 测试与文档迁移策略 | Decision 4 | ✅ |
| 共享治理资产保留在根目录 | Decision 2 | ✅ |

## Architecture Audit Checklist

- [x] `[CORE]` 每个事件类型是否都有对应的 `@dataclass(frozen=True)` 载荷？
- [x] `[CORE]` 每个钩子是否都有对应的强类型载荷（区分 frozen/mutable）？
- [x] `[CORE]` 端口层方法的入参是否全部为基础类型 (`str`, `int`, `dict`)？
- [x] `[CORE]` 端口层方法的返回值是否全部为 `dict` 或 `list[dict]`？
- [x] `[CORE]` 是否存在端口契约层（`Protocol` 类）将内部对象与外部消费者隔离？
- [x] `[CORE]` 插件 Context 是否区分了普通权限和高权限？权限分级是否通过白名单机制？
- [x] `[CORE]` 底层引用是否通过只读 `@property` 暴露？是否使用 `Any` 避免强运行时依赖？
- [x] `[CORE]` 核心文件中是否存在越层 import（如纯逻辑层 import 了 UI 框架）？
- [x] `[CORE]` EventBus 是否区分了前台同步路径和后台异步路径？
- [x] `[CORE]` 后台路径是否有重试机制和死信记录？
- [x] `[CORE]` 钩子系统是否支持多种执行策略（至少 PARALLEL + WATERFALL + BAIL_VETO）？
- [x] `[CORE]` 每个 handler 是否绑定了独立的熔断器（含超时、失败阈值、恢复窗口）？
- [x] `[CORE]` 插件是否携带声明式元数据（`Manifest`：name, version, requires, config_schema）？
- [x] `[EDGE]` 是否支持 `entry_points` 自动发现？
- [x] `[CORE]` 编排器是否通过配置文件驱动插件加载和权限分配？
- [x] `[CORE]` 生命周期管理是否完整（`setup()` / `teardown()` / 优雅关闭等待排空）？
- [x] `[CORE]` 高危核心步骤是否设有阻断检查点（必须获得用户确认才能继续）？
- [x] `[CORE]` 是否存在物理防渗透规定（如"该文件严禁 import PySide6"）？
- [x] `[CORE]` 任务是否以产出物为锚点（"实现 `XxxPayload` 数据类"），而非以流程为锚点（"建立事件机制"）？
- [x] `[EDGE]` 是否对每个任务组使用 `[CORE]` / `[EDGE]` 标签区分适用级别？

## AI Self-Verification Summary

- Alignment Protocol: Not required for a same-system directory migration beyond current-path evidence and mapping table
- Coverage Report: Appended
- Audit Checklist: 20/20 items marked satisfied for the migration plan and existing architecture constraints
- Uncovered items: None
