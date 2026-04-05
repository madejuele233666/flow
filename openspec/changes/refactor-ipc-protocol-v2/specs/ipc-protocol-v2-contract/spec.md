## ADDED Requirements

### Requirement: Shared V2 Contract SHALL be the single source of wire truth
The project MUST provide one shared protocol contract package for IPC V2 wire models, `session.*` control method schemas, codec logic, and reserved error-code constants. Backend and frontend MUST consume this package and MUST NOT keep independent duplicate wire schema definitions.

#### Scenario: Frontend and backend use one contract package
- **WHEN** a V2 frame schema or reserved error code changes
- **THEN** backend and frontend obtain the same update from the shared contract package without duplicating local wire dataclasses

#### Scenario: Duplicate wire definition is rejected
- **WHEN** a contributor introduces a new runtime-local IPC wire dataclass outside the shared contract package
- **THEN** protocol contract validation fails and the change is blocked

### Requirement: Base V2 frame shapes SHALL be explicit and validated
All V2 frames MUST include top-level `v` and `type`, and each `type` MUST satisfy required fields and constraints.

#### Scenario: Request frame validation
- **WHEN** `type = request`
- **THEN** frame includes required fields `id`, `method`, and `params` (object)

#### Scenario: Response frame validation
- **WHEN** `type = response`
- **THEN** frame includes required field `id`
- **AND** `result` and `error` are mutually exclusive (exactly one is non-null)

#### Scenario: Push frame validation
- **WHEN** `type = push`
- **THEN** frame includes required fields `event` and `data`
- **AND** push traffic is server-to-client only

### Requirement: `session.hello` schema SHALL be concrete and mandatory
Each V2 connection MUST start with `session.hello` as the first logical request, and request/response fields MUST match the documented schema.

#### Scenario: Hello request uses canonical field set
- **WHEN** a client sends `session.hello`
- **THEN** `params` includes required fields `client{name,version}`, `role`, `transport`, `protocol_min`, `protocol_max`
- **AND** `capabilities` is optional and, if present, is a list of strings

#### Scenario: Hello response uses canonical field set
- **WHEN** the server accepts `session.hello`
- **THEN** `result` includes required fields `session_id`, `protocol_version`, `server{name,version}`, `role`, `transport`, `capabilities`, and `limits`

#### Scenario: Non-hello first request is rejected
- **WHEN** a client sends any non-`session.hello` request before handshake success
- **THEN** the server rejects with `ERR_INVALID_FRAME` (or closes the connection)

#### Scenario: Unsupported protocol range is rejected
- **WHEN** `protocol_min`/`protocol_max` cannot negotiate to supported V2 range
- **THEN** the server returns `ERR_UNSUPPORTED_PROTOCOL` and does not admit business traffic

### Requirement: Connection role semantics MUST be explicit and enforced
The protocol MUST enforce role-specific behavior for `rpc` and `push`; `duplex` MAY be reserved and rejected in V2 with role-mismatch semantics.

#### Scenario: Push-session business request is rejected
- **WHEN** a connection is negotiated as `push` and the client sends a business method
- **THEN** the server returns `ERR_ROLE_MISMATCH`

#### Scenario: Unsupported role or transport combination
- **WHEN** hello negotiation requests unsupported `role`/`transport` combination
- **THEN** the server returns `ERR_ROLE_MISMATCH`

### Requirement: Reserved post-handshake control methods SHALL be normative
The protocol MUST reserve `session.ping` and `session.bye` semantics, and MUST define shutdown behavior for in-flight sessions.

#### Scenario: Keepalive on established session
- **WHEN** either side sends `session.ping` on an established `rpc` connection
- **THEN** peer responds with `{ "pong": true }`

#### Scenario: Push keepalive channel
- **WHEN** a `push` session is established
- **THEN** server-originated `session.keepalive` push event is the preferred liveness path
- **AND** push session business requests remain disallowed

#### Scenario: Graceful close
- **WHEN** caller sends `session.bye` before intentional disconnect
- **THEN** receiver may acknowledge then close the connection gracefully

#### Scenario: Daemon shutdown behavior
- **WHEN** daemon is shutting down
- **THEN** new RPC requests return `ERR_DAEMON_SHUTTING_DOWN`
- **AND** push sessions may receive final `session.closing` event before socket close

#### Scenario: Duplex role is rejected in V2
- **WHEN** hello negotiation requests `duplex` role in V2 implementation
- **THEN** server returns `ERR_ROLE_MISMATCH`

### Requirement: Error payload schema and reserved code registry SHALL be stable
All protocol and method failures MUST return `error` object fields `code`, `message`, `retryable`, and optional `data`. V2 reserved codes MUST include:
`ERR_UNSUPPORTED_PROTOCOL`, `ERR_INVALID_FRAME`, `ERR_METHOD_NOT_FOUND`, `ERR_INVALID_PARAMS`, `ERR_CAPABILITY_REQUIRED`, `ERR_ROLE_MISMATCH`, `ERR_REQUEST_TIMEOUT`, `ERR_DAEMON_OFFLINE`, `ERR_DAEMON_SHUTTING_DOWN`, `ERR_INTERNAL`.

#### Scenario: Method not found
- **WHEN** a client sends an unknown method
- **THEN** the response contains `error.code = ERR_METHOD_NOT_FOUND`
- **AND** `error.retryable = false`

#### Scenario: Malformed frame
- **WHEN** a frame is unparseable or parseable but missing required V2 fields
- **THEN** the receiver returns or logs `ERR_INVALID_FRAME` and may close the connection

### Requirement: Negotiated `limits` schema SHALL be concrete
`session.hello` success response MUST include `result.limits` with required keys:
- `max_frame_bytes` (unit: bytes, chosen by server config)
- `request_timeout_ms` (unit: milliseconds, chosen by server config)
- `heartbeat_interval_ms` (unit: milliseconds, chosen by server config)
- `heartbeat_miss_threshold` (unit: count, chosen by server config)
These values are communicated in hello response and MUST be applied by peers according to key semantics.

#### Scenario: Server advertises concrete limits
- **WHEN** hello negotiation succeeds
- **THEN** response includes all required `limits` keys with numeric values and documented units

#### Scenario: Client applies negotiated limits
- **WHEN** client receives negotiated `limits`
- **THEN** it enforces at least request-timeout and heartbeat/reconnect behavior from the negotiated values rather than undocumented literals
