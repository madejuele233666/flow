# Flow IPC Protocol V2

## 1. Purpose

This document is the complete normative specification for Flow IPC Protocol V2.

Target:

- a backend daemon can be implemented from this document alone
- a frontend client can be implemented from this document alone
- the two implementations can interoperate without reading any source code

This document defines:

- endpoint discovery and transport profiles
- wire framing and JSON schema
- handshake and connection state machine
- reserved control methods and control events
- structured error semantics
- negotiated operational limits
- retry, timeout, and reconnect behavior
- current business RPC method schemas
- current push event schemas

This document does not require any repository-internal package layout. It describes protocol behavior only.

## 2. Normative Language

The words `MUST`, `MUST NOT`, `REQUIRED`, `SHALL`, `SHALL NOT`, `SHOULD`, `SHOULD NOT`, `MAY`, and `OPTIONAL` are normative.

## 3. Version and Compatibility

- Protocol major version: `2`
- All frames MUST contain top-level field `"v": 2`
- A peer receiving any other major version in a V2 frame MUST treat it as protocol mismatch
- V2 is not backward-compatible with V1

## 4. Transport Profiles

The protocol is transport-neutral. Only two transport names are valid in V2:

- `unix`
- `tcp`

### 4.1 Unix Profile

Use case:

- local Unix-like deployments
- local CLI or TUI

Default endpoint:

- socket path: `~/.flow_engine/daemon.sock`

### 4.2 TCP Profile

Use case:

- Windows HUD
- cross-platform frontend/backend split

Default endpoint:

- host: `127.0.0.1`
- port: `54321`

### 4.3 Transport Equivalence

`unix` and `tcp` MUST use exactly the same frame schema, handshake schema, error codes, and business method semantics. Only connection establishment differs.

### 4.4 Minimum Support Matrix

A conformant V2 implementation pair MUST satisfy this matrix:

- backend daemon MUST listen on `unix` and `tcp` concurrently
- frontend/client implementation MUST support connecting over `unix` and `tcp`

This removes discovery ambiguity between independently implemented peers.

## 5. Endpoint Resolution

This section is not part of the wire format, but it is required for interoperable client behavior.

If a client supports multiple endpoint sources, it MUST resolve the target endpoint in this order:

1. runtime explicit override
2. environment variables
3. client-specific config
4. generic connection config
5. built-in defaults

### 5.1 Recommended Source Names

Runtime explicit override:

- direct constructor argument
- CLI option
- launcher-provided override object

Environment variables:

- `FLOW_DAEMON_TRANSPORT`
- `FLOW_DAEMON_HOST`
- `FLOW_DAEMON_PORT`
- `FLOW_DAEMON_SOCKET`

Recommended config layers:

- client-specific config, for example `[extensions.ipc-client]`
- generic shared config, for example `[connection]`

### 5.2 Resolution Rules

- If resolved transport is `unix`, `socket_path` is REQUIRED
- If resolved transport is `tcp`, `host` and `port` are REQUIRED
- Endpoint resolution affects transport connection only; it MUST NOT change wire payloads
- Built-in default transport MUST be `tcp`
- Built-in default TCP endpoint MUST be `127.0.0.1:54321`
- Built-in default Unix socket path MUST be `~/.flow_engine/daemon.sock`

## 6. Connection Model

V2 is role-aware. Each physical connection negotiates exactly one role.

Valid roles:

- `rpc`
- `push`
- `duplex`

V2 implementations MUST support:

- `rpc`
- `push`

V2 implementations MAY reserve `duplex`, but if unsupported they MUST reject it with `ERR_ROLE_MISMATCH`.

Recommended client topology:

- one long-lived `push` connection
- one ephemeral or pooled `rpc` connection

Rationale:

- push delivery stays independent from RPC latency
- frame direction remains unambiguous

## 7. Encoding and Framing

- Encoding: UTF-8
- Framing: one complete JSON object per line
- Line terminator on send: `\n`
- Receivers SHOULD tolerate `\r\n` by trimming trailing whitespace before JSON parse
- Each line is exactly one frame
- Multi-line JSON is forbidden

