---
type: baseline-delta
task_slug: ask-less
created: 2026-11-10
owns: [surface_baseline]
summary: "SPEC-ask-less' shipped-surface growth: rule R in every stage, spec's DRI-only interview rules, wrapup's split of intent writes"
---

# Baseline delta — PLAN-ask-less

The shipped surface **grew** by 800 chars (claude) and 797 chars (codex). The numbers are measured on top of
SPEC-wrapup-gate, which landed first and shrank execute by 4 chars and wrapup by 14.

- Rule R replaces the old choice rule in all four stages, +150 each. It names what the DRI decides
  and tells the agent to decide and report the rest.
- The spec stage asks only DRI-owned slots, picks the intent and shows the decisions list (+34
  net on claude, +31 on codex). The removed text is the per-AC oracle question and the
  closed-question allowance, and the brief and round-state wording was trimmed.
- Wrapup splits intent writes into unasked records and asked decisions, names
  `approval-status` as the source of the SPEC state, and keeps each call on its own line with
  its `-file` flags, which SPEC-intent-file-inputs pins (+334).

The intent-layer skill (−43) and its workflow-feedback reference (−46) shrank. They are skills,
not commands, so this table does not count them; AC-007 of the SPEC does.

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`measure_surface()`). "Before" is the baseline frozen at 636e9f49 (SPEC-pipeline-env-fixes' fold).

| variant | command | before (chars) | after | cause |
|---|---|---|---|---|
| claude | `spec` | 8 002 | 8 186 | rule R (+150), interview rules (+34) |
| claude | `execute` | 9 232 | 9 378 | rule R (+150), SPEC-wrapup-gate (−4) |
| claude | `research` | 4 892 | 5 042 | rule R |
| claude | `wrapup` | 6 373 | 6 693 | rule R (+150), intent-write split (+184), SPEC-wrapup-gate (−14) |
| codex | `hm-spec` | 8 096 | 8 277 | same text as the Claude command |
| codex | `hm-execute` | 9 235 | 9 381 | same |
| codex | `hm-research` | 4 949 | 5 099 | same |
| codex | `hm-wrapup` | 6 455 | 6 775 | same |

Per ADR-010 the task that moved the surface owns its attribution. Writing it next to the
allowance and the later re-freeze keeps this out of `ratchet-rebaselined-by-its-own-subject`.
The surface rose (+1.6% claude, +2.6% codex) because of rule R in every stage, the DRI-only
interview rules in spec, and wrapup's split of intent writes. No other prose changed.

## Folded into the baseline from main

PR #54 squash-merged the task as 756261b2. The PLAN was then marked complete, which expires its
allowance, so the growth was folded on main. The generator re-froze
`tests/structural/surface_baseline.json` at 756261b223d1: claude 50 059, codex 31 329.
SPEC-wrapup-gate (PR #53) landed in the same window and is netted in (execute −4, wrapup −14).
`render_sha` and `payload_digest` moved mechanically with the re-freeze. `_ATOMIC_RATCHET` is
re-measured for research (4 647 -> 4 810), spec (7 531 -> 7 728) and wrapup (4 961 -> 5 354),
which left its ±2% band; execute stays inside it. No bench measurement ran on the
task branch, so no `bench_hash` alias is needed.
