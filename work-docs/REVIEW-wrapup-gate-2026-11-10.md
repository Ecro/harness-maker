---
type: review
task_slug: wrapup-gate
created: 2026-11-10
spec: "[[SPEC-wrapup-gate]]"
plan: "[[PLAN-wrapup-gate]]"
rounds: 2
reviewers: [code-reviewer]
summary: "Two code-reviewer rounds: 7 findings (2 major, 4 minor, 1 nit), then 3 (2 minor, 1 nit). Nine accepted and fixed; G1 rejected with an authority."
---

# REVIEW — wrapup-gate

Two code-reviewer rounds, with 7 and then 3 findings. Nine were accepted and fixed. G1 was
rejected with an authority, and nothing is unresolved. Before review, a spec-validator pass
raised 9 critiques (2 critical, 3 major, 4 minor); all were folded into the SPEC (see its
Refinement Decisions). The cross-model second opinion is not configured for this harness. No
`Do not change` path was crossed: `check_reuse.py`, `spec_machine.py` and `wrapup_land.py` are
untouched.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | major | tests/unit/test_overhaul_p1_hm_check.py:608 | The section-set pin did not include the new `contract` section. Fix: the pin adds it | accepted | SPEC AC-003 |
| F2 | major | src/harness_maker/check.py (`_dnc_entry`) | A bare entry was not normalised, so `- src/foo.py.`, bold names and a bare `src/api` matched nothing and the gate failed open. Fix: strip bold and trailing punctuation; a bare name with no glob character also covers `<name>/**`. Tests: AC-003 rows 13–15 | accepted | SPEC AC-003, HR-020 |
| F3 | minor | src/harness_maker/check.py (`_dnc_entry`) | `startswith("none")` dropped `- nonessential/`. Fix: `none\b`. Test: AC-003 row 15 | accepted | SPEC AC-003 |
| F4 | minor | src/harness_maker/check.py (`_USER_DECIDED`) | Existing PLANs write `**Decided by:** DRI`, and those allowances were ignored. Fix: `user` or `DRI`; SPEC constraint amended. Test: AC-003 row 16 | accepted | SPEC Constraints (allows) |
| F5 | minor | src/harness_maker/check.py (`_reprint`) | An identical reprint recomputed only `review`, so a gitignored PLAN edit left a stale `contract`. Fix: both sections are recomputed. Test: `test_ac_003_identical_reprint_recomputes_contract` (G3) | accepted | SPEC AC-002 |
| F6 | minor | tests/unit/test_wrapup_gate.py | `--require-review` was not tested through the CLI. Fix: `test_ac_002_cli_flag_reaches_the_gate` | accepted | SPEC IRR-001 |
| F7 | nit | src/harness_maker/check.py (`_verdict_key`) | The docstring had a stray line break. Fix: reflowed | accepted | style |
| G1 | minor | src/harness_maker/templates/stages/execute.md.j2 Step 4 | Step 4 no longer tells the reviewer to read `contract.advisory` | rejected | `agents/code-reviewer_body.md.j2:12` already reviews "drift from the PLAN's … `Do not change` list" against the diff, so a qualified bullet is the reviewer's by default. The stage-size budget (`_STAGE_BUDGET`, `_ATOMIC_RATCHET`) leaves no room for the sentence |
| G2 | nit | src/harness_maker/check.py (`_dnc_entry`) | `**src/a.py**.` became `src/a.py**`. Fix: strip punctuation, then bold, then punctuation again | accepted | SPEC AC-003 |
| G3 | minor | tests/unit/test_wrapup_gate.py | No test showed an identical reprint failing on a contract crossing. Fix: `test_ac_003_identical_reprint_recomputes_contract` | accepted | SPEC AC-002 |

Also found by the gate rather than the reviewer: `tests/unit/test_hm_cost_p2_check.py::test_ac_006_compact_output[full]` compared the full output with the pre-change output and so saw the new section. It now drops `contract` before that comparison; every other section must still be equal.
