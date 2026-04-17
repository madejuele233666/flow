# Gate A Smoke Gate

## Required Automated Scope

Backend automated checks:

```bash
cd backend
pytest -q tests/test_task_flow_contract.py tests/test_ipc_v2_server.py
```

This scope proves:

- canonical lifecycle payload parity across local and daemon modes
- canonical `status` payload shape
- IPC V2 server behavior used by the daemon path

Frontend automated checks:

```bash
cd frontend
QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q \
  tests/hud/test_task_flow_contract.py \
  tests/hud/test_task_status_controller.py \
  tests/hud/test_ipc_client_plugin.py \
  tests/hud/test_runtime_profiles.py \
  tests/hud/test_hud_config_contract.py
```

This scope proves:

- HUD consumes canonical task-flow payloads without adapter drift
- HUD normalizes `active / empty / offline` from canonical `status`
- IPC plugin transport degradation stays outside widget semantics
- runtime profile assembly and `HUD_DATA_DIR -> hud_config.toml` mapping remain repo-owned

Prerequisite:

- `frontend/.venv` (or an equivalent frontend-local environment) must have `.[dev,gui]` installed so `PySide6` is available and no required HUD smoke module is skipped.

## Required Operator Validation Scope

Choose one of the following operator validation paths and record which one was used.

Launcher-assisted path:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\27866\Desktop\flow-hud-control.ps1 sync
powershell -ExecutionPolicy Bypass -File C:\Users\27866\Desktop\flow-hud-control.ps1 status
powershell -ExecutionPolicy Bypass -File C:\Users\27866\Desktop\flow-hud-control.ps1 start
powershell -ExecutionPolicy Bypass -File C:\Users\27866\Desktop\flow-hud-control.ps1 restart
powershell -ExecutionPolicy Bypass -File C:\Users\27866\Desktop\flow-hud-control.ps1 stop-all
```

Desktop-entry alternative:

- run the backend-only and frontend-only paths from [operator-runbook.md](/home/madejuele/projects/flow/docs/day-use/operator-runbook.md)
- record the exact backend env, frontend env, `FLOW_DATA_DIR`, `HUD_DATA_DIR`, and `hud_config.toml` source used for that run
- use the same desktop-entry alternative path for the representative offline drill if you are not using the launcher path

## Required Baseline Exercises

Runbook-from-zero:

- execute the backend-only path from a clean `FLOW_DATA_DIR`
- execute the frontend-only path with a fresh `HUD_DATA_DIR`
- confirm `HUD_DATA_DIR/hud_config.toml` is the config source actually used

Offline troubleshooting drill:

- reproduce one representative daemon-offline case
- follow the troubleshooting order from the runbook
- record whether the HUD returned to canonical `active` or `empty` after recovery

## Pass Criteria

Gate A smoke passes only when all of the following are true:

- backend automated checks pass
- frontend automated checks pass
- launcher or desktop-entry validation path is executed and recorded
- runbook-from-zero is executed and recorded
- one representative offline troubleshooting drill is executed and recorded

If an item is blocked by environment prerequisites, record the exact prerequisite and command attempt instead of silently skipping the step.
