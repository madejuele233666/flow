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
Backend tests and validation commands MUST be runnable from the `backend/` workspace without depending on frontend test directories.

#### Scenario: Backend test assets are local to the backend workspace
- **WHEN** a contributor inspects backend validation assets after migration
- **THEN** backend tests are stored under `backend/`
- **AND** backend validation instructions do not require the contributor to enter `frontend/`
