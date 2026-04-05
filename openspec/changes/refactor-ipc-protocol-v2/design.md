## Context

当前实现在 `backend/flow_engine/ipc/protocol.py` 与 `frontend/flow_hud/plugins/ipc/protocol.py` 各自维护协议模型与 codec，协议演进依赖人工同步，已形成漂移风险。现有链路缺少强制握手、版本与能力协商、结构化错误语义，导致前后端分仓后很难稳定演进。

`docs/ipc-protocol-v2.md` 已定义 V2 目标：保留 NDJSON 可调试性，同时引入 `session.hello`、连接角色、能力协商、结构化错误与传输无关语义。本设计将该文档落地为可实现、可迁移、可验证的工程方案。

## Goals / Non-Goals

**Goals:**
- 建立单一事实来源的 V2 协议契约，供 frontend/backend 共同依赖。
- 强制连接初始化握手（版本、角色、能力、运行参数）并定义失败语义。
- 统一错误模型为稳定 `code` + `message` + `data` 结构，避免自由文本漂移。
- 将传输层（Unix/TCP）与业务协议层解耦，确保协议与传输 profile 正交。
- 提供可分阶段上线的迁移路径与回归验证矩阵。

**Non-Goals:**
- 不改造业务方法命名空间（如 `task.*`、`templates.*`）。
- 不在本次引入远程公网暴露、认证鉴权或多租户能力。
- 不改用 HTTP/WebSocket/gRPC 等新传输协议。

## Decisions

### Decision 1: 引入共享 `flow_ipc` 协议契约包作为唯一协议边界

Problem:
前后端分别维护 wire dataclass/codec，版本更新时无法强约束同步，协议文档与代码容易分叉。

Alternatives considered:
- 保持双端各自定义协议并靠测试对齐。
- 前端直接导入 backend 运行时代码。
- 在仓库内抽离共享协议契约包（被两端依赖）。

Why chosen:
共享契约包同时满足“低耦合”和“单一事实来源”：前后端共享协议定义，但不共享业务运行时。

Stack equivalent:
- `flow_ipc` 包：帧 schema、握手 schema、错误 schema、codec、协议常量。
- backend/frontend 仅通过该包进行序列化与反序列化。

Named deliverables:
- `backend` 与 `frontend` 的 IPC 层删除本地重复 wire dataclass。
- 新增共享契约模块与公共错误码定义。
- 协议黄金帧测试样例（encode/decode 双端一致）。

Failure semantics:
- 若任一端未使用共享契约包导致字段不兼容，连接在握手期失败，返回 `ERR_INVALID_FRAME` 或 `ERR_UNSUPPORTED_PROTOCOL`。

Boundary example:
- Caller: `IpcClientPlugin.request("task.list")`
- Payload: 由共享契约生成 `request` 帧（含 `v`、`id`、`method`、`params`）。
- Forbidden leak: HUD 代码不得导入 `flow_engine.*` 协议实现。
- Returned form: HUD 仅接收共享契约的 `response`/`error` 模型后映射为插件返回字典。

Verification hook:
- 检查前后端代码中不再出现重复 `IpcWire*` 定义。
- 共享契约包的黄金帧测试覆盖 request/response/push/hello/error。

### Decision 2: 强制 `session.hello` 握手与版本/能力/角色协商

Problem:
当前连接建立后直接收发业务帧，版本漂移只能在运行时被动暴露，错误定位晚且不稳定。

Alternatives considered:
- 沿用无握手模型。
- 只协商版本，不协商角色与能力。
- 在每个连接的首个逻辑操作强制 `session.hello`。

Why chosen:
握手是“尽早失败”机制，能在业务调用前阻断不兼容连接，并显式传递角色与可选能力，便于后续增量演进。

Stack equivalent:
- 控制方法：`session.hello`（保留在协议保留命名空间）。
- hello 请求字段：`client{name,version}`、`role`、`transport`、`protocol_min`、`protocol_max`、`capabilities`。
- hello 响应字段：`session_id`、`protocol_version`、`server{name,version}`、`role`、`transport`、`capabilities`、`limits`。

