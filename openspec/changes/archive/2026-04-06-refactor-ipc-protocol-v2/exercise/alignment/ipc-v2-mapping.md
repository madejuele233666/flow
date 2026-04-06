# IPC V2 Field Mapping (`ipc-protocol-v2` ↔ current codebase)

## Scope

- Source contract: `docs/ipc-protocol-v2.md`
- Backend baseline: `backend/flow_engine/ipc/protocol.py`, `backend/flow_engine/ipc/server.py`, `backend/flow_engine/ipc/client.py`
- Frontend baseline: `frontend/flow_hud/plugins/ipc/protocol.py`, `frontend/flow_hud/plugins/ipc/codec.py`, `frontend/flow_hud/plugins/ipc/plugin.py`

## Mapping Summary

### 1) Common frame envelope

| V2 field | Current backend | Current frontend | Mapping |
|---|---|---|---|
| `v` | missing | missing | **ADDED** (new required top-level field) |
| `type` | present (`request/response/push`) | present (`request/response/push`) | **RETAINED** |
| NDJSON framing | present | present | **RETAINED** |

### 2) Request frame (`type=request`)

| V2 field | Current backend | Current frontend | Mapping |
|---|---|---|---|
| `id` | present (uuid short id) | present | **RETAINED** |
| `method` | present | present | **RETAINED** |
| `params` | present | present | **RETAINED** |
| `meta` (optional) | missing | missing | **ADDED (optional)** |

### 3) Response frame (`type=response`)

| V2 field | Current backend | Current frontend | Mapping |
|---|---|---|---|
| `id` | present | present | **RETAINED** |
| `result` | present | present | **RETAINED** |
| `error` object | `error: str | None` | `error: str | None` | **RENAMED/EXPANDED**: `str -> {code,message,retryable,data?}` |
| `result/error` XOR | implicit | implicit | **ADDED explicit invariant** |

### 4) Push frame (`type=push`)

| V2 field | Current backend | Current frontend | Mapping |
|---|---|---|---|
| `event` | present | present | **RETAINED** |
| `data` | present | present | **RETAINED** |
| `meta.seq` (recommended) | missing | missing | **ADDED (recommended)** |

### 5) Hello handshake (`session.hello`)

| V2 field | Current backend | Current frontend | Mapping |
|---|---|---|---|
| `client{name,version}` | missing | missing | **ADDED** |
| `role` | missing | missing | **ADDED** |
| `transport` | missing | missing | **ADDED** |
| `protocol_min/protocol_max` | missing | missing | **ADDED** |
| `capabilities[]` | missing | missing | **ADDED** |
| `session_id` (hello result) | missing | missing | **ADDED** |
| `protocol_version` (negotiated) | missing | missing | **ADDED** |
| `server{name,version}` | missing | missing | **ADDED** |
| `limits{...}` | missing | missing | **ADDED** |

### 6) Error model and error-code table

| V2 requirement | Current backend | Current frontend | Mapping |
|---|---|---|---|
| `error.code` | missing | inferred by plugin | **ADDED canonical field** |
| `error.message` | current `error` string | mapped message | **RETAINED (as structured subfield)** |
| `error.retryable` | missing | missing | **ADDED** |
| `error.data` | missing | missing | **ADDED (optional)** |
| Reserved codes (`ERR_UNSUPPORTED_PROTOCOL`, `ERR_INVALID_FRAME`, ...) | incomplete/inconsistent | partial local codes | **RENAMED + STANDARDIZED** |

### 7) Role/control-plane semantics

| V2 rule | Current backend | Current frontend | Mapping |
|---|---|---|---|
| hello-first | missing | missing | **ADDED** |
| `push` role forbids business requests | missing | missing | **ADDED** |
| `session.ping`/`session.bye` | missing | missing | **ADDED** |
| `session.keepalive`/`session.closing` (push path) | partial event concept only | partial adapter concept only | **ADDED + STANDARDIZED** |
| `duplex` rejected in V2 | missing | missing | **ADDED** |

## Deprecated / Removed from V1-style implementation

- Backend/Frontend local duplicated wire dataclasses (`Request/Response/Push` vs `IpcWire*`) as independent protocol sources.
- Free-form `error: str` as canonical failure representation.
- Implicit connection semantics without handshake/role negotiation.

## Compatibility Notes

- Existing method/event namespaces (`task.*`, `templates.*`, `timer.tick`) are retained as business-layer identifiers.
- Transport-neutral framing (NDJSON) is retained; Unix/TCP divergence remains only in adapter layer.
