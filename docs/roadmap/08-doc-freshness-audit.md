# 08. 文档时效审计

状态基线：2026-04-17

这份文件只做一件事：

**核实现有 `docs/` 文档哪些仍可作为当前事实来源，哪些已经部分或明显过时。**

判定分三类：

- `current`
  - 当前仍可作为事实或规则依据
- `historical`
  - 描述的是历史状态，但文档明确带历史语境，因此不算“坏文档”
- `stale`
  - 写成当前事实、当前判断或当前路径，但已经被代码、测试或较新的规格超越

## A. 审计结论总表

| 文件 | 状态 | 结论 |
|---|---|---|
| `docs/past/ipc-protocol-v2.md` | `current` | 当前仍是 IPC V2 规范真相 |
| `docs/past/ipc-product-first-guardrails.md` | `current` | 当前仍可作为过渡期 IPC 护栏 |
| `docs/past/windows-launcher-postmortem.md` | `historical` | 明确是复盘文档，历史语境清楚 |
| `docs/past/hud-v1-postmortem.md` | `historical` | 明确是第一轮 HUD 失败复盘 |
| `docs/past/ai_architecture_guidelines.md` | `current` | 当前仍可作为架构协作护栏 |
| `docs/past/aim.md` | `stale` | 愿景价值仍在，但它把大量未来能力写成当前特性 |
| `docs/past/architecture.md` | `stale` | 多处“当前状态”判断已经落后 |
| `docs/past/plugin-system-future-direction.md` | `stale` | 前端 plugin runtime 的关键判断已被后续实现超越 |
| `docs/past/plugin-system-future-direction.zh-CN.md` | `stale` | 与英文原件同样过时 |
| `docs/past/ai_model_invocation_guide.md` | `stale` | 事实判断基本成立，但路径引用已因 repo split 失效 |
| `docs/past/ipc-independent-dev-playbook.md` | `stale` | 长期方向仍有价值，但当前仓库路径引用已过时 |
| `docs/past/unified-roadmap.md` | `historical` | 它明确声明自己已经退役，只保留目录跳转作用 |

## B. 关键过时项

### 1. `docs/past/architecture.md`

状态：`stale`

主要问题：

- 文档把 HUD 描述为“规划/雏形”，但当前前端已经有独立 runtime 和 Windows 产品入口。
- 文档把 IPC V2 描述成“新版协议设计”与未来方向，但当前 repo 已经实现并测试了 V2 主链路。
- 文档整体语气像“探索阶段梳理”，不再适合作为当前结构真相。

证据：

- `docs/past/architecture.md:24`
  - 仍写 `TUI / HUD (规划/雏形)`
- `frontend/flow_hud/runtime.py:54`
  - Windows runtime profile 已固定装配 `ipc-client + task-status`
- `frontend/flow_hud/windows_main.py:1`
  - Windows 产品入口已存在
- `backend/tests/test_ipc_v2_server.py:53`
  - V2 握手和协议行为已有后端测试
- `frontend/tests/hud/test_ipc_client_plugin.py:517`
  - 前端已有 TCP 路径测试

处理建议：

- 不再把这份文档当作“当前架构总图真相”
- 当前优先修复 `docs/roadmap/` 中引用它的表述
- 原文档继续作为历史材料保留在 `docs/past/`

### 2. `docs/past/plugin-system-future-direction.md`

状态：`stale`

主要问题：

- 文档认为前端 HUD 状态流和 widget flow “not fully wired”。
- 文档认为 `HudLocalService.transition_to(...)` 仍直接绕过 canonical orchestrator。
- 文档认为 widget registration 仍只是内部字典存储和单一 `QVBoxLayout` 附加。

这些判断在 2026-04-12 之后已经不再成立。

证据：

- `docs/past/plugin-system-future-direction.md:27`
  - 仍写 HUD plugin system “not yet fully connected”
- `docs/past/plugin-system-future-direction.md:118`
  - 仍写 `HudLocalService.transition_to(...)` 直接调用 `state_machine.transition(...)`
