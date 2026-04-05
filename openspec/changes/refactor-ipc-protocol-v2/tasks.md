## 1. 建立共享 IPC V2 契约与后端接入

- [x] 1.1 使用 `openspec-align` 对 `docs/ipc-protocol-v2.md` 与现有 `backend/flow_engine/ipc/*`、`frontend/flow_hud/plugins/ipc/*` 做字段映射，输出 `openspec/changes/refactor-ipc-protocol-v2/exercise/alignment/ipc-v2-mapping.md`（标注保留字段、重命名字段、废弃字段）。
- [x] 1.2 新增共享契约包（例如 `shared/flow_ipc/`）并定义 V2 帧 schema、`session.hello` 具体请求/响应字段（`client{name,version}`、`role`、`transport`、`protocol_min/max`、`protocol_version`、`session_id`、`server{name,version}`、`capabilities`、`limits`）、结构化错误 schema（`code/message/retryable/data?`）、codec 与保留错误码常量，同时在 `backend/pyproject.toml` 与 `frontend/pyproject.toml` 接入同一依赖来源。
- [x] 1.3 改造 `backend/flow_engine/ipc/protocol.py`、`backend/flow_engine/ipc/server.py`、`backend/flow_engine/ipc/client.py` 以使用共享契约，并实现 hello 状态机（未握手前仅允许 `session.hello`，其余首请求均拒绝）、角色校验（`rpc`/`push`）与结构化错误返回。
- [x] 1.4 补充后端协议验证：黄金帧测试（encode/decode）、握手矩阵测试（Unix/TCP × 角色 × 版本匹配/不匹配）、未握手非 hello 首请求拒绝测试、结构化错误码测试、`response.result/error` 互斥规则测试（新增或更新 `backend/tests/` 对应用例）。
- [x] 1.5 在 server hello 响应实现并固定 `limits` 最小字段集：`max_frame_bytes(bytes)`、`request_timeout_ms(ms)`、`heartbeat_interval_ms(ms)`、`heartbeat_miss_threshold(count)`，并明确字段值来源为 server 配置。
- [x] 1.6 增加协议防回退守卫（测试或 CI 检查）：若在 backend/frontend 运行时代码中新增本地 IPC wire dataclass（不在共享契约包内），验证必须失败。
- [x] 1.7 增加控制方法与方向性验证：`session.ping`/`session.bye` 语义测试、push 仅 server->client 测试、daemon shutdown 下 `ERR_DAEMON_SHUTTING_DOWN` 与 `session.closing` 行为测试。

## 2. 前端 IPC 插件解耦重构与协议升级

- [x] 2.1 使用 `openspec-architect` 将 `frontend/flow_hud/plugins/ipc/plugin.py` 拆分为 transport adapter、session(handshake)、message dispatch 三层，并保持 `IpcClientProtocol` 作为唯一对外边界。
- [x] 2.2 改造 `frontend/flow_hud/plugins/ipc/codec.py` 与 `frontend/flow_hud/plugins/ipc/protocol.py`，移除本地重复 wire dataclass，统一改为共享契约包并支持 V2 结构化错误映射。
- [x] 2.3 实现前端双角色通道：长连接 `push` 通道与独立 `rpc` 通道，并确保每个通道在收发业务帧前完成 `session.hello` 协商。
- [x] 2.4 补充前端验证：push 断连重连并重新 hello、rpc 请求错误映射稳定性、Unix/TCP 传输行为等价性（更新 `frontend/tests/hud/` 下 IPC 相关测试）。
- [x] 2.5 实现客户端对 hello `limits` 的接收与应用（必须覆盖 `request_timeout_ms`、`heartbeat_interval_ms`、`heartbeat_miss_threshold`，并对 `max_frame_bytes` 做帧边界保护），并验证 `rpc` 与 `push` 两个通道都遵循协商值。
- [x] 2.6 实现 HUD TCP 端点配置契约（`[connection] transport/host/port/socket_path`）与固定优先级解析（显式配置 > 环境变量 > 配置文件 > 默认值），并补充默认端点与覆盖行为测试。

