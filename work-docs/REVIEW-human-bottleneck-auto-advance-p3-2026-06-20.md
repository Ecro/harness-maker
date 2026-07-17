---
type: review
task_slug: human-bottleneck-auto-advance
status: APPROVED
created: 2026-06-20
phase: 3
reviewers_invoked: [code-reviewer, code-reviewer, codex]
consensus_method: k-of-3 (cross-check + Codex heterogeneous voter)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-20T00:00:00Z
---

# REVIEW — P3 Stop-hook backstop (human-bottleneck-auto-advance)

## 🎯 Round 1 Summary

**Grade: A** (P0_count = 0, P1_count = 0 consensus-passed).

P3 wires the autopilot Stop-hook backstop (ADR-005 of PLAN-human-bottleneck-auto-advance):
`autopilot_guard --mode stop-hook` returns `decision:block` + exit 2 while the
`.hm-autopilot` marker is active, preventing premature session termination mid-pipeline
until prompt-driven Skill chaining (P6) lands. The diff under review:

- `src/harness_maker/hooks/autopilot_guard.py` — `_stophook_reason`, `_pretooluse`,
  `main()` argparse `--mode` dispatch (default `pretooluse`).
- `src/harness_maker/templates/hooks/hooks.json.j2` — second `Stop` entry (alongside
  `loop_gate`), `timeout: 5`.
- `tests/unit/test_autopilot_guard.py` — P3 stop-hook tests.

All three reviewers (2 Claude code-reviewers + Codex) ran on the staged diff.
**Codex: no findings.** The two Claude reviewers surfaced only single-source items
(no surface+reasoning consensus) → no `consensus-passed` finding → **Grade A**.

## 🔍 Drift Findings

`drift_verdict: clean`. The diff touches exactly the files P3's PLAN scope names
(`autopilot_guard.py` stop-hook additions + `hooks.json.j2` Stop wiring + guard tests).
No scope drift, no incomplete-phase gap.

## ✅ Consensus Findings

None. (No finding reached surface + reasoning alignment across two reviewers.)

## 📝 Manual-Only Findings (single-source — recorded, not auto-applied)

Per the grade gate these do NOT lower the grade. Two were judged correct + low-cost
and **voluntarily applied** (consistent with the P1/P2/P4 review precedent in this
feature); one was **declined** with reasoning.

| # | Source | Severity | Finding | Disposition |
|---|--------|----------|---------|-------------|
| 1 | code-reviewer A | P1 | `main()` calls `sys.stdin.read()` unconditionally → a bare-TTY invocation blocks on EOF | **APPLIED** — `text = "" if sys.stdin.isatty() else sys.stdin.read()` (mirrors `loop_gate`'s isatty guard). |
| 2 | code-reviewer B | P2 | `_stophook_reason` returns `"…continue to the next stage"` — a false imperative before P6 lands the chainer; nothing can fulfil "continue" yet | **APPLIED** — softened to descriptive-only: `"[autopilot] pipeline in progress — not terminating. Run \`harness-maker autopilot off\` to end the autopilot session."` |
| 3 | code-reviewer A | P2 | argparse `--mode` should be `required=True` | **DECLINED** — the PreToolUse hooks.json entry passes NO `--mode` and relies on `default="pretooluse"`. `required=True` would break that entry at runtime. Documented via new test `test_main_default_mode_is_pretooluse`. |

### Test-gap closures (review hygiene — added this round)

The reviewers flagged thin coverage on the new dispatch surface. Added to
`tests/unit/test_autopilot_guard.py`:

- `test_main_stophook_active_guard_through_main` — the infinite-loop guard end-to-end
  through `main()`: `stop_hook_active` wins over an active marker → exit 0 (not 2).
- `test_main_stophook_corrupt_stdin_exits_0` — corrupt JSON and non-dict payload both
  fail open (exit 0), never crash-as-block.
- `test_main_default_mode_is_pretooluse` — documents the intentional default (the
  R1 P2 decline above).
- `test_main_stophook_mode_exit_codes` — now passes an explicit
  `workspace.current_dir` (both reviewers' P2) so root resolution matches the
  dedicated stop-hook tests rather than relying on cwd coincidence.

## 🤝 Disagreements

None — reviewers diverged on *which* single-source items to raise, but none collided
on the same file+line with differing severity.

## ⚙️ Verification

- `uv run pytest tests/unit/test_autopilot_guard.py` → all green (incl. 4 new tests).
- `uv run ruff check src/ tests/` → clean.
- `uv run ruff format --check` (changed files) → clean.
- `uv run mypy --strict src/harness_maker/hooks/autopilot_guard.py` → clean.
- **No snapshot impact**: the changes are src-only. The reason string is runtime
  hook output, not a rendered template; the `hooks.json.j2` Stop entry was already
  snapshot-regenerated in P3's execute finalize.

## ⚠️ Out-of-scope (NOT a P3 finding) — pre-existing suite red → ROOT-CAUSED + FIXED separately

`tests/integration/test_memory_retrieve_cli.py::test_cli_real_repo_memory_surfaces_recent_entry`
failed on the **base HEAD (7ac9c30)** too — NOT introduced by the P3 diff. Initially
hypothesized as a brittle top-K assertion against a grown corpus; **investigation
disproved that** — the test was correctly catching a real data-corruption bug:

- **Root cause:** `.claude/memory/wiki.md` was missing its `<!-- @hm:/user:entries -->`
  closing marker. `memory_retrieve.parse_entries` returns `[]` when the close marker is
  absent (`text.find` → -1), so **all 132 wiki entries were invisible to retrieval** —
  only `failures.md` entries surfaced. `boundary-parse-test-layer` (wiki.md:258) could
  never appear.
- **When/how it broke:** the close marker was present in `477fe40` (P2 wrapup) and lost
  in `7ac9c30` (P4 wrapup) — the P4 wiki memory-append wrote the
  `never-auto-guard-marker-gated-not-static-deny` entry *on top of* the close-marker
  line (overwrite). This is the `[fail:render] wrapup-eof-append-outside-marker`
  regression (now count:3 → triggers a pending-proposal at the next wrapup).
- **Fix (separate from P3, per option A):** restored the `<!-- @hm:/user:entries -->`
  closing marker at EOF after the last entry. No test was weakened — the test now
  passes for the right reason (132 wiki entries parse; target surfaced). This fix lands
  as its own change, NOT folded into the P3 commit.

## Status: APPROVED (Grade A) — P3 diff is clean. Wrapup blocked only by the
## documented pre-existing memory-retrieve red (separate concern, user decision).