- `frontend/flow_hud/core/service.py:31`
  - `HudLocalService.transition_to()` 已委托 `self._app.transition_to(target)`
- `frontend/flow_hud/core/app.py:195`
  - 已有 canonical `transition_to()`，并执行 hook + event pipeline
- `frontend/tests/hud/test_transition_runtime.py:32`
  - 已验证 veto / transitioned event 行为
- `frontend/flow_hud/core/app.py:233`
  - 已有 canonical `register_widget()` 管线
- `frontend/flow_hud/runtime.py:105`
  - canvas 已通过 runtime event wiring 响应 widget 注册
- `frontend/tests/hud/test_widget_runtime.py:154`
  - 已验证动态注册通过 canvas event pipeline 挂载
- `frontend/tests/hud/test_widget_runtime.py:209`
  - service reservation 已不是假成功，而是明确 `mounted: false`

处理建议：

- 这份文档不应再被当作“当前插件现状评估”
- 当前优先修复 `docs/roadmap/` 中吸收了它的表述
- 原文档继续保留为历史上下文

### 3. `docs/past/plugin-system-future-direction.zh-CN.md`

状态：`stale`

原因：

- 它是英文原件翻译件，问题与英文版一致
- 当前已经与代码现实脱节

处理建议：

- 不把它再当当前事实来源
- 与英文版一起仅保留为历史材料

### 4. `docs/past/ai_model_invocation_guide.md`

状态：`stale`

主要问题：

- 文档中的现实判断大体仍成立：AIConfig 存在、`flow breakdown` 仍是 stub。
- 但它引用的本地代码路径仍指向 repo split 之前的根目录 `flow_engine/...`，已经失效。

证据：

- `docs/past/ai_model_invocation_guide.md:22`
  - 链接指向 `/home/madejuele/projects/flow/flow_engine/config.py`
- 当前真实文件是：
  - `backend/flow_engine/config.py:83`
- `docs/past/ai_model_invocation_guide.md:44`
  - 链接指向 `/home/madejuele/projects/flow/flow_engine/cli.py`
- 当前真实文件是：
  - `backend/flow_engine/cli.py`
- `docs/past/ai_model_invocation_guide.md:46`
  - 链接指向 `/home/madejuele/projects/flow/flow_engine/scheduler/gravity.py`
- 当前真实文件是：
  - `backend/flow_engine/scheduler/gravity.py:80`

处理建议：

- 不把这份文档直接并入当前路线图事实层
- 如需再次使用其内容，应先按当前仓库路径逐条重核

### 5. `docs/past/ipc-independent-dev-playbook.md`

状态：`stale`

主要问题：

- 长期路线本身仍有价值
- 但当前仓库对应关系里引用了旧的 change 路径，已经不再存在

证据：

- `docs/past/ipc-independent-dev-playbook.md:80`
  - 链接指向 `openspec/changes/refactor-ipc-protocol-v2/...`
- 当前实际路径已是：
  - `openspec/specs/ipc-protocol-v2-contract/spec.md`
  - `openspec/specs/ipc-client/spec.md`
  - 历史 change 则位于 `openspec/changes/archive/2026-04-06-refactor-ipc-protocol-v2/`

处理建议：

- 保留其长期方向作为历史背景
- 如需再次吸收，只能先在 roadmap 中重写，不直接复活原文

### 6. `docs/past/aim.md`

状态：`stale`

主要问题：

- 它的战略目标仍然有价值，但标题和章节直接把大量未来能力写成 `Current Feature Set`。
- 其中多项内容今天仍属于路线目标，不属于已经完成的事实。
- 这份文档适合继续做愿景来源，不适合再做当前事实来源。

证据：

- `docs/past/aim.md:3`
  - 仍把主体章节写成 `MVP 核心特性矩阵 (Current Feature Set)`
- `docs/past/aim.md:11-15`
  - 仍写官方基础插件包、第三方扩展 API、显式/隐式挂载已成立
- `docs/past/aim.md:31-35`
  - 仍写 hover HUD、DDL 视觉化、Flowtime 提醒是当前特性
