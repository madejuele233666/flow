## Why

当前 IPC 实现在前后端分别维护 wire model 与 codec，已出现潜在协议漂移风险；同时缺少 `session.hello` 握手、能力协商与结构化错误，无法稳定支撑前后端分仓开发及 Windows HUD 场景。`docs/ipc-protocol-v2.md` 已给出目标契约，需要将现网 V1 升级到可验证、可演进、低耦合的 V2 协议。

## What Changes

- 引入统一的 IPC V2 线协议契约（NDJSON 保留），包含 `v` 版本字段、`session.hello` 握手、connection role（`rpc`/`push`）与 capability 协商。
- **BREAKING** 将错误模型从自由文本 `error: str` 升级为结构化错误对象（稳定 `code`、`message`、`retryable`、可选 `data`），并统一前后端语义与保留错误码表。
- **BREAKING** 在连接建立后强制执行握手与版本协商；未协商成功的连接必须被拒绝并返回明确错误。
- 将协议常量与编解码逻辑收敛为共享契约包，由 backend 与 frontend 同时依赖，移除双端重复定义。
- 明确 transport/profile 与业务 method/event 解耦边界，确保 Unix Socket 与 TCP 仅在传输适配层差异化。
- 补充握手矩阵、协议黄金帧与跨传输互通验证，防止后续演进引入协议回归。

## Capabilities

### New Capabilities
- `ipc-protocol-v2-contract`: 定义 V2 统一线协议、握手协商、连接角色、能力协商与结构化错误语义，以及共享契约包的单一事实来源要求。

### Modified Capabilities
- `tcp-ipc-transport`: 将 TCP 传输从“仅兼容 V1 JSON-Lines”升级为“强制 V2 握手与协商、统一错误语义、与 Unix 传输等价”。
- `ipc-client`: 将 HUD IPC 客户端从 Unix-only/V1 风格提升为基于共享契约、支持 V2 握手与稳定错误映射的客户端能力。

## Risk Tier

- `STRICT`: 本次变更涉及跨进程协议主干、前后端公开边界与兼容性迁移，包含 breaking wire 语义与多传输并发场景；若设计或验证不足会直接导致 CLI/HUD 与 daemon 互通中断，因此需要严格设计与门禁验证。

## Impact

- Affected code: `backend/flow_engine/ipc/*`, `frontend/flow_hud/plugins/ipc/*`, 相关适配器与测试。
- Affected APIs: IPC 报文结构、握手流程、错误返回契约、连接角色行为。
- Affected systems: Daemon IPC server、HUD IPC plugin、CLI/TUI 调用链路、跨平台（Unix/TCP）互通。
- Dependencies: 新增或抽离共享协议契约包（供 frontend/backend 同步消费）。
- Expected skills: `openspec-architect`, `openspec-artifact-verify`, `openspec-verify-change`。
