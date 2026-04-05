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
flow daemon status
flow tui
```

## Test

```bash
cd backend
pytest -q
```
