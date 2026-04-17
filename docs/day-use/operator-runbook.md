# Gate A Operator Runbook

## Scope

This runbook covers the single-machine closed loop for Horizon A:

- backend-only startup
- frontend-only startup
- operator-local launcher orchestration
- minimum troubleshooting order

The launcher remains orchestration-only and operator-local. It must not become the owner of task-flow or HUD business semantics.

## Backend-Only Startup

Prerequisites:

- backend workspace installed with `.[dev]`
- optional `FLOW_DATA_DIR` chosen if you do not want the default under `~/.flow_engine`

Commands:

```bash
cd backend
flow daemon start
flow daemon status
```

Expected result:

- `flow daemon status` reports the daemon as running
- backend-owned task-flow truth is now available over the configured IPC endpoint

## Frontend-Only Startup

Prerequisites:

- frontend workspace installed with `.[dev,gui]`
- Windows-targeted HUD runtime path
- `HUD_DATA_DIR` points to the directory that contains `hud_config.toml`

Commands:

```bash
cd frontend
python -m flow_hud.windows_main
```

Notes:

- `python -m flow_hud.main` remains a developer desktop path.
- Gate A frontend proof uses the Windows-targeted entrypoint above.
- HUD task-status remains frontend-owned normalization on top of canonical `status`; it does not own backend business truth.

## Operator-Local Launcher Semantics

Current sample:

- `C:\Users\27866\Desktop\flow-hud-control.ps1`
- `C:\Users\27866\Desktop\flow-hud-control.cmd`

Required semantics:

| Action | Expected meaning |
| --- | --- |
| `sync` | Refresh copied frontend/shared assets into the Windows-side target workspace. |
| `status` | Report whether backend and frontend runtime processes are currently up. |
| `start` | Ensure backend and frontend are started from the operator-local orchestration path. |
| `restart` | Recreate the runtime path in an idempotent way. |
| `stop-all` | Stop both runtime sides idempotently. This is the concrete command that satisfies roadmap wording `stop`. |

Boundary rule:

- The launcher may create envs, sync files, and start/stop processes.
- The launcher may not redefine task-status semantics, lifecycle meanings, or HUD degradation rules.

## Minimum Troubleshooting Order

Always check in this order:

1. backend
2. frontend
3. HUD config directory
4. IPC connection state

Suggested checks:

| Step | Check |
| --- | --- |
| Backend | `flow daemon status`, daemon pid/socket location under `FLOW_DATA_DIR`, backend logs if startup failed |
| Frontend | whether `python -m flow_hud.windows_main` or the launcher-started HUD process is actually running |
| HUD config directory | `HUD_DATA_DIR` value, existence of `HUD_DATA_DIR/hud_config.toml`, and expected connection fields inside the file |
| IPC connection state | transport mode, socket/host/port values, daemon availability, protocol mismatch or malformed payload symptoms |

## Representative Offline Drill

Use this drill to confirm the runbook stays actionable:

1. stop the backend daemon while leaving the HUD startup path unchanged
2. confirm the HUD degrades to its canonical `offline` state
3. check backend status
4. check frontend process still running
5. confirm `HUD_DATA_DIR` and `hud_config.toml` still match the expected config source
6. recover the backend and confirm HUD returns to `active` or `empty` instead of staying degraded
