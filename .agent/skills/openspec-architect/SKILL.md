---
name: openspec-architect
description: Architecture reasoning assistant for design decisions, tradeoff analysis, and stack-equivalent modeling. Use when the user is shaping design.md for a STANDARD or STRICT change.
license: MIT
compatibility: Works with any OpenSpec change. Best used after proposal/specs exist and before implementation begins.
metadata:
  author: project
  version: "2.0"
---

# OpenSpec Architect

Use this skill to improve architecture quality without taking over alignment or artifact verification.

This skill is responsible for:
- framing design choices
- comparing alternatives
- translating abstract intentions into stack-specific equivalents
- identifying named deliverables and verification hooks

This skill is NOT responsible for:
- full reference extraction across existing systems (`openspec-align`)
- final artifact auditing (`openspec-artifact-verify`)
- implementation repair routing (`openspec-repair-change`)

## When to use

- The user wants to improve or rewrite `design.md`
- A change is `STANDARD` or `STRICT`
- The design has real alternatives or tradeoffs
- The user needs help turning abstract intentions into concrete design anchors

## Input

Provide:
- the change name, or
- a design problem statement

If a change exists, read its proposal/specs/design first.

## Steps

### 1. Load change context

Read the available change artifacts:
- `proposal.md`
- `specs/**/*.md`
- `design.md` if it already exists

Extract:
- declared capabilities
- risk tier
- unresolved design tensions
- any explicit references to existing systems

### 2. Frame the design problem

Summarize the design problem in concrete terms:
- what must be decided
- what constraints exist
- what cannot be violated
- what remains ambiguous

If the design language is abstract, rewrite it into concrete problem statements before proceeding.

### 3. Generate stack equivalents

For every important concept in the design, name the concrete equivalent in the project or target stack.

Examples:
- boundary contract -> interface / schema / DTO / protocol / trait
- extension mechanism -> manifest / registry / hook contract / adapter contract
- workflow gate -> state table / phase rule / verification checkpoint

Do not stop at concept labels. Always produce a concrete equivalent.

### 4. Compare alternatives

For each significant decision, present at least two options when a real tradeoff exists:
- current vs target
- option A vs option B
- replicate vs adapt
- centralized vs distributed

For each option, explain:
- strengths
- weaknesses
- migration cost
- verification impact

### 5. Name deliverables and failure semantics

For each chosen decision, identify:
- concrete deliverables (files, schemas, skills, outputs, reports, rule sets)
- failure semantics (retry, veto, fallback, reject, route-back, or explicit non-support)
- at least one verification hook

If a critical decision lacks a named deliverable or failure mode, do not treat it as complete.

### 6. Produce design guidance

When updating or drafting `design.md`, ensure each important decision includes:
- the problem
- the chosen approach
- alternatives considered
- stack equivalent
- named deliverables
- failure semantics
- verification hook

### 7. Stop before audit

At the end:
- summarize open tradeoffs
- point to any missing alignment evidence
- recommend `openspec-align` if reference extraction is still needed
- recommend `openspec-artifact-verify` for final artifact review

## Guardrails

- NEVER treat abstract concepts as sufficient output
- NEVER present only one option when a real tradeoff exists
- NEVER claim a design is ready if critical decisions lack stack equivalents or verification hooks
- ALWAYS convert abstract intentions into named deliverables
