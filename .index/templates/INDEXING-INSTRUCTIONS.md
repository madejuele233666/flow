# Repository Indexing Instructions

Use these instructions when an external AI is asked to refresh `.index/`.

## Goal

Produce repository-level reference material that captures stable
responsibilities, boundaries, interfaces, and review hints.

## Inspect

- repository structure
- subsystem boundaries
- contracts, CLIs, schemas, and public entrypoints
- important files that anchor the subsystem
- stable inputs and outputs
- external dependencies that materially affect reasoning or review

## Emit

For each run, write:

- one run JSON
- one manifest JSON
- per-entry JSON files
- one summary Markdown

Follow these contracts exactly:

- `.index/contracts/repository-index-run-v1.json`
- `.index/contracts/repository-index-manifest-v1.json`
- `.index/contracts/repository-index-entry-v1.json`

## Quality Rules

- Prefer stable architecture over code narration.
- Keep every repository path relative to the repo root.
- Do not invent authority the index does not have.
- Keep summaries short enough to scan.
- For scoped refreshes, keep every entry inside the declared scope.

## Avoid

Do not emit:

- verifier verdicts
- closure decisions
- repair routing
- claims that `.index/` is mandatory for verification completion
- line-by-line walkthroughs disguised as entries