Named deliverables:
- server 端新增握手状态机（未握手前仅允许 `session.hello`，其余首请求全部拒绝）。
- client 端在 `rpc` 与 `push` 连接建立后先执行 hello。
- 明确 `limits`（字段名、单位、值来源）通过 hello 返回。

Failure semantics:
- 非 hello 首请求：返回 `ERR_INVALID_FRAME`（可返回后关闭连接）。
- 版本区间不兼容：返回 `ERR_UNSUPPORTED_PROTOCOL`。
- `role`/`transport` 组合不支持：返回 `ERR_ROLE_MISMATCH`。

Boundary example:
- Caller: HUD `push` 连接启动监听前发起 hello(`role="push"`).
- Payload: `{"method":"session.hello","params":{"client":{"name":"flow-hud","version":"0.1.0"},"role":"push","transport":"tcp","protocol_min":2,"protocol_max":2,"capabilities":["push.timer"]}}`
- Forbidden leak: 业务 push 订阅逻辑不得绕过 hello 状态机。
- Returned form: 若协商成功，客户端才进入 push 读取循环。

Verification hook:
- 握手矩阵测试：Unix/TCP × (`rpc`,`push`) × 协议区间请求（`1..1`、`2..2`、`2..3`、`3..3`）。
- 未握手发送任何非 `session.hello` 首请求必须被拒绝。

### Decision 3: 统一结构化错误模型并规定跨端映射语义

Problem:
当前 `error` 多为自由文本，前端自行推断错误码，导致故障自动处理和可观测性不稳定。

Alternatives considered:
- 继续使用 `error: str`。
- 仅服务端改为结构化错误，客户端保持字符串兜底。
- 双端统一结构化错误对象并保留稳定错误码表。

Why chosen:
统一错误模型可支持机器判断、重试策略与跨端可观测，且能与握手协商错误形成一致语义。

Stack equivalent:
- `error` 对象：`{ "code": str, "message": str, "retryable": bool, "data"?: object }`。
- 稳定代码集：`ERR_UNSUPPORTED_PROTOCOL`、`ERR_INVALID_FRAME`、`ERR_METHOD_NOT_FOUND`、`ERR_INVALID_PARAMS`、`ERR_CAPABILITY_REQUIRED`、`ERR_ROLE_MISMATCH`、`ERR_REQUEST_TIMEOUT`、`ERR_DAEMON_OFFLINE`、`ERR_DAEMON_SHUTTING_DOWN`、`ERR_INTERNAL`。

Named deliverables:
- backend dispatch 与握手流程统一返回结构化错误。
- HUD 插件标准返回中 `error_code` 直接映射 `error.code`，`message` 映射 `error.message`。
- 结构化错误兼容测试与未知错误码兜底策略测试。

Failure semantics:
- 未知错误码：客户端保留原始 `code` 并归类为可观测内部错误，不抹平为无信息字符串。
- 解析失败：返回 `ERR_INVALID_FRAME` 并关闭连接。

Boundary example:
- Caller: `request("task.start", task_id=-1)`
- Payload: V2 request frame。
- Forbidden leak: 插件不得把 backend 原始异常堆栈直接泄露到 HUD UI。
- Returned form: `{"ok": false, "error_code": "ERR_INVALID_PARAMS", "message": "...", "retryable": false, "result": null}`。

Verification hook:
- 错误码一致性测试（server -> client mapping）。
- 非法帧与非法参数场景回归测试。

### Decision 4: 传输适配器与协议层解耦，HUD 使用双连接角色模型

Problem:
当前客户端逻辑将传输细节、协议解析与业务派发耦合在同一插件实现中，扩展 TCP/Windows 时维护成本高。

Alternatives considered:
- 在现有插件中继续叠加条件分支。
- 为 Unix/TCP 分别复制整套客户端实现。
- 抽象 transport adapter，协议处理统一走共享契约，按角色分离连接。

Why chosen:
transport adapter 保持实现替换自由；`rpc`/`push` 分离可避免请求响应与推送流相互干扰。

