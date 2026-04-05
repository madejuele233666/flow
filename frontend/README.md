# Frontend Workspace

This workspace contains the Flow HUD frontend:

- `flow_hud/` HUD package (Qt adapters, core state/event/hook system, IPC client plugin)
- `tests/` frontend-local tests
- `hud_config.example.toml` HUD configuration example
- `pyproject.toml` frontend package metadata

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

1. `[extensions.ipc-client]` explicit plugin fields (`transport/host/port/socket_path`)
2. env overrides (`FLOW_DAEMON_TRANSPORT`, `FLOW_DAEMON_HOST`, `FLOW_DAEMON_PORT`, `FLOW_DAEMON_SOCKET`)
3. `[connection]` defaults in `hud_config.toml`
4. built-in defaults (`tcp`, `127.0.0.1`, `54321`)

## Test

```bash
cd frontend
pytest -q
```
