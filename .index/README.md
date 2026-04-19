# Repository Index Contract

This directory defines a repository-level external indexing contract rooted at
`.index/`.

The contract is repository-generic. It is not specific to OpenSpec or Stage A.

## Purpose

- publish stable architectural reference material for humans and external AI
- capture subsystem responsibilities, boundaries, and interface hints
- support periodic regeneration without becoming workflow authority

## Run Modes

- `full_refresh`
  - default mode
  - refreshes the whole repository index surface
- `scoped_refresh`
  - optional mode
  - refreshes only declared directories or modules

## Required Outputs

Every run MUST emit:

- one run JSON
- one manifest JSON
- per-entry JSON files
- one human-readable summary Markdown

Canonical contracts:

- `.index/contracts/repository-index-run-v1.json`
- `.index/contracts/repository-index-manifest-v1.json`
- `.index/contracts/repository-index-entry-v1.json`

Validator entrypoint:

- `.index/bin/validate_repository_index.py`

## Quality Bar

- Prefer stable architectural facts over line-by-line narration.
- Keep all repository paths relative to the repo root.
- Make entries specific enough to guide review and orientation.
- Summaries should stay readable, but JSON is the primary interface.
- Scoped runs must stay inside their declared scope.

## Non-Goals

The index MUST NOT claim any of the following:

- verifier verdicts
- workflow closure authority
- repair routing
- Stage A termination authority
- that verification completion depends on `.index/`

## Reference Position

`.index/` is reference material only.

It may help external AI or human reviewers orient themselves, but it is not
part of the verifier bundle contract and is never required for verification to
start, continue, or finish.

## Suggested Validation

```bash
python3 .index/bin/validate_repository_index.py --run .index/examples/full-refresh/run.json
python3 .index/bin/validate_repository_index.py --run .index/examples/scoped-refresh/run.json
```
