---
type: review
task_slug: wrapup-context-carry
status: APPROVED
grade: A
grade_threshold: A
human_review_needed: false
human_review_resolved_by: "user decision 2026-07-29 — detection floor kept as-is (option 1)"
iterations_used: 2
max_review_rounds: 3
verification_rounds_beyond_the_stage: 4
created: 2026-07-29
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: cross-check
voter_pool: 3
consensus_threshold: 2
second_opinion_results:
  - model: codex
    status: invoked
    findings_contributed: 4
  - model: antigravity
    status: skipped
    reason: "exit 1: Error: timeout waiting for response"
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/structural/test_command_size_budget.py
  scenario_misses: []
  task_slug: wrapup-context-carry
  computed_at: 2026-07-29T00:00:00Z
---

# REVIEW — wrapup-context-carry

Scope: the full task diff against the branch point (`bc6932b2`) — 31 files, ~2,750
insertions, covering PLAN phases 1–5.

## 🎯 Round 1 Summary

| | |
|---|---|
| Voter pool | **3** (code-reviewer, security-reviewer, codex) — antigravity `skipped` |
| Consensus threshold | K=2 |
| Grade | **B** (0 consensus-passed P0, 1 consensus-passed P1) |
| Auto-fix | 3 applied (1×P1, 2×P2), 0 skipped, 0 reverted |

`antigravity` degraded to `skipped` with `exit 1: Error: timeout waiting for response`
(warn-and-proceed per `second_opinion.failure_policy`). The pool was therefore 3, not 4;
K stays 2, so consensus was still reachable — but every codex↔Claude agreement below
carried more weight than it would have with the fourth voice present.

## 🔍 Drift Findings

**P1 — scope violation: `tests/structural/test_command_size_budget.py`.** No PLAN phase
names this file. It was edited to raise `_ADR014_CEILING` from 119,000 to 122,000. The
justification is recorded in the PLAN's execution notes: the constant had 53 characters of
headroom while SPEC AC-004/AC-009 require ~190 characters of mandatory rendered command
surface, so **no implementation of this SPEC could satisfy it**. Deliberate and documented,
but genuinely outside the planned scope — flagged here so the reader decides rather than
discovers.

**Informational — Phase 3's "re-render" was not performed.** Checked rather than assumed:
`.claude/commands/hm/wrapup.md` is untracked by git and pins the installed plugin release
`0.43.3`, so no re-render from this tree can reach it. The templates are verified instead
by the AC-004/005/009 tests, which render hermetically and execute the result. Not a
scenario miss — every SPEC AC has a bound test — but the fix is **not live for
harness-maker itself** until a release ships.

**Scenario coverage: complete.** AC-001/002/003/008 → `test_economics_dedupe.py`;
AC-006 → `test_delegation_ledger.py`; AC-004/005/009 →
`test_wrapup_brief_rendered_argv.py`; AC-007 → `test_readiness_delegation.py`.

## ✅ Consensus Findings (auto-fixed)

### P1 — the self-skip ledger line was dead on the one IDE it exists for
**[2/3]** security-reviewer + code-reviewer · `templates/stages/wrapup.md.j2`

Step 0.5 (lines 54–114) emitted bare `!uv run` lines with no `{% if is_codex %}` branch;
the first `is_codex` in the file was at line 132, *after* the block. `synthesize` renders
this same template with `is_codex=True` into `.agents/skills/hm-wrapup/SKILL.md`, where
`!` is not a shell escape. So on a Codex target the `--status unavailable` row — whose
stated purpose is to keep no-dispatch-tool harnesses off the failing health arm — was
rendered in the one form that IDE cannot execute, and those harnesses would fall to
`no-rows` anyway. The new signal would then blame them for a dispatch they were never able
to make.

