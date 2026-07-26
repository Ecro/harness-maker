---
type: review
task_slug: allow-literal-prune
status: APPROVED
created: 2026-07-26
reviewers_invoked: [code-reviewer, security-reviewer, code-verifier, codex, antigravity]
consensus_method: cross-check
rounds: 3
human_review_needed: true
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: allow-literal-prune
  computed_at: 2026-07-26T00:00:00Z
  note: >-
    No work-docs/PLAN-allow-literal-prune.md exists — this change was requested
    directly, not planned through /hm:plan, so there is no declared scope to diff
    against. `clean` here means "no drift detectable", NOT "scope verified". A
    reader must not treat this verdict as evidence the change stayed in scope.
second_opinion_results:
  - model: codex
    status: invoked
    reconciliation: [regex-overbreadth-CONFIRMED, residual-grants-CONFIRMED]
  - model: antigravity
    status: invoked
    reconciliation:
      [regex-overbreadth-CONFIRMED, invariant3-tautology-CONFIRMED, crash-claim-REFUTED]
---

# REVIEW — allow-literal prune

## 🎯 Summary

| Round | Voters | Grade | Outcome |
|---|---|---|---|
| 1 | security-reviewer, code-reviewer, general-purpose, codex, antigravity | **F** | P0: the change ADDED an arbitrary-execution grant |
| 2 | security-reviewer, code-reviewer, codex, antigravity | **F** | P0: the boundary fix reached new installs only |
| 3 | code-reviewer, security-reviewer, codex, antigravity | **A** | 0 consensus-passed P0/P1 remaining |

Worktree preflight was **skipped**: the change is uncommitted in the base repo, not in
a task worktree, so `task-preflight` would have reviewed a tree without the changes.

## 🔍 Drift findings

None computable — no PLAN exists for this task. Recorded in frontmatter rather than
silently emitting `clean`.

## ✅ Consensus findings (resolved this round)

| # | Sev | Voters | Finding | Resolution |
|---|-----|--------|---------|------------|
| 1 | P1 | 4 (code-rev, sec-rev, codex, agy) | Prune regex used a free `.+` in the `--with` slot, deleting user-authored rules (`--with requests`, `--with .`, `--with /path/to/my/fork`) | Tightened to `[^ ]*harness[-_]maker[^ ]*` — only refs `_compute_install_ref` can emit. Reproduced before/after. |
| 2 | P2 | 2 (sec-rev, agy) | Invariant 3 ("never less than a fresh install") is guaranteed by union order; its test could not fail | Comment now says STRUCTURAL, not test-enforced. Test rewritten to go through a real re-render. |
| 3 | P2 | 2 (code-rev, sec-rev) | `test_dry_run_*` docstring asserted a reachability claim the same change refutes; and pinned `"will now ask before running"`, a string that exists nowhere → assertion could never fail | Docstring corrected to `cli.py`'s traced behaviour; assertion re-anchored on `"dropped"`, which the applied branch proves is emitted. |
| 4 | P1 | 2 (codex, sec-rev) | Docs claimed the arbitrary-execution hole is *closed* while `pytest`/`git`/`codex exec`/bare `Read` grants remain | CHANGELOG residual block rewritten; "closed" removed. |
| 5 | P2 | 1 + verified | `literal.index("python -m")` raises `ValueError` on a future placeholder rule | Guarded. |
| 6 | P2 | 1 + verified | `_PRE_PRUNE_TAG` dead constant with a misleading rationale | Deleted. |
| 7 | P2 | 1 + verified | `scan()` advice recommended `uv run ruff check` — still syncs the project and runs its build backend | Changed to a runner-free example. |
| 8 | P2 | 1 + verified | Uncached git fan-out + ~35 renders | `_every_allow_literal_ever_shipped` memoized. |

Each fix was mutation-tested: reverting it turns the naming test red.

## ⚠️ Refuted — recorded so the silence is not read as agreement

- **antigravity, P1** — "the malformed-entry fix is incomplete; the union loop raises
  `TypeError` on an unhashable dict". **False.** The loop is
  `if isinstance(item, str) and item not in seen`, which short-circuits before the set
  membership. Executed: returns `{'allow': ['Read', 'Bash(mine:*)']}`, no exception.
- **antigravity, P3** — "the diff says the rule was removed but it was tightened".
  Conflated two rules: the `"$HM"` rule was removed; the `src_path` rule was tightened.
  Prompt ambiguity on my side, not a defect.

## 📝 Manual-only / not fixed here — P1 present, hence `human_review_needed: true`

These are **pre-existing** grants, not introduced by this change. They are documented
rather than fixed because each is a separate behavioural decision:

- `Bash(uv run pytest:*)` / `Bash(pytest:*)` execute working-tree `conftest.py`.
- `Bash(git:*)` covers shell-backed git aliases.
- `Bash(codex exec:*)` takes caller-chosen arguments.
- Bare `Read` pre-approves reading any path; `secscan._CATCH_ALL` flags `Read(*)` but
  not the strictly broader no-arg form.
- A pruned grant can be restored via the prompt's "don't ask again" into
  `.claude/settings.local.json`, which is neither pruned nor scanned.
- `--dry-run` does not preview which rules will be deleted.

## 🤝 Disagreements

Rounds 1–2 split on whether `--dry-run` reaches the permission merge. Resolved by
tracing `cli.py`: it raises `typer.Exit(0)` before the only `render()` call site, so
**no shipped command reaches it**. My earlier "verification" ran `render(dry_run=True)`
directly, which answers a different question than the one in dispute.

## Verification

`pytest rc=0`, 0 FAILED · `ruff check` · `ruff format --check` · `mypy --strict` — all
clean. Snapshots regenerated in the base repo (not in a worktree —
`[fail:test] snapshot-regen-inside-worktree`, count:11) and re-verified as
`settings.json`-only.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | F     | 6             | 0         | —   |
| 2         | F     | 7             | 0         | 1   |
| 3         | A     | 8             | 6 (manual, pre-existing) | 0 |

Final grade: **A**
Iterations used: 3 / 3
Status: APPROVED
human_review_needed: **true** — manual-only P1 residual grants above are real and
unverified by consensus; they predate this change but a human should decide whether
any of them warrants its own task.