Frame size rule:

- frame size is measured in encoded UTF-8 bytes, including the trailing newline
- the server advertises `max_frame_bytes` during handshake
- after handshake, both peers MUST enforce that negotiated limit on incoming and outgoing frames

Unknown-field rule:

- required fields MUST be present
- unknown extra fields MUST be ignored unless a future version explicitly defines stricter behavior

## 8. Primitive Types

### 8.1 Integer

An integer field in this document means:

- JSON number
- no fractional part
- boolean values are NOT integers

### 8.2 Object

An object field means a JSON object, not `null`, not array, not string.

### 8.3 Timestamp

If a timestamp appears in an optional metadata field, use RFC 3339 / ISO 8601 string, for example:

```json
"2026-04-05T12:34:56.789Z"
```

### 8.4 Empty Success Result

Because V2 requires `result` and `error` to be mutually exclusive and exactly one non-null, a successful response MUST NOT use `result: null`.

If a method has no meaningful payload, return:

```json
{ "ok": true }
```

or another non-null JSON value.

## 9. Common Frame Envelope

Every frame MUST contain:

```json
{
  "v": 2,
  "type": "request"
}
```

Required common fields:

- `v`: integer, MUST equal `2`
- `type`: string, one of `request`, `response`, `push`

Optional common field:

- `meta`: object

Recommended `meta` keys:

- `session_id`: string
- `seq`: integer
- `trace_id`: string
- `sent_at`: timestamp string

Receivers MUST NOT require `meta` to exist.

## 10. Request Frame

Schema:

```json
{
  "v": 2,
  "type": "request",
  "id": "req_0001",
  "method": "task.list",
  "params": {},
  "meta": {}
}
```

Required fields:

- `id`: non-empty string
- `method`: non-empty string
- `params`: object

Rules:

- request `id` MUST be unique among in-flight requests on the same connection
- `method` is case-sensitive
- method naming SHOULD use dot namespace form, for example `session.hello`, `task.add`
- for backward compatibility, bare method names are allowed only for `ping` and `status`
- omission of `params` is invalid
- `params: null` is invalid

## 11. Response Frame

Success schema:

```json
{
  "v": 2,
  "type": "response",
  "id": "req_0001",
  "result": {
    "items": []
  },
  "error": null
}
```

Failure schema:

```json
{
  "v": 2,
  "type": "response",
  "id": "req_0001",
  "result": null,
  "error": {
    "code": "ERR_METHOD_NOT_FOUND",
    "message": "unknown method: task.begin",
    "retryable": false,
    "data": {
      "method": "task.begin"
    }
  }
}
```

Required fields:

- `id`: non-empty string
- `result`
- `error`

Rules:

- exactly one of `result` or `error` MUST be non-null
- both non-null is invalid
- both null is invalid
- response `id` MUST equal the triggering request `id`

## 12. Push Frame

Schema:

```json
{
  "v": 2,
  "type": "push",
  "event": "task.state_changed",
  "data": {
    "task_id": 3,
    "old_state": "Ready",
    "new_state": "In Progress"
  },
  "meta": {
    "session_id": "sess_abcd1234",
    "seq": 17
  }
}
```

Required fields:

- `event`: non-empty string
- `data`: object

Rules:

- push traffic is server-to-client only
- a client MUST NOT send `type: "push"` to the server
- a server receiving a client-originated push frame MUST treat it as `ERR_INVALID_FRAME`
- `meta.seq`, if present, MUST be monotonic per connection

## 13. Error Object

Schema:

```json
{
  "code": "ERR_UNSUPPORTED_PROTOCOL",
  "message": "requested protocol range 3..3 not supported",
  "retryable": false,
  "data": {
    "supported_min": 2,
    "supported_max": 2
  }
}
```

Required fields:

- `code`: non-empty string
- `message`: string
- `retryable`: boolean

Optional field:

- `data`: object

Reserved V2 error codes:

