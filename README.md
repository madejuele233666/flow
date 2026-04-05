# Flow Repository

This repository is split into two workspaces:

- `backend/`: Flow Engine backend package (`flow_engine`)
- `frontend/`: Flow HUD frontend package (`flow_hud`)

Shared project assets remain at repository root (`openspec/`, `docs/`, `.agent/`, `aim.md`).

## Backend Quick Start

```bash
cd backend
pip install -e ".[dev]"
flow --help
```

## Frontend Quick Start

```bash
cd frontend
pip install -e ".[dev,gui]"
python -m flow_hud.main
```

## Validation

```bash
cd backend && pytest -q
cd frontend && pytest -q
```
