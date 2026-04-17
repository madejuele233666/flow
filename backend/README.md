# Backend Workspace

This workspace contains the Flow Engine backend:

- `flow_engine/` core package (CLI, daemon, state/scheduler/storage/IPC)
- `tests/` backend-local tests
- `pyproject.toml` backend package metadata

## Install

```bash
cd backend
pip install -e ".[dev]"
```

## Run

```bash
cd backend
flow --help
flow daemon start
flow daemon status
flow tui
```

## Test

```bash
cd backend
pytest -q
```

Gate A backend-only run path and smoke scope live in [docs/day-use/operator-runbook.md](/home/madejuele/projects/flow/docs/day-use/operator-runbook.md) and [docs/day-use/gate-a-smoke.md](/home/madejuele/projects/flow/docs/day-use/gate-a-smoke.md).
