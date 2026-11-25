---
type: review
task_slug: saga-bench
created: 2026-11-25
spec: "[[SPEC-saga-bench]]"
summary: One code-reviewer round, 4 P1 and 7 P2 accepted and fixed, 1 P3 kept by design; codex second opinion not configured.
---

# REVIEW — saga-bench

Round 1: `code-reviewer` over SPEC, PLAN, diff and tests. RED: all 8 AC tests failed before the
runner existed (module missing). A live smoke run (S1 only, 3 arms, $1.39) passed end to end:
hm walked spec → owner answer → C1 correction → stamp → execute → wrapup and landed one commit.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P1 | scripts/saga_bench.py new_slug | In S3a ∥ S3b an hm session could take the other's newest SPEC slug | accepted, fixed | slug = the new SPEC its own transcript names most |
| F2 | P1 | scripts/saga_bench.py e1_seen | Any tool result naming test_format_due + "fail" counted, so reading a NOTES/memory lesson scored as recurrence | accepted, fixed | pytest failure marks only (`FAILED …::`, `:: … FAILED`, failure header) |
| F3 | P1 | scripts/saga_bench.py score_traps | `resume` scored when S4 was never cut off; F811 compared cumulatively | accepted, fixed | None unless S4 interrupted; no new F811 since before S4 |
| F4 | P1 | scripts/saga_bench.py _agent_turn | A killed first call has no session id, so no E1 search and no cost | accepted, fixed | `--session-id <uuid4>` on each first call; killed sessions priced from transcripts |
| F5 | P2 | scripts/saga_bench.py Interrupter | Delay could elapse between turns; stale worktree counted as a change | accepted, fixed | clock runs only inside a turn; per-root baselines |
| F6 | P2 | scripts/saga_bench.py run_session | execute sent on unapproved SPECs | accepted, fixed | execute only on a stamped SPEC, wrapup only after execute; negative test added |
| F7 | P2 | scripts/saga_bench.py landed | slug substring in commit bodies | accepted, fixed | `git cat-file -e HEAD:specs/SPEC-<slug>.md` |
| F8 | P2 | scripts/saga_bench.py handoff | quiz uses all agent messages, SPEC said last | rejected (SPEC updated) | smoke: plain's last message after the post-hoc fix held only the fix; all arms get all their messages |
| F9 | P2 | hidden/S1, hidden/S5 | argparse SystemExit(2) and TZID DTSTART were wrongly failed | accepted, fixed | both accepted |
| F10 | P2 | hidden/S2, score_traps | H1 miss counted twice via H1_kept and IRR | accepted, fixed | IRR/plain import use fixed JSON; H1_kept None unless H1 met |
| F11 | P2 | duplicate_definitions | ruff failure read as 0 | accepted, fixed | -1 unless rc in {0, 1} |
| F12 | P3 | no_dependency, validator_summary | dependency from S4 attributed to S5; error rows counted as misses | partly: summary now counts ok rows only; no_dependency stays "goal held at saga end" by design | — |

Second opinion: not configured (`second_opinion.models` empty), skipped.
