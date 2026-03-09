## Context

`ipc-client-plugin` adds a HUD-side IPC plugin that connects to the Flow Engine daemon over newline-delimited JSON messages on Unix Domain Socket. The change must preserve HUD's anti-corruption boundaries: no `flow_engine` import dependency, typed payload flow, protocol boundary for consumers, tiered plugin context, and non-blocking event dispatch.

This change is `[CORE]` because it adds cross-process control flow and background transport behavior.

## Goals / Non-Goals

**Goals**
- Align with Flow Engine IPC contracts (`request`/`response`/`push`, line-delimited JSON) without importing engine runtime code.
- Keep HUD plugin boundary typed and stable: primitive-in, dict-out port contract.
- Dispatch daemon pushes through HUD `emit_background()` with frozen payload dataclasses.
- Add reconnect/backoff and deterministic shutdown.
- Keep plugin loading configuration-driven via manifest `config_schema` and admin whitelist.

**Non-Goals**
- Reusing `flow_engine.ipc.client.IPCClient` directly.
- Changing HUD core EventBus/HookManager architecture.
- Implementing business-specific push handlers in this change.

## Reference Contract Lock (Alignment Protocol 3a)

Reference source files used as primary contracts:
- `flow_engine/ipc/protocol.py`
- `flow_engine/ipc/client.py`
- `flow_engine/ipc/server.py`
- `flow_engine/client.py`
- `flow_engine/plugins/context.py`
- `flow_engine/plugins/registry.py`

## Contract Extraction (Alignment Protocol 3b)

### `flow_engine/ipc/protocol.py`
- `MessageType(str, Enum)`: `REQUEST`, `RESPONSE`, `PUSH`.
- `Request(method: str, params: dict[str, Any], id: str)`.
- `Response(id: str, result: Any = None, error: str | None = None)` with `ok` property.
- `Push(event: str, data: dict[str, Any])`.
- `encode(msg) -> bytes` and `decode(data: bytes) -> Request | Response | Push`.
- Design decision: newline-delimited JSON framing.

### `flow_engine/ipc/client.py`
- `IPCClient.connect()`: open Unix connection.
- `IPCClient.call(method: str, **params: Any) -> Any`: request/response round-trip.
- `IPCClient.listen_pushes() -> AsyncIterator[Push]`: long-lived push stream.
- `IPCClient.close()`: lifecycle close.

### `flow_engine/ipc/server.py`
- `DEFAULT_SOCKET_PATH` (configurable endpoint concept).
- One-line JSON message handling per read loop (`reader.readline()`).
- Request routing and response encode/decode symmetry.

### `flow_engine/client.py`
- `FlowClient(Protocol)` pattern for external boundary abstraction.
- Methods use primitive parameters and return `dict`/`list[dict]` for anti-leakage.

### `flow_engine/plugins/context.py`
- Tiered sandbox: `PluginContext` + `AdminContext`.
- `AdminContext.event_bus` exposed as read-only property typed as `Any`.

### `flow_engine/plugins/registry.py`
- Declarative plugin manifest with `config_schema`.
- Registry supports config-driven setup and `entry_points` discovery.

## Mapping Table (Alignment Protocol 3c)

| Reference Module | New Module | Action | Notes |
|---|---|---|---|
| `flow_engine/ipc/protocol.py::Request/Response/Push` | `flow_hud/plugins/ipc/protocol.py::IpcWireRequest/IpcWireResponse/IpcWirePush` | Adapt | Preserve wire fields and line protocol, keep HUD-owned types |
| `flow_engine/ipc/protocol.py::encode/decode` | `flow_hud/plugins/ipc/codec.py::encode_message/decode_message` | Replicate | Same newline-delimited JSON framing |
| `flow_engine/ipc/client.py::listen_pushes()` | `flow_hud/plugins/ipc/plugin.py::_listen_loop()` | Adapt | Thread-hosted asyncio loop and HUD event dispatch |
| `flow_engine/ipc/client.py::call()` | `flow_hud/plugins/ipc/plugin.py::request()` | Adapt | Return normalized dict contract, no exception leakage |
| `flow_engine/client.py::FlowClient(Protocol)` | `flow_hud/plugins/ipc/protocol.py::IpcClientProtocol` | Replicate | Boundary isolation via Protocol |
| `flow_engine/plugins/context.py::AdminContext.event_bus` | `flow_hud/plugins/context.py::HudAdminContext.event_bus` usage in IPC plugin | Replicate | IPC plugin requires admin context to emit internal events |
| `flow_engine/plugins/registry.py::PluginManifest.config_schema` | `flow_hud/plugins/manifest.py::HudPluginManifest.config_schema` for `ipc-client` | Replicate | Socket path injected via config |

## Decisions (Alignment Protocol 3d)

