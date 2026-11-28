---
type: baseline-delta
task_slug: test-shape-rules
created: 2026-11-28
owns: [surface_baseline]
summary: "SPEC-behaviour-named-tests + SPEC-test-shape-rules shipped-surface growth: test-shape rules in /hm:spec and the existing-list paste in /hm:execute"
---

# Baseline delta — PLAN-test-shape-rules

The shipped surface **grew** by 147 chars per variant against the frozen baseline (ec2d6209c086).
The evidence judge, with each cause then checked by counterfactual, showed hm's tests losing on
maintainability to plain + tests because of their shape. That is text the model reads at the spec
and execute stages, so it cannot be paid for elsewhere without cutting a rule:

- spec: "A golden table maps one function's arguments to its return value; printed output, exit
  code, call sequence or lone case is a mechanical AC too" and "A rule about the change itself
  (files touched, no secret committed) is a Constraint for the review, not an AC". This is net of
  the trims ("(a check; writes nothing)", "; on exit 1 nothing is stamped", "it is parametric").
- execute: "a parametric AC whose call a test there already parametrizes with the same columns
  pastes rows `hm spec_machine export-golden --inline --slug <slug> --ac AC-NNN` prints into that
  list, else …", together with SPEC-behaviour-named-tests' bind step and `--ac/--name` write, net of
  the trim of "note drift … as a finding" (the reviewer checklist carries drift).

Measured with the committed generator (`tests/structural/_surface_baseline.py`, `build_baseline()`)
against the frozen baseline. wrapup/hm-wrapup −6 comes from the same PR.

| variant | command | delta (chars) | cause |
|---|---|---|---|
| claude | `execute` | +129 | bind before RED, named write, existing-list paste |
| claude | `spec` | +24 | call → return rule, Constraint rule, net of trims |
| codex | `hm-execute` | +129 | same text |
| codex | `hm-spec` | +24 | same text |

Result that pays for it: tier 1+2 ×3 vs plain + tests, maintainability 8-27 → 13-7, overall
13-18 → 25-8 (`/mnt/project-files/hm-blog-cost/CAUSES-maintainability-2026-11-28.md`).

Per ADR-010 the task that moved the surface owns its attribution; the re-freeze follows on main
after merge.
