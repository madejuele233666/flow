# Reusable Verification Flow

The active reusable flow is `verification-cycle`, not the archived
legacy dual-session loop.

## Read First

1. `openspec/schemas/modules/verification-cycle/README.md`
2. `openspec/schemas/modules/verification-cycle/VERIFY-IMPLEMENTATION.md`
3. `openspec/schemas/modules/verification-cycle/REFERENCE-INDEX.md`
4. `openspec/schemas/ai-enforced-workflow/verification-sequence.md`

## Minimal Runtime Rules

- resume usable `active` first
- spawn only when no usable `active` exists
- repair against the same blocking agent
- only `block -> pass` creates `non_active`
- partial review must declare `scope`
- terminate only on a valid `active` pass

## Historical Note

The old review-loop is archive-only:

- `openspec/schemas/modules/archive/review-loop-2026-04-18`