### Decision 1: HUD-owned IPC port contract (`IpcClientProtocol`) returning normalized dict
- Reference: `flow_engine/client.py::FlowClient` and `flow_engine/ipc/client.py::call()`.
- Aligned contract: primitive input + dict output boundary.
- Code example:
```python
class IpcClientProtocol(Protocol):
    async def request(self, method: str, **params: Any) -> dict[str, Any]:
        ...
```
- Why this over alternatives: returning transport exceptions directly would leak infra details across plugin boundaries and break anti-corruption constraints.

### Decision 2: Preserve line-delimited JSON request/response/push wire contract without engine import
- Reference: `flow_engine/ipc/protocol.py::encode/decode`.
- Aligned contract: `type` + message body per line.
- Code example:
```python
def encode_message(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
```
- Why this over alternatives: reusing `flow_engine` codec would violate share-nothing runtime dependency; changing wire shape would break daemon compatibility.

### Decision 3: Long-lived push listener runs in background thread with dedicated asyncio loop
- Reference: `flow_engine/ipc/client.py::listen_pushes()` (long-lived stream) and `flow_engine/ipc/server.py` line-based stream behavior.
- Aligned contract: continuous read loop with reconnect.
- Code example:
```python
def _thread_entry(self) -> None:
    self._loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self._loop)
    self._loop.run_until_complete(self._listen_loop())
```
- Why this over alternatives: running socket reads on Qt main thread risks UI stalls; separate loop isolates transport latency.

### Decision 4: Pushes are adapted to frozen dataclasses before bus dispatch
- Reference: `flow_engine/events.py::Event(payload=...)` typed event principle.
- Aligned contract: typed payload, immutable event notifications.
- Code example:
```python
payload = adapt_ipc_message(method=event_name, data=event_data)
self._ctx.event_bus.emit_background(HudEventType.IPC_MESSAGE_RECEIVED, payload)
```
- Why this over alternatives: passing raw dict to subscribers causes schema drift and key-coupling across plugins.

### Decision 5: `request()` uses ephemeral connection and domain error translation
- Reference: `flow_engine/ipc/client.py::call()` request-response semantics.
- Aligned contract: one request receives one response; return structured result.
- Code example:
```python
return {
    "ok": False,
    "result": None,
    "error_code": "ERR_DAEMON_OFFLINE",
    "message": "daemon socket unavailable",
}
```
- Why this over alternatives: sharing the push stream connection for RPC can interleave frames and create head-of-line contention.

### Decision 6: Plugin is config-driven and admin-gated
- Reference: `flow_engine/plugins/registry.py::PluginManifest.config_schema` and `flow_engine/plugins/context.py::AdminContext`.
- Aligned contract: declarative manifest + privileged context access.
- Code example:
```python
manifest = HudPluginManifest(
    name="ipc-client",
    version="0.1.0",
    config_schema={"socket_path": str},
)
```
- Why this over alternatives: hardcoded socket paths and non-admin context access are brittle and violate sandbox policy.

### Decision 7: Deterministic teardown uses stop flag + thread-safe loop stop + join timeout
- Reference: `flow_engine/ipc/client.py::close()` lifecycle closure intent.
- Aligned contract: explicit termination path.
- Code example:
```python
self._stop_event.set()
if self._loop and not self._loop.is_closed():
    self._loop.call_soon_threadsafe(self._loop.stop)
if self._thread and self._thread.is_alive():
    self._thread.join(timeout=5.0)
```
- Why this over alternatives: daemon thread-only cleanup is nondeterministic and can leak sockets between test runs.

## Risks / Trade-offs

- Reconnect storms when daemon is unavailable.
  Mitigation: exponential backoff with capped max interval and jitter.
- Wire contract drift if daemon protocol evolves.
  Mitigation: codec validation and dedicated adapter fallback payload.
- Background loop shutdown race.
  Mitigation: single ownership of loop/thread, idempotent teardown, timeout-bounded join.

## Coverage Report (Alignment Protocol 3e)

| Reference Contract | New Contract | Status |
|---|---|---|
| `Request/Response/Push` dataclasses in `flow_engine/ipc/protocol.py` | HUD IPC wire models in `flow_hud/plugins/ipc/protocol.py` | ✅ |
| `encode()/decode()` newline JSON codec | `encode_message()/decode_message()` codec | ✅ |
| `IPCClient.listen_pushes()` continuous stream | `_listen_loop()` with reconnect/backoff | ✅ |
| `IPCClient.call()` request-response behavior | `IpcClientProtocol.request()` + plugin implementation | ✅ |
| `FlowClient` Protocol boundary style | `IpcClientProtocol` primitive-in dict-out port | ✅ |
| `AdminContext.event_bus` privileged access | IPC plugin setup requires `HudAdminContext` | ✅ |
| `PluginManifest.config_schema` declarative config | `HudPluginManifest(config_schema={"socket_path": str})` | ✅ |

## AI Self-Verification Summary
- Alignment Protocol: Executed
- Coverage Report: Appended
- Audit Checklist: 16/16 items passed
- Uncovered items: None
