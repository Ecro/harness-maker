---
type: review
task_slug: human-bottleneck-auto-advance
status: APPROVED
created: 2026-06-20
reviewers_invoked: [code-reviewer (×2), security-reviewer (×2), codex]
consensus_method: k-of-n (3 Claude + Codex round 1; security re-review round 2)
codex_status: invoked
phase: 4
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-20T00:00:00Z
final_grade: A
status_final: APPROVED
human_review_needed: false
---

# REVIEW — human-bottleneck-auto-advance Phase 4 (never-auto guard)

## 🎯 Round 1 Summary

- **Scope:** `autopilot_guard.py` (PreToolUse never-auto enforcement hook), `hooks.json.j2` wiring, tests, 8 regenerated snapshots. Security-sensitive (permission enforcement) → reviewer panel = 2 code-reviewers + 1 security-reviewer + Codex (k-of-n).
- **Round 1 grade: F** — multiple consensus-passed P0/P1 (the guard had real security holes). Auto-fix loop engaged (auto_fix=true).
- **Round 2:** security re-review of the fixes → all round-1 P0/P1 verified HOLDING; 2 new minor findings (1 applied, 1 declined-with-reason).
- **Final grade: A** — 0 consensus-passed P0/P1 remaining. **APPROVED.**

## 🔍 Drift Findings
**clean.** All changed files are within PLAN Phase 4 scope.

## ✅ Consensus Findings (round 1) — all FIXED

| Sev | Sources | Finding | Fix |
|-----|---------|---------|-----|
| **P0** | Codex + code-reviewer | **Marker not worktree-aware** — `evaluate()` used `Path.cwd()`; during a worktree-isolated autonomous run the marker (at base root) isn't found → guard silently no-ops in the exact mode it guards | `_resolve_root(payload)` mirrors worktree_gate (workspace.current_dir/cwd/env) + walks up + handles the `.worktrees/` parent. Test `test_resolve_root_finds_marker_from_worktree_subdir`. |
| **P0/P1** | security + Codex | **Bash-redirect + hooks.json self-disable** — Write-tool block didn't cover `echo > .claude/settings.json`; nothing protected `.claude/hooks/hooks.json` (the agent could edit out this very guard) | New `permission-surface-write` Bash regex (catches redirect/tee/sed/`python -c open()` by filename-substring) + `NEVER_AUTO_WRITE_PATH` now covers settings + `.claude/hooks/hooks.json` + cursor/codex hooks. Tests for Bash-redirect + all 3 Write tools. |
| **P1** | Codex + security + code-reviewer | **`git -c k=v push` bypass** — adjacency regex `\bgit\s+push\b` missed option prefixes | Replaced regex with a word-tokenizer `_git_segment_hit` (skips `-c VALUE`/`-C`/`--flag` prefixes; handles N consecutive `-c`). Tests for `git -c`/`-C`/`--no-pager push`. |
| **P1** | Codex + security + code-reviewer | **`rm "$HOME"/x` / `find -delete` bypass** | rm regex widened to catch `$`-expansion; new `find-delete` pattern. Tests. |
| **P1** | security | **Stale marker cross-session** — project-scoped uuid can't tell a crashed session's marker from the current one | `_MARKER_TTL_HOURS=18` freshness gate in `active_marker` (+ unparseable created_at → stale). Test. |

## 📝 Manual-Only / lower-severity (round 1) — applied

- P2 missing `timeout` on the guard hook entries → added `"timeout": 10` (both matchers).
- P2 publish list omissions → added `docker push`, `helm upgrade`, `aws s3 cp/sync/rm`, `gcloud deploy/run deploy`.
- P1/P2 test gaps (tests reviewer) → added: OFF→no-op for Write tools, main() Write-path exit-2, `git stash clear` block, benign-git ALLOW (`git stash list/show/pop`, `git commit -m "...push..."`, `git log --grep=push`), baseline-categories assertion.

## 🔁 Round 2 (security re-review of the fixes)

All 5 round-1 P0/P1 fixes **verified holding** by an adversarial security pass. Two new findings:

| Sev | Finding | Disposition |
|-----|---------|-------------|
| P2 | Future-dated `created_at` (negative age) slipped past the one-sided `> TTL` check → a crafted far-future marker could keep autopilot armed forever | **APPLIED** — `active_marker` now rejects `age_s < 0` too. Test `test_future_dated_marker_rejected`. |
| P1 | `shlex.split` `ValueError` → `str.split()` fallback can FALSE-POSITIVE-block a *malformed-quote* benign command containing `git push` text | **DECLINED (with reason), recorded.** The reviewer's "return None on ValueError" fix would convert this into a false-NEGATIVE bypass (`git push "unclosed` → ValueError → allowed) — the dangerous direction for a security guard. The `str.split` fallback is block-biased (over-block on malformed shell), which is the safe direction: a malformed command under active autopilot is worth pausing anyway. Rationale documented inline in `_git_segment_hit`. |

## 🤝 Disagreements

The one genuine reviewer-vs-implementer divergence is the round-2 P1 above: the security-reviewer's suggested fix optimizes for no-false-positive, but a security guard must optimize for no-false-negative. Resolved by keeping the safe (block-biased) fallback and documenting why — new evidence (the bypass it would introduce), not a fold.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | F     | — (findings only) | 5 consensus P0/P1 | — |
| 2 (auto-fix + security re-review) | **A** | all 5 P0/P1 + 2 P2 + future-TTL; test hardening | 0 consensus P0/P1 | 1 declined-with-reason (false-positive-only, safe) |

Final grade: **A** · Iterations: 2 / 3 · Status: **APPROVED** · human_review_needed: false

Post-fix verification: guard+autopilot tests 50 passed; full `pytest` exit 0; `ruff` + `ruff format` clean; `mypy --strict` clean; 8 snapshots regenerated (hooks.json timeout sha, install_ref pinned → deterministic).
