---
name: openspec-align
description: Reference-alignment assistant for extracting contracts from existing systems and building coverage mappings. Use when the user says to reference, align with, replicate, or adapt an existing system.
license: MIT
compatibility: Works with any OpenSpec change.
metadata:
  author: project
  version: "1.0"
---

# OpenSpec Align

Use this skill when a change must reference an existing system and the design needs implementation-grade alignment evidence.

## Input

Provide:
- the change name
- the system or files to align against
- whether the goal is `replicate`, `adapt`, or `hybrid`

## Steps

### 1. Lock reference scope

List the real source files or equivalent engineering evidence being aligned against.
Do not treat high-level concept docs as sufficient primary references.

### 2. Extract contracts

For each reference file, extract:
- important classes, interfaces, traits, schemas, or state tables
- key method or message signatures
- lifecycle or state rules
- important failure behaviors
- extension or boundary rules

### 3. Build a mapping table

Create a mapping table in this form:

| Reference Module | Target Module | Action | Notes |
|---|---|---|---|
| `<reference>` | `<target>` | Replicate / Adapt | `<reason>` |

### 4. Produce a coverage report

For each mapped contract, mark:
- ✅ fully covered
- ⚠️ partially covered
- ❌ missing

A missing critical contract must be surfaced explicitly before design finalization.

### 5. Surface adaptation boundaries

If a contract is intentionally not copied, state why:
- platform difference
- stack difference
- reduced scope
- explicit simplification
- incompatible lifecycle assumptions

### 6. Hand off cleanly

At the end, provide:
- reference inventory
- extracted contracts
- mapping table
- coverage report
- unresolved alignment risks

Recommend `openspec-architect` if design tradeoffs remain.
Recommend `openspec-artifact-verify` after the design is updated.

## Guardrails

- NEVER say a design is aligned without listing actual reference files
- NEVER hide missing contracts behind generic wording
- ALWAYS distinguish replicate from adapt