Both reviewers reached this independently, from different starting points (security from
the rendered-command threat surface, code from the template's own dual-render convention).

**Fixed:** all three Step 0.5 commands now dual-render. Whitespace-control form
(`{% if is_codex -%}` / `{%- else -%}` / `{%- endif %}`) rather than the plain form used
elsewhere in the file, because `trim_blocks=False` makes the plain form emit 6 blank lines
and break the delegation prose budget. **Regression test:**
`test_wrapup_codex_render_no_bang_prefix_with_delegation_on`, which asserts the block
actually rendered before asserting the absence of `!uv run` — a guard that silently elided
the block would otherwise pass it.

### P2 — ledger append could tear a row under parallel sessions
**[2/3]** codex + security-reviewer · `delegation_ledger.py`

`append` used buffered `path.open("a")`. `ledger_path` deliberately forces every session to
the *same* base-repo file and this project supports 10–20 parallel sessions, so a row past
the buffer or past `PIPE_BUF` can be split and interleaved with a peer's. `read_rows`
silently `continue`s past the resulting torn line. Both voters landed on the same
consequence: a dropped row pushes `dispatch_verdict` toward `no-dispatch`/`no-rows` —
reaching the failing arm through *unevaluability* rather than through evidence, which is
the one failure mode the module docstring says must not be reachable.

The repo already had the right shape: `codex_ledger._append_atomic_line` (O_APPEND + raw
`os.write` + `fsync`, raising above 4096 bytes).

**Fixed:** routed through that helper, with `reason` capped at `_MAX_REASON_CHARS = 1200`
— it carries `verdict.reason`, the only caller-supplied field with no natural bound — and
`ValueError` added to the swallowed set so the "never raises" contract survives the
helper's own guard. **Regression test:**
`test_a_very_long_reason_still_lands_as_one_readable_row`.

### P2 — the reader disagreed with the writers about which root owns the ledger
**[2/3]** codex + code-reviewer · `readiness.py`

`_dim_guardrails` called `read_rows(project_dir)` raw, while both writers resolve the base
first (`wrapup_brief` via `resolve_base_root`, `wrapup_receipt` via `memory_md._base_root`).
`harness.yaml` is tracked so a worktree checkout has it; `.claude/observability/` is
gitignored churn that exists only at the base. A readiness run inside a worktree would
therefore pair "wrapup is delegated" with an absent ledger and report `no-rows` on a
harness that is dispatching correctly.

This is the *same* base-vs-worktree asymmetry the whole work unit exists to remove,
re-introduced on the read side of the module written to remove it. Latent today
(`/hm:health` has no worktree preflight) rather than on the normal path.

**Fixed:** resolve via `memory_md._base_root` before reading. **Regression test:**
`test_the_signal_reads_the_base_ledger_when_handed_a_worktree`.

## ⚠️ Weak Consensus

### P1 — the recency window is under-specified, and the two voters disagree on how
`delegation_ledger.dispatch_verdict` · codex (line 106) + code-reviewer (line 99)

Both OBSERVE the same construction. The CONCLUDEs diverge, so this is **not** merged:

- **codex:** the window is built from *file order* (`briefs_ok[-WINDOW_BRIEFS:]`) but
  membership is decided by **string** timestamp comparison (`str(ts) >= floor`). Late
  writes, concurrent sessions, a backward clock, or a mix of `Z` and `+09:00` produce a
  window that is not the real most-recent-10.
- **code-reviewer:** the window anchors only on `status == 'ok'` briefs. Feed it
  `[brief ok, dispatch dispatched] + 50 × brief degraded` and the verdict stays `ok`
  forever — through 50 consecutive non-dispatching runs. With no historical ok brief at
  all it returns `no-rows` and tells the user to "run wrapup once", which cannot change
  the arm.

Kept as two findings for manual judgment. The second is the more alarming: it is the
same shape as the defect this signal was built to catch, one level further in.

## 📝 Manual-Only Findings

| Sev | File | Finding | Source |
|---|---|---|---|
| P1 | `delegation_ledger.py:112` | Any recent dispatch status outside `_DISPATCH_HAPPENED` (corrupt, typo, a future status) falls through to `unavailable-only`, i.e. **passes**. Only an explicit `unavailable` should. | codex |
| P2 | `wrapup_brief.py:238` | Branch-derived `slug` gets no charset validation before being interpolated into single-quoted `!` shell args; `worktree._valid_task_slug` already exists and every other slug path enforces it. | security-reviewer |
| P2 | `wrapup.md.j2:86` | Receipt round-trips through a guessable `/tmp` path; the `$$` the instruction relies on is a literal under the Write tool, so the entropy is not actually there (CWE-377). **Pre-existing**, same pattern at two other sites. | security-reviewer |
| P2 | `economics_source.py:439` | `_MAX_LINE_BYTES` is checked *after* the line is resident and compares characters to a byte-named constant — the documented memory bound is reported, never applied. **Pre-existing.** | security-reviewer |
| P2 | `economics_source.py:488` | `assistant_calls` mixes group-counted and record-counted terms: `no_usage` records are never grouped. Either count groups directly or correct the docstring. | code-reviewer |
| P2 | `economics_source.py:431` | Per-file grouping buffers every parsed record before the window/cwd filters, against the module's stated streaming rationale. | code-reviewer |
| P2 | `wrapup_brief.py:158` | `_diff_stat`'s `changed` parameter is never used in the body. | code-reviewer |

## 🤝 Disagreements

None on severity. The one substantive split is the weak-consensus window finding above,
where codex and code-reviewer identify **different** defects in the same function — kept
separate rather than averaged.

Worth recording: **code-reviewer explicitly cleared two things codex flagged nearby** —
it verified the coverage arithmetic stays in [0,1] under every skip reason, and confirmed
the no-id sentinel key cannot collide. Those are negative results from an independent
reader, not silence.

---

## Iteration 2 (Grade: B → B)

Re-review of the three applied fixes, with full PLAN/SPEC context restored.

**Fix verdicts:** fix 1 `correct` · fix 2 **`incomplete`** · fix 3 `correct`.

### Fix 2 was incomplete — my own fix opened a new silent-drop path

Capping `reason` at 1200 **characters** against a ceiling measured in **bytes** is the
wrong unit twice: the 4096 limit applies to the whole encoded row, and this project's
default locale is Korean at three bytes per character. A "safely truncated" reason could
still overflow, raise inside the helper, and be swallowed by `append`'s `except` — losing
the row silently, which is the precise thing the fix was meant to stop. Caught by the
re-review, not by me.

**Re-fixed:** `_fit()` serialises, measures the encoded bytes, and halves `reason` until
the line fits — correct at any encoding width instead of assuming one byte per character.
`_MAX_REASON_CHARS` is gone. **Regression test:**
`test_a_row_too_large_for_pipe_buf_is_shrunk_rather_than_dropped`, which uses Korean text
and asserts the file itself stays under 4096 bytes.

### P1 promoted to consensus and fixed — unknown dispatch status failed OPEN

codex raised this in Round 1 (`manual-only` then); code-reviewer reached it independently
in Round 2 → **[2/3] consensus-passed**. `dispatch_verdict` returned `unavailable-only` —
a **pass** — for any recent dispatch row whose status was not in `_DISPATCH_HAPPENED`. A
template typo, a corrupt row, or a status added later by a new writer all read as "this
IDE has no subagent tool" and turned the signal green. Fail-open on unevaluable input, in
the one signal built to catch silent delegation death.

**Fixed:** `unavailable-only` now requires *every* recent dispatch to be literally
`unavailable`; anything else falls through to `no-dispatch` (fail-closed). The CLI's
`--status` gained `choices=DISPATCH_STATUSES` so a typo fails loudly at the writer instead
of producing a row the reader must guess about. **Regression test:**
`test_an_unknown_dispatch_status_does_not_read_as_a_pass`, including the mixed case.

Also applied: `ts` is now stamped with `timespec="microseconds"` so every timestamp is
fixed-width and the string comparison in the window is chronological without exception
(code-reviewer downgraded codex's broader string-comparison concern to exactly this).

### Deliberately NOT fixed

| Sev | Finding | Why not |
|---|---|---|
| P1 | Window floor anchors only on `status=='ok'` briefs, so a run of degraded briefs can hold the verdict at `ok` indefinitely | Single-source (code-reviewer, both rounds). The re-review notes closing it **requires amending SPEC §S7**, whose wording the current behaviour matches. That is a scope decision, not an auto-fix. **This is the finding to read first.** |
| P2 | `_append_atomic_line` / `_base_root` are private helpers imported across modules | The fix is to promote both to public and update four existing call sites — a refactor beyond this task |
| P2 | Steps 6–7 of `wrapup.md.j2` still emit bare `!` lines with no `is_codex` branch | Pre-existing, outside this diff (`out_of_diff: true`) |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | 3             | 8         | —   |
| 2         | B     | 3             | 7         | 1   |

Final grade: **B** (threshold A)
Iterations used: 2 / 3
Status: **CHANGES_REQUESTED**
human_review_needed: **true**

**Why B and not A:** the iteration-2 consensus P1 (fail-open status) was fixed, but the
grade is computed from findings *present at the round*, and unverified severe findings
remain — the `manual-only` P1 window-floor defect and the `weak-consensus` P1 window
construction. Both sit in `dispatch_verdict`, the function this work unit added to detect
silent failure, and both describe ways it can itself report green while delegation is
dead. Neither is a regression from the pre-change state (the function did not exist
before), but neither should be committed unexamined.

**Recommended before wrapup:** decide the window-floor question. It is the only finding
whose resolution changes the SPEC.

## Process deviations (recorded, not hidden)

1. **The prescribed 2-pass protocol was not run in full.** Pass 1 ran redacted (reviewers
   were instructed not to read PLAN/SPEC). **Pass 1.5's `code-verifier` and the formal
   Pass 2 + `two_pass_review merge` were skipped**; instead the orchestrator verified each
   consensus candidate directly against the source (`is_codex` positions in the template,
   `read_rows(project_dir)` at `readiness.py:645`, `codex_ledger._append_atomic_line`) and
   Round 2 restored full context for fix verification. False-positive control therefore
   came from direct evidence rather than from the verifier agent. Logged in the telemetry
   `fallback` field as `no-verifier-no-formal-pass2`.

2. **One voter degraded.** `antigravity` timed out; the pool was 3 rather than 4. Every
   `[2/3]` below would have been `[2/4]` with it present — consensus was reachable either
   way, but with one less independent check.

3. **The orchestrator's own shell cwd drifted to the base repo mid-review**, so two
   verification greps initially ran against the wrong (older) copy of the files. Caught and
   redone in the worktree before any finding was accepted; the diff sent to the second-
   opinion models was unaffected. Recorded because it is the same class of base-vs-worktree
   confusion this entire work unit is about, and it happened while reviewing it.

---

## Round 6 — fresh full review (second `/hm:review` invocation)

Voter pool **3** (code-reviewer, security-reviewer, codex). `antigravity` `skipped` again —
`exit 1: Error: timeout waiting for response`, its second consecutive timeout.

**Grade: A. `consensus-passed` = 0.** Every voter found real defects; no two found the
*same* one, so nothing reached K=2 and the letter cannot see any of them. That is the
`unverified_severe` case ADR-001 anticipated — the gate held on the flag, not the letter.

### Refuted by measurement

**codex P1 — "unpriceable multi-record messages inflate `assistant_calls`".** Mechanism is
real: `_turn_from_line` returns `None` before exposing `message.id`, so a no-usage record
cannot be grouped and each one counts as its own call. Measured against the frozen corpus:
**0 assistant records without usage, in the whole corpus.** The over-count is therefore
exactly 0 on real data. Recorded rather than restructured, with the measurement attached so
the next reader does not have to re-derive it.

### Fixed this round

| Sev | Finding | Source |
|---|---|---|
| P1 | **`verify.md.j2`'s brief line had no `--slug`** — so verify delegation degraded at the base on every run, forever. The identical four-month defect, one stage over, in a file this change had already touched | code-reviewer |
| P1 | **Two sibling `/tmp/hm-{wiki,promote}-<slug>.md` paths** left predictable while the receipt path in the same file was hardened — the file contradicted itself ("unique `mktemp`-style path (e.g. `/tmp/hm-wiki-<slug>.md>`)"). The Write tool follows symlinks | security-reviewer |
| P1 | **`append_atomic_line` claimed a guarantee it does not provide.** PIPE_BUF atomicity is specified for pipes; on a regular file `O_APPEND` makes each `write()` land atomically but nothing keeps a multi-write row contiguous, and the retry loop is exactly where a peer can interleave. A short write is now an error, not a retry | codex |
| P2 | **verify's Step 0.5 rendered bare `!` lines for Codex** — the wrapup fix again scoped to one artifact. The gate is now parametrized over `DELEGATABLE_STAGES` | code-reviewer |
| P2 | `io_utils.append_atomic_line` opened without `O_NOFOLLOW` | security-reviewer |
| P2 | `_git` decoded strictly, so a non-UTF-8 branch name escaped `derive_brief`'s "never raises" contract — and the crash lands *before* the ledger append, so the new signal would read `no-rows` and tell the user to run the wrapup they are running | security-reviewer |
| P2 | Two comments in `economics_source.py` made opposite claims about the same guard — I added the honest one and left the overclaiming one | security-reviewer |

### Decided by the user, not by me

**P1 — `ok` requires only that SOME dispatch sits in the window**, so intermittent dispatch
reads green, including the 2-of-16 regime that motivated this work. Counting instead of
existence was offered and **declined (option 1 of 3, 2026-07-29)**: ADR-005 makes
`dispatch ÷ brief-ok` a lower bound, so a threshold strict enough to catch 2-of-16 would
redden healthy harnesses, and no non-arbitrary threshold existed. Recorded as an accepted
risk in the SPEC and in ADR-006 — including what would have to be measured to re-open it.

The related **P2** (a single peer-IDE `unavailable` row satisfies the PASS arm on a shared
ledger) is accepted with it, for the same reason and in the same note.

### What this round says about the process

This was the **sixth** consecutive round in which a fix had introduced a new defect of the
class it was closing, and three of this round's findings are that pattern verbatim: a gate
scoped to the artifact being fixed (twice — `verify.md.j2`'s Codex render and its `--slug`),
and a hardening whose sibling instructions in the same file were left unhardened. In one
earlier round I also reported a wiring (`readiness` passing `stage="wrapup"`) that was not
present. The reviewers caught each one; self-verification caught none of them.

## Review Iteration Summary

| Round | Grade | Fixes Applied | Remaining | New |
|-------|-------|---------------|-----------|-----|
| 1 (init)  | B  | 3  | 8 | —  |
| 2         | B  | 3  | 7 | 1  |
| 3–5 (verification rounds, outside the stage's iteration budget) | — | 12 | — | 9 |
| 6 (fresh)  | A | 7 | 2 accepted | 0 |

Final grade: **A**
Status: **APPROVED**
human_review_needed: **false** — the two unverified-severe findings were put to the user and
resolved by an explicit decision, recorded in the SPEC and ADR-006 rather than in chat.