- `ERR_UNSUPPORTED_PROTOCOL`
- `ERR_INVALID_FRAME`
- `ERR_METHOD_NOT_FOUND`
- `ERR_INVALID_PARAMS`
- `ERR_CAPABILITY_REQUIRED`
- `ERR_ROLE_MISMATCH`
- `ERR_REQUEST_TIMEOUT`
- `ERR_DAEMON_OFFLINE`
- `ERR_DAEMON_SHUTTING_DOWN`
- `ERR_INTERNAL`

Semantics:

- `ERR_INVALID_FRAME`: wire-level invalidity, malformed JSON, missing required frame fields, wrong first request, wrong direction, invalid handshake shape
- `ERR_INVALID_PARAMS`: method-level parameter validation failure after a valid frame and valid method name have been established
- `ERR_ROLE_MISMATCH`: wrong role usage or unsupported role/transport combination
- `ERR_REQUEST_TIMEOUT`: handler exceeded negotiated request timeout
- `ERR_DAEMON_OFFLINE`: local client-side synthesized connectivity failure; usually not sent by server
- `ERR_DAEMON_SHUTTING_DOWN`: daemon accepted the connection but is refusing new RPC work during shutdown
- `ERR_INTERNAL`: unexpected server failure

## 14. Handshake Overview

Every connection MUST start with `session.hello` as the first request.

Until `session.hello` succeeds:

- client MUST NOT send business methods
- server MUST reject any non-hello first request

After hello success:

- the connection is bound to one role
- negotiated `limits` become active
- business traffic is allowed only if consistent with that role

## 15. `session.hello` Request

Schema:

```json
{
  "v": 2,
  "type": "request",
  "id": "req_hello_01",
  "method": "session.hello",
  "params": {
    "client": {
      "name": "flow-hud",
      "version": "0.1.0"
    },
    "role": "push",
    "transport": "tcp",
    "protocol_min": 2,
    "protocol_max": 2,
    "capabilities": [
      "push.task_state",
      "push.timer"
    ]
  }
}
```

Required `params` fields:

- `client`: object
- `client.name`: non-empty string
- `client.version`: non-empty string
- `role`: string, one of `rpc`, `push`, `duplex`
- `transport`: string, one of `unix`, `tcp`
- `protocol_min`: integer
- `protocol_max`: integer

Optional field:

- `capabilities`: array of strings

Rules:

- `protocol_min` MUST be `<= protocol_max`
- client SHOULD send `protocol_min = 2` and `protocol_max = 2`
- omission of `role`, `transport`, `protocol_min`, or `protocol_max` is `ERR_INVALID_FRAME`

## 16. `session.hello` Success Response

Schema:

```json
{
  "v": 2,
  "type": "response",
  "id": "req_hello_01",
  "result": {
    "session_id": "sess_abcd1234",
    "protocol_version": 2,
    "server": {
      "name": "flow-engine",
      "version": "0.1.0"
    },
    "role": "push",
    "transport": "tcp",
    "capabilities": [
      "push.task_state",
      "push.timer",
      "rpc.task",
      "rpc.templates"
    ],
    "limits": {
      "max_frame_bytes": 65536,
      "request_timeout_ms": 30000,
      "heartbeat_interval_ms": 15000,
      "heartbeat_miss_threshold": 2
    }
  },
  "error": null
}
```

Required `result` fields:

- `session_id`: non-empty string
- `protocol_version`: integer, MUST equal `2`
- `server`: object
- `server.name`: non-empty string
- `server.version`: non-empty string
- `role`: string
- `transport`: string
- `capabilities`: array of strings
- `limits`: object

Capabilities negotiation semantics:

- `capabilities` in hello request is the client-requested feature hint list
- `capabilities` in hello response is the server-accepted feature list for this session
- a server MAY accept all requested capabilities (echo behavior)
- a server MAY return a subset if policy or implementation constraints require filtering
- a server MAY include role baseline capabilities even if they were not explicitly requested
- if capability-sensitive behavior is used, clients SHOULD gate it by response `capabilities`, not request `capabilities`

Flow Engine V2 capability policy (current profile):

