# Migration Inventory

## Workspace Targets

- `backend/`: backend runtime source, backend metadata, backend tests
- `frontend/`: frontend runtime source, frontend metadata, frontend tests/config
- Repository root (kept): `openspec/`, `docs/`, `.agent/`, `aim.md`, top-level guidance README

## Applied Moves

- `flow_engine/` -> `backend/flow_engine/`
- `flow_hud/` -> `frontend/flow_hud/`
- `tests/` -> `frontend/tests/`
- `hud_config.example.toml` -> `frontend/hud_config.example.toml`
- `pyproject.toml` -> `backend/pyproject.toml`

## Added/Updated Workspace Metadata

- Added `frontend/pyproject.toml`
- Updated `backend/pyproject.toml` package include list to `flow_engine*`
- Added `backend/README.md`
- Added `frontend/README.md`
- Replaced repository root `README.md` with workspace navigation guide
- Added backend test placeholder `backend/tests/__init__.py`
