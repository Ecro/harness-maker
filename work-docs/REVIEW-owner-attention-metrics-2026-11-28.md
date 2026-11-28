---
type: review
task_slug: owner-attention-metrics
created: 2026-11-28
spec: "[[SPEC-owner-attention-metrics]]"
summary: One reviewer round over SPEC and diff, no P1; 5 P2 and 3 P3, 8 accepted and fixed (one adjusted).
---

# REVIEW — owner-attention-metrics

Round 1: one reviewer over the SPEC and the diff. RED: the 5 new tests failed on main 16731486
(`attention`, `doc_chars`, `escaped_regressions`, `owner_summary`, `run_judge` missing).

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | tests/unit/test_saga_bench.py AC-003 | no still-passing test and no `hidden_dir` (S4r) case, so "return everything that passed" passes | accepted | added test_d (passes before and after) and an S4r record grading S4's dir |
| F2 | P2 | tests/unit/test_saga_bench.py AC-005 | order swap and rep pairing not observed | accepted | fake logs schema prompts; test checks hm first then second, same rep, per-rep diffs |
| F3 | P2 | scripts/saga_bench.py owner_summary | old rows have no `doc_chars`, so hm's baseline silently omits SPEC reading | accepted | `docs_counted` flag; report prints "SPEC documents not counted: hm" |
| F4 | P2 | scripts/saga_bench.py run_judge | rerun appends duplicate pairs and pays again | accepted | pairs already ok in judge.jsonl are skipped |
| F5 | P2 | scripts/saga_bench.py run_judge | a moved run dir diffs as "deleted everything" | accepted | pair skipped with a stderr line |
| F6 | P3 | scripts/saga_bench.py run_sessions | S4r inherits S4's approved SPEC and counts it again | accepted | S4r's doc_chars is 0 when its slug is the resumed session's |
| F7 | P3 | scripts/saga_bench.py escaped_regressions | a failed final run (timeout) reads as regressions | accepted, adjusted | only runner-level failures (`<run>`, `<collection>`) are unknown; a module error from the agent's code still counts |
| F8 | P3 | scripts/saga_bench.py judge_summary | no n or failed count | accepted | `n` and `failed` per other arm |

Reviewer note kept for the write-up: the owner simulator stops after `max_replies` (3) per
session, so replies and approvals are capped there; read chars are not.