- role `rpc` baseline capabilities: `rpc.task`, `rpc.templates`
- role `push` baseline capabilities: `push.task_state`
- role `push` optional capabilities: `push.timer`
- unknown requested capabilities MUST be ignored (not echoed into response)

Required `limits` fields:

- `max_frame_bytes`: positive integer, unit `bytes`
- `request_timeout_ms`: positive integer, unit `milliseconds`
- `heartbeat_interval_ms`: positive integer, unit `milliseconds`
- `heartbeat_miss_threshold`: positive integer, unit `count`

Client verification after success:

- client MUST verify `protocol_version == 2`
- client MUST verify returned `role` equals requested role
- client MUST verify returned `transport` equals requested transport
- mismatch in any of the three MUST be treated as protocol mismatch and the connection MUST be abandoned

## 17. Handshake Failure Rules

### 17.1 Non-hello first request

Server behavior:

- respond with `ERR_INVALID_FRAME` if a request `id` is available
- then close the connection

### 17.2 Unsupported protocol range

Server behavior:

- respond with `ERR_UNSUPPORTED_PROTOCOL`
- set `retryable: false`
- SHOULD include:

```json
{
  "supported_min": 2,
  "supported_max": 2
}
```

- then close the connection

### 17.3 Unsupported role or transport

Server behavior:

- respond with `ERR_ROLE_MISMATCH`
- then close the connection

### 17.4 Invalid hello shape

Examples:

- missing `role`
- missing `capabilities` in hello success response
- `protocol_min: true`
- `limits.max_frame_bytes: false`

Behavior:

- treat as `ERR_INVALID_FRAME`
- do not admit business traffic

## 18. Negotiated Limits

These are operational parameters chosen by the server and activated by hello success.

### 18.1 `max_frame_bytes`

- unit: bytes
- chosen by server
- applied by both peers after hello success

Required behavior:

- reject outgoing frames larger than this limit
- reject incoming frames larger than this limit

### 18.2 `request_timeout_ms`

- unit: milliseconds
- chosen by server
- primarily applies to RPC request/response timeout

Required client behavior:

- a client waiting for an RPC response MUST use this timeout unless a narrower local timeout is intentionally configured

### 18.3 `heartbeat_interval_ms`

- unit: milliseconds
- chosen by server
- used for liveness cadence

### 18.4 `heartbeat_miss_threshold`

- unit: count
- chosen by server
- used by clients to decide reconnect after missing keepalives

Required push-client behavior:

- if no valid push frame or `session.keepalive` arrives for `heartbeat_miss_threshold` consecutive heartbeat windows, the client SHOULD reconnect

## 19. Role Semantics

### 19.1 `rpc` Role

Allowed after hello:

- client-to-server `request`
- server-to-client `response`
- reserved control method `session.ping`
- reserved control method `session.bye`

Forbidden:

- server business push traffic SHOULD NOT be sent on `rpc`
- client MUST NOT treat an `rpc` connection as a push subscription

### 19.2 `push` Role

Allowed after hello:

- server-to-client `push`
- optional reserved control traffic

Forbidden:

- client business requests on a negotiated `push` session

If client sends a business request on a `push` session:

- server MUST return `ERR_ROLE_MISMATCH`
- server MAY keep the connection open

### 19.3 `duplex` Role

- reserved in V2
- if unsupported, reject at hello with `ERR_ROLE_MISMATCH`

## 20. Reserved Control Methods and Events

### 20.1 `session.ping`

Request:

```json
{
  "v": 2,
  "type": "request",
  "id": "req_ping_01",
  "method": "session.ping",
  "params": {}
}
```

Success response:

```json
{
  "v": 2,
  "type": "response",
  "id": "req_ping_01",
  "result": {
    "pong": true
  },
  "error": null
}
```

### 20.2 `session.bye`

Request:

```json
{
  "v": 2,
  "type": "request",
  "id": "req_bye_01",
  "method": "session.bye",
  "params": {}
}
```

Success response:

```json
{
  "v": 2,
  "type": "response",
  "id": "req_bye_01",
  "result": {
    "bye": true
  },
  "error": null
}
```

After success, the receiver MAY close immediately.