Stack equivalent:
- `TransportAdapter` 边界：`connect(profile)` / `readline()` / `write()` / `close()`。
- `profile`：`unix` 与 `tcp`；`role`：`rpc` 与 `push`。
- HUD 持有长连接 `push` 通道 + 独立 `rpc` 通道（瞬时或池化）。

Named deliverables:
- 前端 IPC 插件拆分为 transport、session(handshake)、message-dispatch 三层。
- backend server 维持 Unix/TCP 双监听，但共享同一协议分发与握手逻辑。

Failure semantics:
- push 通道断开时只影响事件流；rpc 通道可继续使用并独立重连。
- rpc 通道握手失败不得自动降级到未握手模式。

Boundary example:
- Caller: HUD 初始化时创建 `push` adapter（tcp）。
- Payload: adapter 只处理字节流；协议编解码由共享契约处理。
- Forbidden leak: adapter 不得感知 `task.*` 业务 method。
- Returned form: 插件只向 event bus 发已适配的 HUD payload。

Verification hook:
- 连接故障隔离测试（push 断开不影响 rpc）。
- transport 无关一致性测试（同一业务请求在 unix/tcp 行为等价）。

### Decision 5: 采用“V2-only 准入 + 明确拒绝旧帧”迁移策略

Problem:
如果同时支持 pre-V2 无握手流量，会与“hello-first”核心契约冲突，导致实现与验证边界不一致。

Alternatives considered:
- 兼容窗口桥接 V1 帧。
- V2-only 准入并对旧帧显式拒绝。

Why chosen:
保持协议契约单义性优先于短期兼容性；实现层只需围绕 V2 语义构建，不引入双栈歧义。

Stack equivalent:
- 服务端在握手前仅接受 `session.hello` 控制流。
- 缺失 `v` 或缺失 hello 的业务帧统一按协议不兼容处理。

Named deliverables:
- 明确旧帧拒绝语义与错误码（`ERR_UNSUPPORTED_PROTOCOL` / `ERR_INVALID_FRAME`）。
- 提供升级文档与连通性验证矩阵（仅 V2）。

Failure semantics:
- 收到 pre-V2 帧时直接拒绝并返回结构化错误，不进入业务分发流程。

Boundary example:
- Caller: 旧 HUD 发送 V1 `request`。
- Payload: 无 `v`、无 hello。
- Returned form: 立即返回 `ERR_UNSUPPORTED_PROTOCOL` 或 `ERR_INVALID_FRAME`，连接不进入业务态。

Verification hook:
- 旧帧拒绝测试（Unix/TCP）。
- 缺失 hello 拒绝测试（`rpc`/`push`）。

### Decision 6: 固化 HUD TCP 端点配置边界与优先级

Problem:
TCP 传输能力已是修改目标，但若不固定 `host/port` 配置边界与优先级，前端实现会出现多入口漂移，导致跨平台联调不可重复。

Alternatives considered:
- 继续在插件内部硬编码默认端点。
- 仅支持配置文件，不支持临时覆盖。
- 统一定义配置面与优先级（推荐）。

Why chosen:
统一优先级规则可避免“同一环境不同启动方式”连接目标不一致，同时保留 CI/调试场景下的临时覆盖能力。

Stack equivalent:
- HUD 配置源：`hud_config.toml` 的 `[connection]`。
- 字段：`transport`（`unix|tcp`）、`host`、`port`、`socket_path`。
- 默认值：`transport=tcp` 时 `host=127.0.0.1`、`port=54321`；`transport=unix` 时使用 `socket_path`。
- 解析优先级：插件显式配置 > 环境变量 > `hud_config.toml` > 默认值。

Named deliverables:
- 前端连接配置解析器与端点解析函数（统一给 `rpc`/`push` 通道复用）。
- 配置文档与示例更新（默认与覆盖行为）。

Failure semantics:
- 缺失必填端点字段或字段非法（如端口非整数）时，连接初始化失败并返回结构化配置错误。

