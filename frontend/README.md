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

## Test

```bash
cd frontend
pytest -q
```