### 20.3 `session.keepalive`

This is a server-originated push event on `push` sessions.

Schema:

```json
{
  "v": 2,
  "type": "push",
  "event": "session.keepalive",
  "data": {},
  "meta": {
    "session_id": "sess_abcd1234",
    "seq": 18
  }
}
```

### 20.4 `session.closing`

This is a server-originated final push event during shutdown.

Schema:

```json
{
  "v": 2,
  "type": "push",
  "event": "session.closing",
  "data": {
    "reason": "daemon_shutdown"
  },
  "meta": {
    "session_id": "sess_abcd1234",
    "seq": 99
  }
}
```

Required `data` field:

- `reason`: string

## 21. Server State Machine

### 21.1 States

- `connected`
- `negotiated`
- `closing`
- `closed`

### 21.2 Transition Rules

1. upon TCP or Unix accept, state becomes `connected`
2. only valid first logical request in `connected` is `session.hello`
3. on hello success, state becomes `negotiated`
4. in `negotiated`, role rules apply
5. on `session.bye` or fatal protocol failure, state becomes `closing`
6. socket closes, state becomes `closed`

### 21.3 Fatal Protocol Violations

The receiver SHOULD close the connection after:

- totally unparseable JSON
- parseable frame with impossible envelope
- invalid first request
- invalid hello shape
- incoming frame exceeds negotiated size

## 22. Client Reconnect Behavior

This section is normative for long-lived `push` clients and recommended for others.

### 22.1 Trigger Conditions

Reconnect on:

- socket EOF
- transport connect failure
- missing heartbeat threshold exceeded
- hello failure caused by transient availability problem

### 22.2 Backoff

Recommended algorithm:

- initial delay: `0.5s`
- multiplier: `1.5`
- jitter: random `0%` to `10%`
- max delay: `10s`

### 22.3 Reconnect Procedure

1. open new transport connection
2. send fresh `session.hello`
3. verify returned `protocol_version`, `role`, and `transport`
4. reactivate negotiated limits
5. resume push handling

## 23. Daemon Shutdown Behavior

When the daemon is shutting down:

- new RPC requests MUST receive `ERR_DAEMON_SHUTTING_DOWN`
- `retryable` SHOULD be `true`
- existing push sessions MAY receive `session.closing`
- sockets MAY then close

Example error:

```json
{
  "v": 2,
  "type": "response",
  "id": "req_0042",
  "result": null,
  "error": {
    "code": "ERR_DAEMON_SHUTTING_DOWN",
    "message": "daemon is shutting down",
    "retryable": true
  }
}
```

## 24. Business RPC API

This section defines the current application-level methods carried by V2.

### 24.1 `ping`

Purpose:

- legacy application ping

Request:

```json
{
  "method": "ping",
  "params": {}
}
```

Success result:

```json
"pong"
```

Note:

- this is not the same as `session.ping`

### 24.2 `status`

Request params:

```json
{}
```

Success result when no active task:

```json
{
  "active": null,
  "total_tasks": 12
}
```

Success result when there is an active task:

```json
{
  "active": {
    "id": 3,
    "title": "Write protocol doc",
    "state": "In Progress",
    "priority": 1
  },
  "total_tasks": 12
}
```

### 24.3 `task.list`

Request params:

```json
{
  "show_all": false,
  "filter_state": "In Progress",
  "filter_tag": "backend",
  "filter_priority": "1-2"
}
```

All request fields are optional.

Field meanings:

- `show_all`: boolean, default `false`
- `filter_state`: string task state
- `filter_tag`: string tag
- `filter_priority`: string, either single priority like `"2"` or inclusive range like `"1-3"`

Success result:

```json
[
  {
    "id": 3,
    "title": "Write protocol doc",
    "state": "In Progress",
    "priority": 1,
    "ddl": "04-30",
    "score": 91.2
  }
]
```

Result item fields:

- `id`: integer
- `title`: string
- `state`: string
- `priority`: integer
- `ddl`: string `MM-DD` or `null`
- `score`: number or `null`

### 24.4 `task.add`

Two modes exist: direct-add mode and template mode.

