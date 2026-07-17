---
type: review
task_slug: multisession-fleet-reverify
status: APPROVED
created: 2026-06-21
reviewers_invoked: [concurrency-reviewer, code-reviewer, security-reviewer, codex]
consensus_method: k-of-3 (cross-check + Codex third voter)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multisession-fleet-reverify
  computed_at: 2026-06-21
---

# REVIEW — multisession-fleet-reverify (H1 memory-tier locking)

## 🎯 Round 1 Summary

- **Grade (Round 1): B** — consensus-passed: 0× P0, 1× P1, 1× P2.
- 4 voices: concurrency / code / security reviewers + Codex (gpt-5.5) as the k-of-3 third voter (Production preset → mandatory; `codex_status: invoked`).
- No PR metadata exists (execute did not commit), so the 2-pass redaction collapsed to one pass — there was nothing to anchor on.
- Auto-fix round 2 applied 8 fixes → **Grade A**, then a fresh-eyes Codex re-review confirmed the fixes sound (heterogeneous-review lesson: author self-review of auto-fixes is insufficient).
- Core design **confirmed sound** by all reviewers: RMW fully inside the lock, `.lock` sentinel never the target `.md` (mutual exclusion holds across `os.replace`), reentrancy correct, the concurrency proof is genuinely cross-process (subprocess, not threads), no unlocked writer path remains.

## 🔍 Drift Findings

`drift_verdict: clean`. All 14 changed files map to a PLAN phase (Phase 1: memory_md + test; Phase 2: flush_session + test; Phase 3: wrapup.md.j2 + 8 snapshots + render-gate test). No scope drift, no incomplete phase.

## ✅ Consensus Findings (consensus-passed)

| # | Sev | File | Issue | Sources | Resolution |
|---|-----|------|-------|---------|------------|
| 1 | **P1** | memory_md.py:154 | **Heading-shaped body line** (`## [tier:cat] slug`) injected into an entry body becomes a phantom heading on the next upsert → silent truncation (wiki) or tier DoS (failures) | security + code-reviewer (2/4, same surface+reasoning) | **FIXED** — `_upsert` now rejects any body line matching `_HEADING_RE`; regression tests `test_upsert_wiki_rejects_heading_shaped_body` + `test_upsert_failure_rejects_heading_shaped_body` |
| 2 | **P2** | memory_md.py:52 | `_base_root` stripped at the **first** `.worktrees` segment → mis-targets lock + memory for a path with a `.worktrees` ancestor | codex + concurrency + security (3/4) | **FIXED** — strips at the **last** occurrence; residual edge accepted (see below) |

## ⚠️ Weak Consensus

None — surface matches all had aligned reasoning.

## 📝 Manual-Only Findings (single-source; all triaged)

| # | Sev | File | Issue | Source | Resolution |
|---|-----|------|-------|--------|------------|
| 3 | P1 | memory_md.py:148 | **Markerless-but-non-empty** tier file (lost both markers but has entries) treated as benign-fresh → silently split into unmanaged-old + managed-new halves (contradicts fail-closed design) | codex (HIGH) | **FIXED** — now fail-closed (`MemoryBlockError`) when text is non-empty without markers; only absent/empty is benign-created. Test `test_failclosed_markerless_nonempty_file` |
| 4 | P1 | test_memory_md.py | Same-slug **count++** (sharpest read-N→write-N+1 lost-update) tested only sequentially | concurrency | **FIXED** — added `test_subprocess_concurrent_upsert_failure_same_slug_count` (12 processes, same slug → `count:12` exactly) |
| 5 | P2 | wrapup.md.j2 | 3 new memory_md blocks emitted `Bash("…")` unconditionally — not `{% if is_codex %}`-branched like every other block → Claude Code would show literal text instead of an auto-run `!` line | code-reviewer | **FIXED** — wrapped all 3 in the `is_codex` branch (render-gate still passes) |
| 6 | P2 | memory_md.py | No `--slug`/`--category` validation → a value with `]`/`|`/space makes the heading un-reparseable → silent duplicate instead of replace | code-reviewer | **FIXED** — `_SLUG_RE`/`_CATEGORY_RE` validation; tests `test_upsert_rejects_invalid_slug`/`_category` |
| 7 | P2 | wrapup.md.j2:197 | Temp-file body handoff under-specified ("unique temp file" — no scheme/cleanup → collision risk + Step-6 mis-staging) | security | **FIXED** — template now mandates a unique `mktemp` path **outside the repo** + delete after |
| 8 | P3 | memory_md.py:94 | `append_session` on an existing-but-empty file → leading blanks, no header | code-reviewer | **FIXED** — empty-existing treated like absent |
| 9 | P2 | _locking.py:67 | fcntl-absent → silent no-op (no mutual exclusion) for the H1 tiers | concurrency | **ACCEPTED** — pre-existing shared primitive (also guards semantic/profile); N-A on WSL2/Linux/macOS (have fcntl); documented as the no-fcntl boundary in PLAN ADR-004 + Success Criteria. Not touched (changing it affects the structured stores). |
| 10 | P2 | memory_md.py:53 | `_base_root` still mis-roots a repo **located inside** a `.worktrees` dir (e.g. `/x/.worktrees/repo`, no `<name>` suffix) | codex (re-review) | **ACCEPTED residual** — pathological (repo must live in a `.worktrees` dir; N-A for `/home/noel/harness-maker`); a robust fix needs git-worktree introspection disproportionate to this pure-path helper. Common ancestor case is fixed (#2). |
| 11 | P2 | io_utils.py:36 | `atomic_write` final mode is umask-dependent (ends 0600 via NamedTemporaryFile) | security | **NOTED, out of scope** — pre-existing shared helper, not in this diff; errs private (acceptable). |
| 12 | P3 | memory_md.py:190 | `splitlines()`+join normalizes EOF blank lines / line-endings outside the block | codex | **ACCEPTED** — LF-only managed files; benign normalization. |
| 13 | P2 | memory_md.py:53 | Lock-path **symlink** divergence between CLI and hook | concurrency | **REFUTED** — `Path.resolve()` canonicalizes symlinks, so both callers converge on the same real path (the opposite of divergence). |
| 14 | P3 | _locking.py:84 / memory_md.py:255 | lock-dir mode; `--body-file` arbitrary path read | security | **ACCEPTED** — local same-user CLI; O_NOFOLLOW+0600 fd already closes the symlink/leak vector. |

## 🤝 Disagreements

Severity spread on finding #2 (`_base_root`): codex P2 / concurrency P3 / security P2 → resolved to **P2** (majority). No reasoning-level disagreements.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 2 consensus + 6 real manual | — |
| 2 (auto-fix) | **A** | 8 (+ fresh-eyes re-review) | 0 consensus P0/P1; 5 accepted/refuted residuals | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false

**Verification:** full `pytest` + `ruff check` + `ruff format --check` + `mypy --strict src/` GREEN from base; 8 snapshots regenerated (post-finalize, from base — count:7 trap avoided). All round-2 fixes carry a passing regression test. Fresh-eyes Codex re-review of the fix diff found no new lost-update/corruption hole.
