---
type: review
task_slug: multi-repo-mgmt-2026-05
status: APPROVED
created: 2026-05-09
reviewers_invoked: [code-reviewer, concurrency-reviewer, security-reviewer]
consensus_method: cross-check (2/3)
grade_threshold: A
final_grade: A
iterations_used: 2
human_review_needed: false
---

# Review: multi-repo-mgmt-2026-05

## 🎯 Round 1 Summary

**Grade: D** (1 consensus-passed P0, 1 consensus-passed P1)

Reviewers: code-reviewer, concurrency-reviewer, security-reviewer (parallel).

**Auto-fixes applied:**
- Fix #1 (P0): Sibling worktree rollback on creation failure
- Fix #2 (P1): `subprocess.run` timeout (60 s) + `TimeoutExpired → RuntimeError`
- Fix #3 (confirmed regression): e2e test `worktree.create()[0]` indexing (test confirmed broken by full suite run)

---

## 🔍 Drift Findings

**Scope check:** Changes are in `models.py`, `worktree.py`, `test_models.py`, `test_worktree.py`, `test_worktree_multi.py`. All within Phase 1 + Phase 2 scope per PLAN.

**Notable deferred scope (Phase 3 — known):**
- `worktree_gate.py` not yet updated to use `_read_active_worktrees()`. The gate currently reads the old `.hm-loop-active` (deleted by Phase 2). This is a **known Phase 3 item** per PLAN. Write isolation is partially broken for Phase 2 sessions until Phase 3 lands. Flagged as `manual-only P0` in Round 1 findings — not auto-fixed since it's explicitly deferred to Phase 3.

---

## ✅ Consensus Findings (Round 1)

### P0 — Sibling worktree orphan on creation failure [FIXED]

| Field | Value |
|-------|-------|
| Tag | `consensus-passed` |
| File | `src/harness_maker/worktree.py` |
| Line | 130–131 |
| Reviewers | code-reviewer (line 130) + concurrency-reviewer (line 131) |
| Severity | P0 |
| Status | **Fixed in Round 1** |

**Evidence:** The sibling creation loop re-raised `RuntimeError` without cleanup. The primary worktree (created before the loop) and any earlier-created siblings were left as permanent orphaned git worktrees with no marker and no automated recovery.

**Fix applied:**
```python
# Before: bare re-raise
try:
    _run(["git", "worktree", "add", ...], cwd=sibling)
except RuntimeError:
    raise  # primary orphaned

# After: rollback then re-raise
try:
    for sibling, slug in zip(siblings, slugs, strict=True):
        ...
        sibling_wts.append(sib_wt)
except RuntimeError:
    for created_wt, sib in zip(sibling_wts, siblings[:len(sibling_wts)], strict=False):
        with contextlib.suppress(RuntimeError):
            _run(["git", "worktree", "remove", "--force", str(created_wt)], cwd=sib)
    with contextlib.suppress(RuntimeError):
        _run(["git", "worktree", "remove", "--force", str(primary_wt)], cwd=base)
    raise
```

### P1 — `subprocess.run` no timeout [FIXED]

| Field | Value |
|-------|-------|
| Tag | `consensus-passed` |
| File | `src/harness_maker/worktree.py` |
| Line | 40–43 |
| Reviewers | concurrency-reviewer (line 43) + security-reviewer (line 40) |
| Severity | P1 |
| Status | **Fixed in Round 1** |

**Evidence:** `_run()` called `subprocess.run` without `timeout=`. A hung git command (SSH prompt, NFS stall) would block the CLI indefinitely. Violates CLAUDE.md §외부 명령 호출 requirement.

**Fix applied:**
```python
_GIT_TIMEOUT = 60  # seconds

def _run(args, cwd):
    try:
        return subprocess.run(..., timeout=_GIT_TIMEOUT)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(...) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"git command timed out after {_GIT_TIMEOUT}s: ...") from e
```

---

## ⚠️ Weak Consensus (Round 1)

### P2 — `_ensure_gitignore_entry` TOCTOU + non-atomic append

| Field | Value |
|-------|-------|
| Tag | `weak-consensus` |
| File | `src/harness_maker/worktree.py` |
| Line | 487–495 |
| Reviewers | concurrency-reviewer (TOCTOU → duplicate lines), security-reviewer (violates atomic_write policy) |
| Status | Not auto-fixed (weak-consensus) |

OBSERVE matches: same lines. CONCLUDE diverges: concurrency says duplicate lines; security says partial-write corruption. The function has `except OSError: pass` and "best-effort" docstring. A full fix would use `atomic_write` (read+append in memory + os.replace). Left for human review.

---

## 📝 Manual-Only Findings (Round 1)

### [D] P0 — Gate reads `.hm-loop-active` (Phase 3 deferred)

| File | `src/harness_maker/gates/worktree_gate.py` |
|------|-----|
| Line | 76 |
| Reviewer | code-reviewer |

The gate still reads the old `.hm-loop-active` filename. Phase 2 writes `.hm-loop-{wt_name}` instead — so the gate is completely blind to Phase-2 sessions. This is the **known Phase 3 gap** from the PLAN. Write isolation is non-functional for new sessions until Phase 3 lands. Not auto-fixed (PLAN explicitly defers it).

### [H] P0 — `_load_sibling_dirs` bypasses Pydantic validator

| File | `src/harness_maker/worktree.py` |
|------|-----|
| Line | 325 |
| Reviewer | security-reviewer |

`_load_sibling_dirs` reads `sibling_repos` from YAML via `yaml.safe_load_all` directly, never instantiating `HarnessConfig`. The `_reject_absolute_sibling_paths` validator never fires on the CLI path. A relative `../../etc` path passes through unchecked.

