# Gate A Single-Machine Baseline

## Configuration Layers

Gate A treats single-machine setup as three explicit layers.

| Surface | Repo default | Operator-local override | Future distribution parameter |
| --- | --- | --- | --- |
| Backend data root | `FLOW_DATA_DIR` unset -> `~/.flow_engine` | `FLOW_DATA_DIR=/custom/path` | Installer-managed or per-machine packaged data root |
| Backend config file | `FLOW_DATA_DIR/config.toml` | Operator edits local `config.toml` | Product installer generating config |
| Backend IPC paths | `daemon.sock`, `daemon.pid` under backend data dir | Alternate data dir shifts both files together | Distribution-managed service registration |
| Frontend data root | `HUD_DATA_DIR` unset -> `~/.flow_hud` | `HUD_DATA_DIR=/custom/path` | Installer-managed Windows app-data location |
| Frontend config file | `HUD_DATA_DIR/hud_config.toml` | Operator edits local `hud_config.toml` | Packaged config generation or migration |
| Frontend connection defaults | Built-in defaults: `tcp`, `127.0.0.1`, `54321` | `[connection]` or `[extensions.ipc-client]` in `hud_config.toml` | Distribution-specific endpoint discovery |
| Current launcher sample | None | Machine-local PowerShell / desktop entry values such as WSL distro, repo path, and Windows target path | Portable launcher or installer inputs |

## Boundary Rules

- Repo defaults live in repo code:
  - backend: `backend/flow_engine/config.py`
  - frontend: `frontend/flow_hud/core/config.py`
- Operator-local launcher values are real prerequisites, but they are not promoted to repo defaults.
- Future distribution parameters stay deferred until Horizon E work owns them.

## `HUD_DATA_DIR -> hud_config.toml` Rule

The canonical HUD config lookup rule is:

1. choose the HUD data directory
2. resolve `hud_config.toml` inside that directory
3. load connection/runtime defaults from that file

In code this mapping is expressed by `HudConfig.default_config_path(...)`.

Operator rule:

- If `HUD_DATA_DIR` is set, it must point at the directory that contains the `hud_config.toml` used for Gate A startup.
- If `[hud].data_dir` is also set inside `hud_config.toml`, keep it aligned with the same directory during Gate A validation instead of relying on an implicit fallback.

## Clean-Config Startup Exercise

Backend clean-config exercise:

```bash
cd backend
FLOW_DATA_DIR="$PWD/.tmp/gate-a-backend" flow daemon status
```

Expected result:

- command succeeds without undocumented machine-local parameters
- backend data directory is created under the chosen `FLOW_DATA_DIR`

Frontend clean-config exercise:

```bash
cd frontend
mkdir -p "$PWD/.tmp/gate-a-hud"
cp hud_config.example.toml "$PWD/.tmp/gate-a-hud/hud_config.toml"
HUD_DATA_DIR="$PWD/.tmp/gate-a-hud" python - <<'PY'
from flow_hud.core.config import HudConfig
cfg = HudConfig.load()
print(cfg.data_dir)
print(HudConfig.default_config_path(cfg.data_dir))
PY
```

Expected result:

- printed data directory matches `HUD_DATA_DIR`
- printed config path is `HUD_DATA_DIR/hud_config.toml`

## Baseline Consistency Check

Before claiming Gate A closure, record whether each of these matched observed runtime behavior:

- `FLOW_DATA_DIR`
- backend `config.toml`
- `HUD_DATA_DIR`
- `HUD_DATA_DIR/hud_config.toml`
- frontend connection defaults after config load
- any operator-local launcher-injected path or endpoint overrides

If any item depends on oral history rather than a documented source, Gate A baseline validation fails.
