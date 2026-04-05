## ADDED Requirements

### Requirement: Repository SHALL expose dedicated frontend and backend workspaces
The repository MUST provide `frontend/` and `backend/` as the primary application workspaces. Runtime application source directories MUST live under those workspaces after migration, and duplicated top-level application source directories MUST NOT remain at the repository root.

#### Scenario: Root layout after migration
- **WHEN** a contributor inspects the repository root after the migration
- **THEN** `frontend/` and `backend/` exist as first-level directories
- **AND** top-level runtime source directories such as `flow_engine/` and `flow_hud/` no longer exist at the repository root

### Requirement: Repository SHALL document workspace-specific entry paths
The repository MUST provide root-level documentation that directs contributors to the correct workspace-specific install, run, and validation commands for frontend and backend development.

#### Scenario: Contributor reads the root guide
- **WHEN** a contributor opens the repository root README after migration
- **THEN** they can identify which commands must be run from `frontend/`
- **AND** they can identify which commands must be run from `backend/`
