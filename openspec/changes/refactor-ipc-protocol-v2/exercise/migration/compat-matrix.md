# IPC V2 Compatibility Matrix

## Scope

- Change: `refactor-ipc-protocol-v2`
- Profiles: `unix`, `tcp`
- Roles: `rpc`, `push`
- Validation focus: hello-first, V2-only admission, role enforcement

## Matrix

| Client | Transport | Role | Frame version | First request | Expected result |
|---|---|---|---|---|---|
| CLI (`backend IPCClient.call`) | unix | rpc | v2 | `session.hello` then business method | success |
| TUI (`backend IPCClient.listen_pushes`) | unix | push | v2 | `session.hello` then push stream | success |
| HUD plugin request path | unix | rpc | v2 | `session.hello` then business method | success |
| HUD plugin push path | unix | push | v2 | `session.hello` then push stream | success |
| HUD plugin request path | tcp | rpc | v2 | `session.hello` then business method | success |
| HUD plugin push path | tcp | push | v2 | `session.hello` then push stream | success |
| Any client | unix/tcp | rpc/push | v1 or missing `v` | business method | reject `ERR_UNSUPPORTED_PROTOCOL` or `ERR_INVALID_FRAME` |
| Any client | unix/tcp | rpc/push | v2 | non-hello first request | reject `ERR_INVALID_FRAME` |
| Any client | unix/tcp | push | v2 | business method after hello | reject `ERR_ROLE_MISMATCH` |
| Any client | unix/tcp | duplex | v2 | hello with `duplex` role | reject `ERR_ROLE_MISMATCH` |

## Notes

- Push traffic is server-to-client only.
- `response.result` and `response.error` are XOR (exactly one non-null).
- Keepalive/close control path:
  - `rpc`: `session.ping` request/response allowed.
  - `push`: server `session.keepalive` preferred.
  - shutdown: `ERR_DAEMON_SHUTTING_DOWN` for new RPC and optional `session.closing` push.