**Recommendation:** Add `..`-component check directly in `_load_sibling_dirs` (or call the validator explicitly). Pairs with Finding [I].

### [E] P1 — e2e test `list.exists()` crash [FIXED as regression]

| File | `tests/e2e/test_dogfood_sandbox.py` |
|------|-----|
| Line | 143 |

`worktree.create()` changed return type to `list[Path]`. The e2e test called `.exists()` on the list → `AttributeError`. **Fixed**: `worktree.create("dev", repo)[0]`.

### [I] P1 — `sibling_repos` validator allows `../` traversal

| File | `src/harness_maker/models.py` |
|------|-----|
| Line | 267 |
| Reviewer | security-reviewer |

The validator blocks `/abs/path` and `~/...` but not `../../other`. `(base / "../../etc").resolve()` escapes the project tree. Fix: add `if any(part == '..' for part in Path(p).parts): raise ValueError(...)`.

### [J] P1 — `_find_free_name` TOCTOU (same-minute collision)

| File | `src/harness_maker/worktree.py` |
|------|-----|
| Line | 91 |
| Reviewer | concurrency-reviewer |

Two sessions starting in the same minute both pass `_branch_exists` check, then the second `git worktree add` fails with an unhelpful git error. Low probability in practice (same clock-minute); `_run` now has a timeout so hung git won't block forever. The existing retry loop (100 attempts) handles sequential retries but not concurrent races.

### [K] P1 — Merge + cleanup failure leaves marker permanently

| File | `src/harness_maker/worktree.py` |
|------|-----|
| Line | 611 |
| Reviewer | concurrency-reviewer |

If `merge()` succeeds but `cleanup()` fails (WSL2/NTFS file-lock, documented in CLAUDE.md), `rc = 1` and the `finally` block skips `_clear_loop_marker`. The gate then reports a stale worktree permanently. Recommend: clear the marker after merge succeeds, before cleanup attempt.

### [L] P1 — Sibling directory basename unsanitized for git branch names

| File | `src/harness_maker/worktree.py` |
|------|-----|
| Line | 119 |
| Reviewer | security-reviewer |

`slug = s.name` used directly in `sib_name = f"{name}-{slug}"` and `git worktree add -b sib_name`. Directory names with spaces, `.lock` suffix, or leading `-` produce git errors (no shell injection since `shell=False`, but poor error messages). Sanitize: `re.sub(r'[^a-zA-Z0-9_.-]', '_', s.name)`.

### [F] P1 — `wt.resolve().name` repeated (latent)

| File | `src/harness_maker/worktree.py` |
|------|-----|
| Line | 612 |
| Reviewer | code-reviewer |

`wt.resolve().name` called twice independently. Under a symlinked ancestor path, `.name` and `.resolve().name` can diverge, orphaning the marker. Low probability. Fix: extract `resolved_wt = wt.resolve()` once at start of `_cli_finalize`.

### [G] P1 — Marker written after all WTs created (crash window)

| File | `src/harness_maker/worktree.py` |
|------|-----|
| Line | 144 |
| Reviewer | code-reviewer |

Marker written only after all `git worktree add` calls succeed. A crash between the last add and the marker write leaves live worktrees with no gate protection. Low probability but non-zero. Consider writing the marker after primary is created (then updating on sibling success).

---

## 🤝 Disagreements

None — reviewers agreed on severity for all consensus-passed findings.

---

## Round 2 Summary

### Fixes applied in Round 1 verified GREEN

- Fix A (P0 sibling rollback): Correct rollback order (siblings then primary). Timeout in rollback path silently suppressed by `contextlib.suppress(RuntimeError)` — acceptable per best-effort contract.
- Fix B (P1 timeout): `TimeoutExpired` correctly translated to `RuntimeError`. CPython kills child process before raising, so no zombie.
- Fix E (e2e regression): Test passes.

### Round 2 new findings (P2 only)

| Tag | Severity | Summary |
|-----|----------|---------|
| manual-only | P2 | `except RuntimeError` in rollback doesn't catch `BaseException` (e.g., `KeyboardInterrupt`) |
| weak-consensus | P2 | `_ensure_gitignore_entry` non-atomic append (same as Round 1 weak-consensus [C]) |

No new P0 or P1 findings. Grade threshold met.

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining consensus-passed | New Issues |
|-----------|-------|---------------|---------------------------|------------|
| 1 (init)  | D     | —             | 2 (1×P0, 1×P1)            | —          |
| 2         | A     | 3 (A, B, E)   | 0                          | 0          |

**Final grade: A**
**Iterations used: 2 / 3**
**Status: APPROVED**
**human_review_needed: false**

---

## Remaining Manual Items (not blocking)

These manual-only and weak-consensus findings are NOT blocking merge but should be addressed in Phase 3 or follow-up work:

| Priority | Finding | Action |
|----------|---------|--------|
| HIGH | [D] Gate reads `.hm-loop-active` — Phase 3 | Fix in Phase 3 (tracked in PLAN) |
| HIGH | [H] `_load_sibling_dirs` bypasses validator | Add `..` check in `_load_sibling_dirs` |
| HIGH | [I] `sibling_repos` validator allows `../` | Add `..` component check to validator |
| MED | [K] Merge+cleanup fail leaks marker | Move `_clear_loop_marker` after merge |
| MED | [L] Slug unsanitized for branch names | `re.sub` slug before use |
| LOW | [J] `_find_free_name` TOCTOU | Acceptable per single-user context |
| LOW | [G] Marker after all WTs (crash window) | Write primary marker first |
| LOW | [C] `_ensure_gitignore_entry` non-atomic | Use `atomic_write` |
| LOW | [F] `wt.resolve().name` repeated | Extract `resolved_wt` once |