Boundary example:
- Caller: HUD 在 Windows 使用 TCP 模式启动。
- Payload: `[connection] host=\"192.168.1.100\" port=9999 transport=\"tcp\"`。
- Returned form: `rpc` 与 `push` 都解析到 `192.168.1.100:9999`，不依赖硬编码路径。

Verification hook:
- 默认端点测试（未配置时连接 `127.0.0.1:54321`）。
- 覆盖优先级测试（显式配置/环境变量/配置文件）。

### Decision 7: 固化角色化控制面语义（keepalive/close/duplex）

Problem:
控制面规则若只写“保留方法”而不区分角色，`session.ping`、`session.keepalive`、`session.bye` 与 `session.closing` 的时序会在实现间分叉。

Alternatives considered:
- 所有角色共用同一控制流规则。
- 仅用 `session.ping`，不使用 push keepalive 事件。
- 按角色定义控制面规则，并在 V2 明确拒绝 `duplex`。

Why chosen:
与 `ipc-protocol-v2` 文档一致的角色化控制面能确保 HUD 长连接与 RPC 短连接行为可预测，并降低时序歧义。

Stack equivalent:
- `rpc`：允许 request/response；双方可用 `session.ping` 做 liveness。
- `push`：优先 server push 事件 `session.keepalive`；业务请求禁用；可在关闭前发 `session.closing`。
- `session.bye`：用于主动优雅断开。
- `duplex`：V2 明确以 `ERR_ROLE_MISMATCH` 拒绝。

Named deliverables:
- 共享契约定义 `session.ping`、`session.bye`、`session.keepalive`、`session.closing` 的角色语义。
- 后端与前端测试覆盖 keepalive、graceful close、shutdown 时序。

Failure semantics:
- 在 `push` 会话上收到业务请求：返回 `ERR_ROLE_MISMATCH`。
- daemon shutdown 期间新 RPC：返回 `ERR_DAEMON_SHUTTING_DOWN`。

Boundary example:
- Caller: push 会话空闲时 server 周期发送 `session.keepalive`。
- Returned form: 客户端按 `heartbeat_miss_threshold` 判定重连，非主动发业务请求保活。

Verification hook:
- `rpc` ping 往返测试。
- `push` keepalive + closing 事件测试。
- `duplex` 协商拒绝测试。

## Independent Verification Plan (STANDARD/STRICT)

Document verification using shared sequence `verify-sequence/default` from:
`openspec/schemas/ai-enforced-workflow/verification-sequence.md`

Two-stage flow:
- Stage 1: read-only verifier subagent (`.codex/agents/verify-reviewer.toml`) review
- Stage 2: Gemini second opinion through logical runner contract `gemini-capture` only when required (`STRICT` or explicit dual gate)

Runtime profile policy:
- Use verifier runtime profile from `.codex/agents/verify-reviewer.toml` by default.

Loop rule:
- Each verify/fix iteration MUST spawn a fresh verifier instance with no inherited verifier memory.

Continuation override vocabulary:
- The only supported continuation overrides are `verify-only`, `dry-run`, and `manual_pause`.
- Do not substitute ad hoc phrases such as "manual stop" or "pause after a stage".

Minimal verification bundle (reuse exactly):
- `change`
- `mode`
- `risk_tier`
- `evidence_paths_or_diff_scope`
- `findings_contract`
- `retry_policy`

### Artifact Verification

