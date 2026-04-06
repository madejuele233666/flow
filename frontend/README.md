# Frontend Workspace

This workspace contains the Flow HUD frontend:

- `flow_hud/` HUD package (Qt adapters, core state/event/hook system, IPC client plugin)
- `tests/` frontend-local tests
- `hud_config.example.toml` HUD configuration example
- `pyproject.toml` frontend package metadata

## Runtime Position

`frontend/` represents the HUD runtime that is intended to run on Windows.

The current repository and day-to-day development environment may live in WSL, but that is a development convenience, not the target deployment assumption for the HUD itself.

When frontend transport or packaging decisions differ between WSL/Linux and Windows, prefer the Windows runtime model unless a document explicitly states that the behavior is development-only.

For the concrete lessons learned while building the Windows desktop launcher and syncing from WSL, see [docs/windows-launcher-postmortem.md](/home/madejuele/projects/flow/docs/windows-launcher-postmortem.md).

## Install

```bash
cd frontend
pip install -e ".[dev,gui]"
```

## Run

```bash
cd frontend
python -m flow_hud.main
```

Connection endpoint precedence:

1. runtime explicit override (`set_runtime_endpoint_override(...)`)
2. env overrides (`FLOW_DAEMON_TRANSPORT`, `FLOW_DAEMON_HOST`, `FLOW_DAEMON_PORT`, `FLOW_DAEMON_SOCKET`)
3. `[extensions.ipc-client]` explicit plugin fields (`transport/host/port/socket_path`)
4. `[connection]` defaults in `hud_config.toml`
5. built-in defaults (`tcp`, `127.0.0.1`, `54321`)

IPC client runtime tuning precedence:

1. `[extensions.ipc-client]` runtime tuning overrides
2. `[ipc_client]` defaults in `hud_config.toml`
3. built-in plugin defaults

## Test

```bash
cd frontend
pytest -q
```
