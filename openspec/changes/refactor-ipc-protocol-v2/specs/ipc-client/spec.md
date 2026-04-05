## MODIFIED Requirements

### Requirement: Plugin Initialization and Connection
The IpcClientPlugin MUST initialize transport-agnostic IPC connections using shared V2 contract primitives, and MUST complete `session.hello` negotiation for each role-specific channel before serving HUD traffic.

#### Scenario: Successful role-based initialization
- **WHEN** the plugin is initialized via `setup(ctx)`
- **THEN** it starts a long-lived `push` channel and prepares an `rpc` request channel using configured transport profile
- **AND** each channel performs hello negotiation before business frames are processed

#### Scenario: Hello negotiation fails
- **WHEN** daemon version or role negotiation fails during setup or reconnect
- **THEN** the plugin returns/logs a structured protocol error and enters bounded retry behavior without crashing HUD

### Requirement: Receive and Dispatch Pushes
The plugin MUST receive daemon pushes only from a negotiated `push` role channel, decode payloads with the shared V2 contract, and dispatch adapted HUD events through the existing event bus boundary.

#### Scenario: Push received and adapted
- **WHEN** daemon sends a V2 push frame after successful hello
- **THEN** the plugin decodes it with shared codec, adapts domain payload, and emits `HudEventType.IPC_MESSAGE_RECEIVED` in background

#### Scenario: Push channel reconnects
- **WHEN** the push channel disconnects unexpectedly
- **THEN** the plugin reconnects with backoff and repeats hello negotiation before resuming push dispatch

### Requirement: Send Request messages
The plugin MUST send business requests through a negotiated `rpc` role channel and map daemon structured errors into the plugin contract (`ok`, `result`, `error_code`, `message`) without leaking backend runtime internals.

#### Scenario: Request succeeds
- **WHEN** HUD component calls `request(method, **params)` and daemon returns success
- **THEN** plugin returns `{"ok": true, "result": <value>, "error_code": null, "message": null}`

#### Scenario: Structured daemon error is returned
- **WHEN** daemon responds with a V2 structured error object
- **THEN** plugin maps `error.code` to `error_code` and `error.message` to `message` while preserving a stable API shape

#### Scenario: Protocol mismatch during request
- **WHEN** request channel receives malformed or incompatible protocol data
- **THEN** plugin returns a protocol mismatch error code and does not expose raw backend stack traces to HUD callers