- `docs/past/aim.md:45-59`
  - 仍写零点击复盘、被动上下文轨迹、BYOK、智能拆解、下一跳建议是当前特性
- `docs/past/aim.md:65`
  - 仍写社交软件全局网关为当前跨端层能力

处理建议：

- 继续把它当作愿景源材料，而不是事实层文档
- 只允许其中经过代码和测试复核的部分进入 `docs/roadmap/`
- 原文继续保留在 `docs/past/`

## C. 仍然可靠的文档

### 1. `docs/past/ipc-protocol-v2.md`

状态：`current`

理由：

- 规范与现有后端/前端测试方向一致
- 没发现明显被代码推翻的核心协议判断

### 2. `docs/past/ipc-product-first-guardrails.md`

状态：`current`

理由：

- 它本质上是过渡期规则文档
- 当前 repo 仍处于 shared runtime 过渡态
- 文档中的边界限制仍然适用

### 3. `docs/past/ai_architecture_guidelines.md`

状态：`current`

理由：

- 它是治理护栏，不依赖具体某个运行态判断
- 其中关于逐文件对标、payload、边界隔离、检查点和防腐规则的建议仍然适用

## D. 历史文档，不应误判为“过时垃圾”

### 1. `docs/past/hud-v1-postmortem.md`

状态：`historical`

理由：

- 它明确写的是第一轮 HUD 原型失败复盘
- 只要不把它当作“当前系统现状”，它就是有效文档

### 2. `docs/past/windows-launcher-postmortem.md`

状态：`historical`

理由：

- 它明确记录的是 2026-04 的本机 launcher 经验
- 其中原则仍然可复用
- 但其中“当前 launcher 已在本机验证”的表述只适用于那条本地路径，不应外推成通用分发现状

补充核实：

- 2026-04-15 已再次核对当前本地 launcher：
  - `C:\Users\27866\Desktop\flow-hud-control.cmd`
  - `C:\Users\27866\Desktop\flow-hud-control.ps1`
- 因此，roadmap 现在不能再把 launcher 只写成“历史复盘对象”
- 更准确的说法是：
  - 当前存在一条真实可用的本地 launcher 链路
  - 但它仍是机器特定的 operator launcher，不是 repo 内的通用分发方案

### 3. `docs/past/unified-roadmap.md`

状态：`historical`

理由：

- 它已经明确声明“单文件版本已经退役”
- 它的主要作用是把读者导向新的 `docs/roadmap/` 目录
- 只要不把它当作仍在维护的路线正文，它就是有效的历史跳转文档

## E. 对路线图目录的影响

当前 `docs/roadmap/` 目录已经吸收了若干旧文档的判断。

其中需要重新审视的重点是：

- `06-architecture-anchors.md`
  - 不能继续把 `docs/past/architecture.md` 当作当前真相原文
- `05-document-map.md`
  - 应明确标注哪些来源文档已 stale
- `03-workstreams.md`
  - 涉及 plugin / AI / launcher 的判断，需要只保留已核实部分

## F. 修订优先级

当前优先级不是修复 `docs/past/` 原文，而是修复 `docs/roadmap/` 中对这些原文的引用和吸收方式。

建议按这个顺序修 roadmap：

1. `docs/roadmap/01-current-state.md`
2. `docs/roadmap/03-workstreams.md`
3. `docs/roadmap/04-sequencing.md`
4. `docs/roadmap/06-architecture-anchors.md`
5. `docs/roadmap/07-guardrails.md`

理由：

- 这些文件最容易把历史判断误写成当前事实
- `docs/past/` 当前作为档案保留，不承担现行真相职责

## G. 当前结论

现在不能再假设 `docs/` 里的所有内容都可直接融入路线图。

当前更准确的做法是：

- 把 `current` 文档当规则或事实来源
- 把 `historical` 文档当复盘与经验来源
- 把 `stale` 文档当作历史材料保留，只有在被代码重新核实后，才能以新表述重新进入 roadmap 正文
