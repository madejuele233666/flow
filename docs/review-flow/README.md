# Verification Cycle

This directory now documents the active `verification-cycle` model used by
Stage A verification.

The old `review-loop` model has been archived at:

- `openspec/schemas/modules/archive/review-loop-2026-04-18`

## Active Entry Points

- [verification-cycle module](/home/madejuele/projects/2K0300/openspec/schemas/modules/verification-cycle/README.md)
- [verify implementation](/home/madejuele/projects/2K0300/openspec/schemas/modules/verification-cycle/VERIFY-IMPLEMENTATION.md)
- [reference index](/home/madejuele/projects/2K0300/openspec/schemas/modules/verification-cycle/REFERENCE-INDEX.md)
- [shared verify sequence](/home/madejuele/projects/2K0300/openspec/schemas/ai-enforced-workflow/verification-sequence.md)

## Active Runtime Shape

The cycle is:

```text
resume active
  -> or spawn active
  -> block => repair same agent
  -> pass => mark non_active
  -> continue
  -> terminate on valid active pass
```

Useful reminders:

- `pass` is valid only with `coverage_status=complete` and
  `exhaustive=true`
- partial verification requires explicit `scope`
- `close` or `exit` does not imply `non_active`
- `.index/` is optional external reference material only