## 3. 迁移与文档交付

- [x] 3.1 在后端固化 V2-only 准入策略：pre-V2 或缺失 hello 的业务帧统一返回结构化错误（`ERR_UNSUPPORTED_PROTOCOL` 或 `ERR_INVALID_FRAME`），`push` 会话上的业务请求返回 `ERR_ROLE_MISMATCH`。
- [x] 3.2 更新 `docs/ipc-protocol-v2.md` 与运行说明，明确握手流程、角色语义、错误码表、`limits` 字段协商、V2-only 准入与旧帧拒绝语义。
- [x] 3.3 新增迁移验证记录 `openspec/changes/refactor-ipc-protocol-v2/exercise/migration/compat-matrix.md`，覆盖 CLI/TUI/HUD 在 Unix/TCP、`rpc/push`、pre-V2 拒绝与缺失 hello 拒绝下的预期结果。

## 4. STRICT 验证门禁与修复回路演练

- [x] 4.1 配置并复用共享验证序列 `verify-sequence/default` 的最小 bundle（`change/mode/risk_tier/evidence_paths_or_diff_scope/findings_contract/retry_policy`），固定 `findings_contract=shared-findings-v1`，并声明每次 rerun 使用 fresh verifier instance（无继承记忆）。
- [x] 4.2 执行 artifact 阶段验证（`openspec-artifact-verify`）：通过内置 subagent API + `verify-reviewer-inline-v1` 写入 `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/verifier/artifact-findings.json` 与 `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/verifier/artifact-execution.json`，并在 `STRICT` 下运行 `gemini-capture` 生成 `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/gemini/artifact-raw.json` 与 `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/gemini/artifact-report.json`（失败时执行 `input_raw_path -> report_path` 恢复）。
- [x] 4.3 [Checkpoint] Run verifier-subagent review for artifact bundle/report outputs using `verify-sequence/default`; write authoritative verifier-subagent findings JSON and verifier execution evidence JSON, and ensure each rerun uses a fresh verifier instance (no inherited memory). If Gemini is required by risk tier or explicit dual gate, run logical runner contract `gemini-capture`, write both raw and normalized reports, and if primary execution fails after writing raw, run recovery (`input_raw_path -> report_path`) before blocking. Record verifier invocation metadata (`agent_id/start_at/end_at/final_state`) and Gemini resolved Linux/Windows command (when Gemini runs) in execution evidence, not in task policy prose. Only `verify-only`, `dry-run`, and `manual_pause` may override automatic continuation.
- [x] 4.4 执行 implementation 阶段验证（`openspec-verify-change`）：以 `apply` 或 `implementation_verify` 作为 originating phase，写入 `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/verifier/implementation-findings.json` 与 `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/verifier/implementation-execution.json`，并在 `STRICT` 下运行 `gemini-capture` 生成 `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/gemini/implementation-raw.json` 与 `openspec/changes/refactor-ipc-protocol-v2/exercise/reports/gemini/implementation-report.json`。
- [x] 4.5 [Checkpoint] Run verifier-subagent review for implementation verification report outputs using `verify-sequence/default`; write authoritative verifier-subagent findings JSON and verifier execution evidence JSON, and ensure each rerun uses a fresh verifier instance (no inherited memory). If Gemini is required by risk tier or explicit dual gate, run logical runner contract `gemini-capture`, write both raw and normalized reports, and if primary execution fails after writing raw, run recovery (`input_raw_path -> report_path`) before blocking. Record verifier invocation metadata (`agent_id/start_at/end_at/final_state`) and Gemini resolved Linux/Windows command (when Gemini runs) in execution evidence, not in task policy prose. Only `verify-only`, `dry-run`, and `manual_pause` may override automatic continuation.
