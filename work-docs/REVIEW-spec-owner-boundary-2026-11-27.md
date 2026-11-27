---
type: review
task_slug: spec-owner-boundary
created: 2026-11-27
spec: "[[SPEC-spec-owner-boundary]]"
summary: One reviewer round, no P1; seven findings accepted (skip-rule typo carve-out, Boundary placed before the brief and counted in the 3, docs, CHANGELOG, SubprocessError), SIGQUIT recorded out of scope.
---

# REVIEW — spec-owner-boundary

Round 1: one reviewer over the SPEC and commit 199e7574; new tests and AC-007 green.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | spec.md.j2:17 | "CLI-output or user-facing message change" blocks a true one-liner (typo in an error string or a rendered template) | accepted | "(a typo fix is not one)" added; SPEC Refinement Decisions |
| F2 | P3 | spec.md.j2:17 | Step 0 runs before the Step 2 code read, so "no open Boundary" could be judged unread | accepted | condition 5 now "(read the code as Step 2 says)" |
| F3 | P3 | spec.md.j2:32 | the Boundary question could be asked as a 4th question | accepted | "(one of its 3 questions)" |
| F4 | P3 | spec.md.j2:28-32 | the Design brief rendered before the Boundary could call scope settled first | accepted | Boundary moved above the brief; AC-002 checks the order |
| F5 | P3 | HOW-IT-WORKS(.ko) | "docs count" without "tests do not" | accepted | both docs |
| F6 | P3 | CHANGELOG | cause omitted the 4/10 approval-only sessions | accepted | added |
| F7 | P3 | check.py:220 | a `preexec_fn` failure raises SubprocessError, not OSError; SIGQUIT also ignored for async jobs | accepted (catch) / rejected (SIGQUIT) | nothing here depends on SIGQUIT; recorded in SPEC |
| F8 | P3 | SPEC Verification S3 | the two real tests via `check._run` are not automated | accepted | marked manual |

Growth after fixes: +475 chars per spec render; budgets set to the measured value.

## Revision 2 review (2026-11-27)

Scope: Boundary "unless the code settles it" → asked unless the ask states it (live re-measure:
asked 0/3). One reviewer round.

| # | Sev | Finding | Disposition |
|---|---|---|---|
| R1 | P1 | Step 0 "the ask states its Boundary" almost never holds, so trivial asks lose the skip | Fixed: "no **Boundary** left open (Step 2)" |
| R2 | P1 | "unless the ask states it" forces an empty question on greenfield changes | Fixed: open unless the ask states it "or the change keeps no existing behaviour" |
| R3 | P2 | three ambiguous "it" | Fixed: "Ask an open boundary in round 1 …; a Refinement Decision alone is not enough." |
| R4 | P2 | BASELINE-DELTA quoted the old Step 0 text | Fixed |
| R5 | P3 | Boundary not tied to categories 1–4 | Not taken: adds chars; Boundary is already "one of its 3 questions" |
| R6 | P3 | HOW-IT-WORKS grammar | Fixed |