#### Direct-add mode

Request params:

```json
{
  "title": "Write protocol doc",
  "priority": 1,
  "ddl": "2026-04-30",
  "tags": ["docs", "ipc"]
}
```

Required fields:

- `title`

Optional fields:

- `priority`: integer, default `2`
- `ddl`: string `YYYY-MM-DD`
- `tags`: array of strings

Success result:

```json
{
  "id": 14,
  "title": "Write protocol doc",
  "priority": 1
}
```

#### Template mode

Request params:

```json
{
  "template_name": "weekly-review",
  "title": "Weekly Review",
  "priority": 2,
  "ddl": "2026-04-12"
}
```

Required fields:

- `template_name`

Optional fields:

- `title`
- `priority`
- `ddl`

Success result:

```json
{
  "template": "weekly-review",
  "tasks": [
    {
      "id": 20,
      "title": "Collect notes",
      "priority": 2
    }
  ]
}
```

### 24.5 `task.start`

Request params:

```json
{
  "task_id": 14
}
```

Required fields:

- `task_id`: integer

Preconditions:

- task with `task_id` MUST exist
- target task state MUST allow transition to `In Progress` (from `Ready` or `Scheduled`)

Failure mapping:

- missing/invalid `task_id` SHOULD return `ERR_INVALID_PARAMS`
- task not found SHOULD return `ERR_INVALID_PARAMS`
- illegal state transition SHOULD return `ERR_INVALID_PARAMS`

Success result:

```json
{
  "id": 14,
  "title": "Write protocol doc",
  "paused": [11, 12]
}
```

### 24.6 `task.done`

Request params:

```json
{}
```

Behavior:

- operates on the currently active task

Preconditions:

- at least one task in `In Progress` state MUST exist

Failure mapping:

- no active task SHOULD return `ERR_INVALID_PARAMS`

Success result:

```json
{
  "id": 14,
  "title": "Write protocol doc"
}
```

### 24.7 `task.pause`

Request params:

```json
{}
```

Behavior:

- operates on the currently active task

Preconditions:

- at least one task in `In Progress` state MUST exist

Failure mapping:

- no active task SHOULD return `ERR_INVALID_PARAMS`

Success result:

```json
{
  "id": 14,
  "title": "Write protocol doc"
}
```

### 24.8 `task.resume`

Request params:

```json
{
  "task_id": 14
}
```

Required fields:

- `task_id`: integer

Preconditions:

- task with `task_id` MUST exist
- if current state is `Paused`, transition target is `In Progress`
- if current state is `Blocked`, transition target is `Ready`
- all other states are invalid for `task.resume`

Failure mapping:

- missing/invalid `task_id` SHOULD return `ERR_INVALID_PARAMS`
- task not found SHOULD return `ERR_INVALID_PARAMS`
- invalid current state SHOULD return `ERR_INVALID_PARAMS`

Success result:

```json
{
  "id": 14,
  "title": "Write protocol doc",
  "state": "Ready"
}
```

Allowed success `state` values for this method:

- `In Progress`
- `Ready`

### 24.9 `task.block`

Request params:

```json
{
  "task_id": 14,
  "reason": "waiting for API key"
}
```

Required fields:

- `task_id`

Optional fields:

- `reason`: string, default empty string

Preconditions:

- task with `task_id` MUST exist

Failure mapping:

- missing/invalid `task_id` SHOULD return `ERR_INVALID_PARAMS`
- task not found SHOULD return `ERR_INVALID_PARAMS`

Success result:

```json
{
  "id": 14,
  "title": "Write protocol doc",
  "reason": "waiting for API key"
}
```

### 24.10 `task.breakdown`

Request params:

```json
{
  "task_id": 14
}
```

Required fields:

- `task_id`: integer

Preconditions:

- task with `task_id` MUST exist

Failure mapping:

- missing/invalid `task_id` SHOULD return `ERR_INVALID_PARAMS`
- task not found SHOULD return `ERR_INVALID_PARAMS`

Success result:

```json
[
  "Read current IPC code",
  "Write protocol document",
  "Review interoperability"
]
```