- Sequence reference: `verify-sequence/default`
- Mode: `artifact`
- Verifier agent path: `.codex/agents/verify-reviewer.toml`
- Invocation method: built-in subagent API in main process
- Invocation template id: `verify-reviewer-inline-v1`
- Verifier-subagent review scope: `proposal.md`, `design.md`, `tasks.md`, `specs/**/spec.md`
- Authoritative verifier-subagent findings JSON path: `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/verifier/artifact-findings.json`
- Verifier execution evidence JSON path: `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/verifier/artifact-execution.json`
- Verifier runtime profile: from `.codex/agents/verify-reviewer.toml`
- Gemini policy: `STRICT` or explicit dual gate only
- Runner contract: `gemini-capture`
- Prompt inputs: `openspec/changes/refactor-ipc-protocol-v2/proposal.md`, `openspec/changes/refactor-ipc-protocol-v2/design.md`, `openspec/changes/refactor-ipc-protocol-v2/tasks.md`, `openspec/changes/refactor-ipc-protocol-v2/specs/`
- Output format: `authoritative verifier-subagent findings json + execution evidence json` (+ Gemini raw/report when enabled)
- Raw report path (when Gemini enabled): `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/gemini/artifact-raw.json`
- `report_path` (when Gemini enabled): `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/gemini/artifact-report.json`
- Fallback behavior: `retry once; if raw exists but report_path output is missing, run recovery using input_raw_path -> report_path before blocking`
- Originating phase field: `artifact_gate`
- Continuation target on pass: `apply`
- Loop behavior: `artifact mode does not perform implementation auto-fix; a passing artifact gate hands off to apply`
- Execution evidence path: record verifier invocation metadata (`agent_id/start_at/end_at/final_state`) and Gemini resolved command when Gemini runs
- Skill entry point: `openspec-artifact-verify`

### Implementation Verification

- Sequence reference: `verify-sequence/default`
- Mode: `implementation`
- Verifier agent path: `.codex/agents/verify-reviewer.toml`
- Invocation method: built-in subagent API in main process
- Invocation template id: `verify-reviewer-inline-v1`
- Verifier-subagent review scope: `backend/flow_engine/ipc/**`, `frontend/flow_hud/plugins/ipc/**`, protocol contract package and protocol-related tests
- Authoritative verifier-subagent findings JSON path: `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/verifier/implementation-findings.json`
- Verifier execution evidence JSON path: `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/verifier/implementation-execution.json`
- Verifier runtime profile: from `.codex/agents/verify-reviewer.toml`
- Gemini policy: `STRICT` or explicit dual gate only
- Runner contract: `gemini-capture`
- Prompt inputs: implementation diff, `docs/ipc-protocol-v2.md`, protocol tests, migration notes
- Output format: `authoritative verifier-subagent findings json + execution evidence json` (+ Gemini raw/report when enabled)
- Raw report path (when Gemini enabled): `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/gemini/implementation-raw.json`
- `report_path` (when Gemini enabled): `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/gemini/implementation-report.json`
- Fallback behavior: `retry once; if raw exists but report_path output is missing, run recovery using input_raw_path -> report_path before blocking`
- Loop behavior: `if auto-fixable implementation findings exist and budget remains, main flow fixes then reruns with a fresh verifier instance`
- Originating phase field: `apply` or `implementation_verify`
- Continuation target on pass: `implementation_verify` while implementation work already exists; otherwise archive/report completion according to caller flow
- Execution evidence path: record verifier invocation metadata (`agent_id/start_at/end_at/final_state`) and Gemini resolved command when Gemini runs
- Skill entry point: `openspec-verify-change`

## Migration Plan

1. 先落地共享协议契约包与黄金帧测试，建立统一 V2 编解码基础。
2. backend 接入 V2 握手状态机与结构化错误，Unix/TCP 共用同一协议分发层。
3. frontend IPC plugin 改为 transport adapter + session 管理 + message 分发分层，接入 V2 hello 与统一端点配置解析。
4. 实现角色化控制面（`session.ping`/`session.keepalive`/`session.bye`/`session.closing`）并覆盖 shutdown 时序。
5. 完成仅 V2 链路联调（CLI/TUI/HUD；Unix/TCP；rpc/push）与 pre-V2/缺失 hello/duplex 拒绝回归测试。

## Open Questions

- 当前无阻塞性开放问题。

## Risks / Trade-offs

- V2-only 策略会提升旧客户端升级压力；但能避免双栈语义分叉与后续维护成本。
- 共享契约包增加一次依赖管理成本；但换来协议演进的一致性与可测性。
- 双连接模型提高连接管理复杂度；但可隔离 push 与 rpc 干扰，提升稳定性和调试性。
