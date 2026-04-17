# Gate A Day-Use Docs

This directory is the repo-owned operating surface for Horizon A / Gate A.

- [task-flow-contract.md](/home/madejuele/projects/flow/docs/day-use/task-flow-contract.md)
  freezes the canonical task-flow payloads, `status` payload, and cross-entrypoint failure policy.
- [single-machine-baseline.md](/home/madejuele/projects/flow/docs/day-use/single-machine-baseline.md)
  classifies repo defaults, operator-local overrides, and future distribution parameters.
- [operator-runbook.md](/home/madejuele/projects/flow/docs/day-use/operator-runbook.md)
  documents backend-only, frontend-only, and launcher-assisted operation.
- [gate-a-smoke.md](/home/madejuele/projects/flow/docs/day-use/gate-a-smoke.md)
  defines the minimum automated and operator validation scope for Gate A closure.

Current code anchors:

- Backend task-flow truth: `backend/flow_engine/task_flow_runtime.py`
- Local/daemon adapter boundary: `backend/flow_engine/client.py`
- HUD task-status normalization boundary: `frontend/flow_hud/task_status/controller.py`
- HUD config loading boundary: `frontend/flow_hud/core/config.py`

Historical launcher context remains in [docs/past/windows-launcher-postmortem.md](/home/madejuele/projects/flow/docs/past/windows-launcher-postmortem.md), but Gate A execution should prefer the docs in this directory.