### 24.11 `task.export`

Request params:

```json
{
  "fmt": "json",
  "show_all": false
}
```

Optional fields:

- `fmt`: string, default `json`
- `show_all`: boolean, default `false`

Success result:

- a string
- content format depends on `fmt`

Examples:

- for `json`, result is a JSON string
- for `csv`, result is a CSV string

### 24.12 `templates.list`

Request params:

```json
{}
```

Success result:

```json
[
  ["weekly-review", "Weekly review workflow"],
  ["study-session", "Focused study session"]
]
```

Each item is a two-element array:

1. template name
2. template description

### 24.13 `plugins.list`

Request params:

```json
{}
```

Success result:

```json
[
  {
    "name": "ipc-client",
    "version": "0.2.0",
    "description": "V2 IPC client with transport/session/message boundaries"
  }
]
```

### 24.14 Task Lifecycle Transition Contract

Task lifecycle RPC methods in this document follow the state-transition whitelist below:

| From | To |
|---|---|
| `Draft` | `Ready`, `Canceled` |
| `Ready` | `Scheduled`, `In Progress`, `Canceled` |
| `Scheduled` | `In Progress`, `Ready`, `Canceled` |
| `In Progress` | `Paused`, `Blocked`, `Done` |
| `Paused` | `In Progress`, `Canceled` |
| `Blocked` | `Ready`, `Canceled` |
| `Done` | (none) |
| `Canceled` | (none) |

Method-specific implications:

- `task.start` targets `In Progress`
- `task.pause` targets `Paused`
- `task.done` targets `Done`
- `task.block` targets `Blocked`
- `task.resume` targets `In Progress` (when source `Paused`) or `Ready` (when source `Blocked`)

If a requested action violates this whitelist, server SHOULD return `ERR_INVALID_PARAMS`.

## 25. Push Event API

This section defines application push events in addition to reserved session events.

### 25.1 `task.state_changed`

Schema:

```json
{
  "v": 2,
  "type": "push",
  "event": "task.state_changed",
  "data": {
    "task_id": 14,
    "old_state": "Ready",
    "new_state": "In Progress"
  }
}
```

Required `data` fields:

- `task_id`: integer
- `old_state`: string
- `new_state`: string

### 25.2 `timer.tick`

Status:

- OPTIONAL extension event
- servers MUST emit it only to sessions where capability `push.timer` is accepted in hello response

Schema:

```json
{
  "v": 2,
  "type": "push",
  "event": "timer.tick",
  "data": {
    "tick": 37,
    "task_id": 14,
    "type": "focus"
  }
}
```

Required `data` fields:

- `tick`: integer, monotonic counter in seconds since current focus timer start

Optional `data` fields:

- `task_id`: integer
- `type`: string, currently `focus`
- `elapsed`: integer, alias of `tick` for UI convenience
- `title`: string, task title snapshot

Sender rule:

- sender SHOULD include `tick` and MAY include optional fields
- if both `tick` and `elapsed` are present, receivers SHOULD treat them as equivalent counters

## 26. Task State Values

The following task state strings are valid:

- `Draft`
- `Ready`
- `Scheduled`
- `In Progress`
- `Paused`
- `Blocked`
- `Done`
- `Canceled`

These strings are case-sensitive.

## 27. Failure Handling Matrix

| Situation | Required behavior |
|---|---|
| invalid JSON | log and close; response may be impossible |
| parseable frame but missing required envelope field | `ERR_INVALID_FRAME`, then MAY close |
| non-hello first request | `ERR_INVALID_FRAME`, then close |
| unsupported protocol range | `ERR_UNSUPPORTED_PROTOCOL`, then close |
| unsupported role or transport | `ERR_ROLE_MISMATCH`, then close |
| client sends push frame | `ERR_INVALID_FRAME`, then MAY close |
| unknown method | `ERR_METHOD_NOT_FOUND`, keep connection open |
| method params invalid | SHOULD return `ERR_INVALID_PARAMS`; legacy implementations MAY return `ERR_INTERNAL` |
| handler timeout | `ERR_REQUEST_TIMEOUT`, keep connection open |
| daemon shutting down | `ERR_DAEMON_SHUTTING_DOWN`, keep connection open or close after drain |
| internal server exception | `ERR_INTERNAL` |

