---
format: spec
version: 1.0.0
title: "Backend Standalone Package"
status: active
---

## Purpose
The Flow Engine backend MUST remain installable and runnable as an independent workspace package rooted under `backend/`.

## Requirements
### Requirement: Backend SHALL be packaged as a standalone workspace project
Flow Engine MUST be installable and runnable from the `backend/` workspace as an independent Python project, with its own project metadata and package source rooted inside `backend/`.

#### Scenario: Backend workspace contains project metadata
- **WHEN** a contributor inspects the `backend/` directory
- **THEN** it contains the backend project metadata file required to install the engine workspace
- **AND** the Flow Engine package source is located under `backend/`

### Requirement: Backend SHALL preserve existing engine entrypoints after migration
The backend workspace MUST continue to expose the existing engine-facing entrypoints, including the CLI command and daemon-capable runtime, after the repository split.

#### Scenario: Backend CLI remains available after editable install
- **WHEN** a contributor installs the backend workspace in editable mode from `backend/`
- **THEN** the `flow` command remains available
- **AND** backend imports resolve without requiring the frontend workspace

### Requirement: Backend SHALL own backend-local tests and validation assets
Backend tests and validation commands MUST be runnable from the `backend/` workspace without depending on frontend test directories, and MUST include backend-local validation that proves the canonical core task flow for both local direct execution and daemon execution.

#### Scenario: Backend task-flow validation stays local to backend workspace
- **WHEN** a contributor validates the backend workspace after this change
- **THEN** the required validation assets for the canonical core task flow live under `backend/`
- **AND** the contributor does not need to enter `frontend/` to prove local-mode and daemon-mode task lifecycle closure
