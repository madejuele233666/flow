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

For the current documentation set, start with [docs/roadmap/README.md](/home/madejuele/projects/flow/docs/roadmap/README.md). For the archived Windows launcher postmortem, see [docs/past/windows-launcher-postmortem.md](/home/madejuele/projects/flow/docs/past/windows-launcher-postmortem.md).

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

Windows-targeted Gate A runtime path:

```bash
cd frontend
python -m flow_hud.windows_main
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

## HUD Plugin Hook Safety

UI-facing HUD hooks (`before_widget_register`, transition lifecycle hooks) execute on the HUD runtime thread.

Do:
- Keep hook handlers short and deterministic.
- Return quickly; move long-running work to background event paths or plugin-managed workers.
- Treat hook payloads as the canonical mutation boundary (`before_widget_register` can rewrite slot only).

Don't:
- Block in hook handlers with long network/disk operations.
- Assume hook handlers run in worker threads.
- Mutate Qt widgets from non-HUD threads.

## Test

```bash
cd frontend
pytest -q
```

Gate A frontend-only startup, `HUD_DATA_DIR -> hud_config.toml` rules, and smoke scope live in [docs/day-use/single-machine-baseline.md](/home/madejuele/projects/flow/docs/day-use/single-machine-baseline.md), [docs/day-use/operator-runbook.md](/home/madejuele/projects/flow/docs/day-use/operator-runbook.md), and [docs/day-use/gate-a-smoke.md](/home/madejuele/projects/flow/docs/day-use/gate-a-smoke.md).