## 28. Full Example: RPC Session

### 28.1 Hello

Client:

```json
{"v":2,"type":"request","id":"h1","method":"session.hello","params":{"client":{"name":"flow-cli","version":"0.1.0"},"role":"rpc","transport":"unix","protocol_min":2,"protocol_max":2,"capabilities":[]}}
```

Server:

```json
{"v":2,"type":"response","id":"h1","result":{"session_id":"sess_1001","protocol_version":2,"server":{"name":"flow-engine","version":"0.1.0"},"role":"rpc","transport":"unix","capabilities":["rpc.task","rpc.templates"],"limits":{"max_frame_bytes":65536,"request_timeout_ms":30000,"heartbeat_interval_ms":15000,"heartbeat_miss_threshold":2}},"error":null}
```

### 28.2 Business Request

Client:

```json
{"v":2,"type":"request","id":"r1","method":"task.list","params":{"show_all":false}}
```

Server:

```json
{"v":2,"type":"response","id":"r1","result":[{"id":1,"title":"Write protocol doc","state":"Ready","priority":1,"ddl":null,"score":88.7}],"error":null}
```

### 28.3 Graceful Close

Client:

```json
{"v":2,"type":"request","id":"b1","method":"session.bye","params":{}}
```

Server:

```json
{"v":2,"type":"response","id":"b1","result":{"bye":true},"error":null}
```

## 29. Full Example: Push Session

### 29.1 Hello

Client:

```json
{"v":2,"type":"request","id":"h2","method":"session.hello","params":{"client":{"name":"flow-hud","version":"0.1.0"},"role":"push","transport":"tcp","protocol_min":2,"protocol_max":2,"capabilities":["push.task_state","push.timer"]}}
```

Server:

```json
{"v":2,"type":"response","id":"h2","result":{"session_id":"sess_2001","protocol_version":2,"server":{"name":"flow-engine","version":"0.1.0"},"role":"push","transport":"tcp","capabilities":["push.task_state","push.timer"],"limits":{"max_frame_bytes":65536,"request_timeout_ms":30000,"heartbeat_interval_ms":15000,"heartbeat_miss_threshold":2}},"error":null}
```

### 29.2 Keepalive

Server:

```json
{"v":2,"type":"push","event":"session.keepalive","data":{},"meta":{"session_id":"sess_2001","seq":1}}
```

### 29.3 Business Push

Server:

```json
{"v":2,"type":"push","event":"task.state_changed","data":{"task_id":14,"old_state":"Ready","new_state":"In Progress"},"meta":{"session_id":"sess_2001","seq":2}}
```

## 30. Conformance Checklist

A backend implementation is conformant only if it:

- listens on both supported transports (`unix` + `tcp`) concurrently
- accepts `session.hello` as the first request only
- enforces `rpc` and `push` role semantics
- returns structured errors with reserved codes
- advertises full `limits` object on hello success
- enforces negotiated frame size
- supports `session.ping`, `session.bye`, `session.keepalive`, `session.closing`

A frontend implementation is conformant only if it:

- resolves endpoints deterministically
- performs hello before business traffic on every channel
- verifies hello success fields, not just shape
- enforces negotiated limits
- reconnects push channels with backoff
- treats malformed protocol data as protocol mismatch
- does not send client-originated push frames

## 31. Reference Defaults

These are recommended implementation defaults, not wire constants:

- default transport: `tcp`
- Unix socket path: `~/.flow_engine/daemon.sock`
- TCP host: `127.0.0.1`
- TCP port: `54321`
- `max_frame_bytes`: `65536`
- `request_timeout_ms`: `30000`
- `heartbeat_interval_ms`: `15000`
- `heartbeat_miss_threshold`: `2`

Interoperability does not depend on these exact operational defaults because they are negotiated in hello, except for endpoint discovery where both peers need a common starting assumption.
