# Gate A Task-Flow Contract

## Truth Boundaries

- `TaskFlowRuntime` is the only task-flow business-truth boundary.
- `LocalClient` and `RemoteClient` must preserve the same business payloads and business errors.
- HUD `task-status` consumes only the canonical `status` semantics after frontend normalization.
- RPC transport fields such as `ok`, `error_code`, and `message` belong to the adapter envelope. They are not task-flow business-state fields.

## Canonical Lifecycle Payloads

| Operation | Canonical payload | Notes |
| --- | --- | --- |
| `add` | `id`, `title`, `priority`, `state` | Plain add returns one task payload. Template add wraps the same payload shape under `tasks[]` plus `template`. |
| `start` | `id`, `title`, `state`, `paused`, `restore_report` | `paused` lists auto-paused task ids. `restore_report` is the canonical executable recovery report v2. |
| `pause` | `id`, `title`, `state` | No adapter-specific fields are added. |
| `block` | `id`, `title`, `state`, `reason` | `reason` is canonical block metadata, not HUD-only copy. |
| `resume` | `id`, `title`, `state`, `restore_report` | `resume` publishes the same executable recovery report v2 contract as `start`. |
| `done` | `id`, `title`, `state` | Terminal transition result only. |

## Canonical `restore_report` V2 Payload

Top-level report fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `version` | `int` | Report schema version; B2 uses `2`. |
| `task_id` | `int` | Task being restored. |
| `overall_status` | `str` | One of `empty`, `skipped`, `executed`, `partial`, `failed`, or `unsupported`. |
| `execution_enabled` | `bool` | Whether real restore side effects were allowed by config. |
| `actions` | `list[object]` | Planned action outcomes. Empty when no restorable context exists. |
| `browser_session` | `object` | Browser-session summary, including provenance when inferred from ActivityWatch. |
| `user_message` | `str \| null` | Optional user-facing degradation message. |

Action fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | `str` | Stable action identifier within the report. |
| `type` | `str` | Action type such as `open_url`, `open_file`, `open_workspace`, or `focus_window`. |
| `field` | `str` | Snapshot field that produced the action. |
| `role` | `str` | Product role such as `active`, `secondary`, `workspace`, or `focus`. |
| `target` | `str` | URL, file, workspace, or window title target. |
| `status` | `str` | `skipped`, `executed`, `failed`, or `unsupported`. |
| `reason` | `str` | Empty on success; otherwise stable degradation reason. |
| `source` | `str` | Capture/provider source or provenance. |
| `priority` | `str` | Recovery priority inherited from context semantics. |

`restored_window` is no longer a top-level lifecycle payload field. Window focus, when available, is represented as a `focus_window` action in `restore_report.actions`.

## Canonical `status` Payload

Top-level business result:

| Field | Type | Meaning |
| --- | --- | --- |
| `active` | `object \| null` | `null` means there is no active task. This is the canonical empty-state signal. |
| `break_suggested` | `bool` | Runtime-owned focus hint derived from elapsed time. |

`active` object fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | `int` | Active task id. |
| `title` | `str` | Active task title. |
| `priority` | `int` | Canonical task priority. |
| `state` | `str` | Canonical backend state label. |
| `duration_min` | `int \| null` | Elapsed active duration in minutes. |

HUD task-status is allowed to depend only on:

- `result.active`
- `result.active.id`
- `result.active.title`
- `result.active.state`
- `result.active.duration_min`
- `result.break_suggested`

If any required field is missing or malformed, HUD must degrade to `offline` rather than fabricate a pseudo-active state.

## Canonical Vs Entrypoint-Local Fields

Canonical cross-entrypoint fields:

- All lifecycle payload fields listed above
- All `restore_report` v2 fields listed above
- All `status` business fields listed above

Entrypoint-local or transport-only fields:

- CLI-only formatting such as emoji, sentence phrasing, and ordering
- Daemon RPC envelope fields: `ok`, `error_code`, `message`
- HUD presentation labels such as `No active task` and `Offline`
- Log lines, stack traces, and parser fragments

Rule:

- Entry points may translate the contract into surface-specific copy.
- Entry points may not invent new business meanings from transport fragments or guessed fields.

## Day-Use Failure Taxonomy

| Failure class | Type | Meaning | Primary visibility |
| --- | --- | --- | --- |
| Missing task | Business error | Referenced task id does not exist. | User-visible |
| Illegal transition | Business error | Requested lifecycle step is invalid for current state. | User-visible |
| No active task | Business error | `pause`, `done`, or `status` active lookup found no in-progress task. | User-visible for direct command surfaces; canonical empty state for `status` |
| Multiple active tasks | Business error | Repository state violates single-active invariant. | User-visible and log detail |
| Transition veto | Business error | Hook/plugin veto blocked the transition. | User-visible and log detail |
| Daemon offline | Transport degradation | Remote adapter cannot reach daemon. | User-visible degradation |
| Protocol mismatch | Transport degradation | IPC hello or framing contract does not match. | User-visible degradation and log detail |
| Malformed `status` payload | Transport degradation | `status` payload cannot satisfy canonical contract. | HUD-visible degradation and log detail |
| Snapshot capture / restore failure | Degraded side effect | Context capture or restore failed, but task-flow transition still completed. | Log-only plus `restore_report` degradation where available |
| Restore action skipped / unsupported / failed | Degraded side effect | Executable recovery did not complete all planned actions. | `restore_report` and optional notification |

## Cross-Entrypoint Error-Presentation Matrix

| Failure class | CLI / local direct call | Daemon RPC consumer | HUD task-status |
| --- | --- | --- | --- |
| Missing task | Show stable product-language failure. | Preserve same business meaning after RPC transport. | Not applicable in widget bootstrap path. |
| Illegal transition | Show stable product-language failure. | Preserve same business meaning after RPC transport. | Not applicable in widget bootstrap path. |
| Multiple active tasks | Show operator-visible failure and keep diagnostics secondary. | Preserve same operator-visible failure and keep diagnostics secondary. | Reduce `status` bootstrap to stable `offline` degradation. |
| Daemon offline | Not applicable to local mode. | Surface unavailable/degraded outcome; do not recast as task state. | Render canonical `offline` state. |
| Protocol mismatch | Not applicable to local mode. | Surface degraded connection failure; keep protocol fragments out of primary copy. | Render canonical `offline` state and keep protocol detail log-only. |
| Malformed `status` payload | Not applicable to local mode. | Treat as degraded transport/result contract failure. | Render canonical `offline` state; do not guess fields. |
| Snapshot capture / restore failure | Keep lifecycle result successful if transition succeeded; inspect `restore_report`. | Same behavior after RPC transport. | Task-status remains driven by `status`; other HUD surfaces may consume `restore_report` later. |
| Restore action skipped / unsupported / failed | Keep lifecycle result successful if transition succeeded; summarize `restore_report` in product language. | Preserve report fields after RPC transport. | Task-status ignores this report in Gate B2. |

Primary contract rule:

- User-facing surfaces should expose stable product-language outcomes first.
- Raw exception fragments are diagnostic material, not the primary day-use contract.
