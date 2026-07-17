---
type: review
task_slug: loop-longevity-strategies
status: APPROVED
created: 2026-05-09
reviewers_invoked: [code-reviewer-A, code-reviewer-B, security-reviewer]
consensus_method: cross-check (2/3)
---

## 🎯 Round 1 Summary

**Grade: B** (1 consensus-passed P1 found; threshold A not met; auto-fix applied)

- Consensus-passed findings: 1 (P1)
- Auto-fix eligible: 1
- Weak-consensus findings: 2 (manual-only, not auto-fixed)
- Manual-only findings: 1 (significant, noted for user awareness)

After auto-fix loop: **Grade: A → APPROVED**

---

## 🔍 Drift Findings

No scope drift detected. All changed files are within PLAN phase scope:
- `src/harness_maker/autoloop_driver.py` — Phase 1a scope
- `src/harness_maker/hooks/loop_gate.py` — Phase 1b scope
- `src/harness_maker/templates/hooks/hooks.json.j2` — Phase 1b scope
- `src/harness_maker/templates/cursor/hooks.json.j2` — Phase 1b scope
- `src/harness_maker/templates/commands/hm/loop.md.j2` — Phase 1a+1b scope
- `src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2` — Phase 1a scope
- `tests/unit/hooks/test_loop_gate.py` — Phase 1b scope
- `tests/unit/test_autoloop_driver.py` — Phase 1a scope

---

## ✅ Consensus Findings

### CP-1 [P1] `test_git_as_file_stops_walk` doesn't prove boundary enforcement
- **File**: `tests/unit/hooks/test_loop_gate.py:79`
- **Tag**: `consensus-passed` (A-F2 + B-F2, strong consensus)
- **Evidence**: The test plants no marker above the `.git`-as-file boundary. A broken `_find_marker()` that ignored `.git`-as-file and walked all the way to filesystem root would still return `None` and the test would still pass — because there happens to be no marker above `tmp_path` during test execution. The guard is effectively untested.
- **Reasoning (OBSERVE → INFER → CONCLUDE)**:
  - OBSERVE: `test_git_as_file_stops_walk` calls `_find_marker(subdir)` and asserts `None`. No marker exists anywhere above `tmp_path` in the test environment.
  - INFER: The assertion cannot distinguish between "walk stopped at `.git`-as-file" and "walk continued to filesystem root and found nothing". Both produce `None`.
  - CONCLUDE: The boundary invariant is not tested; a future refactor that breaks `.git`-as-file detection would silently pass this test.
- **Suggestion**: Plant `(tmp_path.parent / ".hm-loop-active").touch()` before the assertion and clean up in `finally`. This makes the test fail if the walk goes past the boundary.
- **Status**: ✅ Applied (Fix #1)

---

## ⚠️ Weak Consensus

### WC-1 [P1] `loop_gate.py:14` — walk unbounded when no git ancestor exists
- **File**: `src/harness_maker/hooks/loop_gate.py:14`
- **Tag**: `weak-consensus` (B-F1 surface-matches S-F1, reasoning diverges)
- **Reviewer B reasoning**: OBSERVE: walk iterates `[cwd, *cwd.parents]` until `.git` is found; if cwd is outside any git repo (bare `/tmp`, CI ephemeral FS), the walk goes to `/`. INFER: At each level, checking `.git` existence on every ancestor is O(depth) filesystem I/O. CONCLUDE: Negligible performance risk; functional correctness risk is "never finds marker, returns None" which is the safe path.
- **Reviewer S (security) reasoning**: OBSERVE: same walk pattern. INFER: If cwd is `/`, `Path("/").parents` is `(Path("/"),)` — walk terminates immediately. CONCLUDE: Not a security issue; at worst a missed marker in non-git contexts.
- **Divergence**: B says performance-negligible; S says not a security issue. Both agree it's not critical but frame the risk differently.
- **Manual judgment**: The current behavior (return None when no git ancestor) is the correct safe path. The walk terminates at filesystem root naturally. Accept as acceptable trade-off — no change needed unless performance profiling shows real cost.

### WC-2 [P1] `loop_gate.py:77` — isatty guard vs stdin blocking concern
- **File**: `src/harness_maker/hooks/loop_gate.py:77`
- **Tag**: `weak-consensus` (A-F1 surface-matches B-F3, reasoning diverges)
- **Reviewer A reasoning**: OBSERVE: `if not sys.stdin.isatty(): stdin_text = sys.stdin.read()`. INFER: When invoked from Claude Code hook infrastructure, stdin is always a pipe with JSON payload. CONCLUDE: isatty guard is correct and necessary — prevents blocking on interactive terminal invocations during debugging.
- **Reviewer B reasoning**: OBSERVE: Same guard. INFER: Hook runners pipe JSON; manual invocations won't pipe stdin. CONCLUDE: Guard is correct but could also default `stdin_text=""` on isatty rather than empty string, which is what the code already does.
- **Divergence**: Both agree the guard is correct. A frames it as "necessary"; B frames it as "already handled correctly". No actionable difference.
- **Manual judgment**: No change needed. Current behavior is correct.

---

## 📝 Manual-Only Findings

### MO-1 [P1] `loop_gate.py:13` — uses `Path.cwd()` instead of workspace path from hook payload
- **File**: `src/harness_maker/hooks/loop_gate.py:13`
- **Tag**: `manual-only` (S-F2, single source — Security Reviewer)
- **Finding**: Claude Code Stop hook stdin JSON contains a `workspace` field with the project root path. `_find_marker()` defaults to `Path.cwd()` which is the Claude Code process cwd, not necessarily the project root. In multi-project or nested repo scenarios, cwd might differ from workspace root.
- **Reasoning**: OBSERVE: `cwd = start_dir if start_dir is not None else Path.cwd()`. Stop hook payload has `{"stop_hook_active": bool, "workspace": "/path/to/project"}`. INFER: If hook process cwd != workspace root, `_find_marker()` starts walking from wrong dir. CONCLUDE: Marker at workspace root would not be found; loop gate silently fails to block session close.
- **Severity assessment**: P1 in isolation, but in practice Claude Code sets hook process cwd = project root (same as workspace). Verified by Claude Code hook docs. Risk is low in current deployment context.
- **Recommendation**: Consider parsing `workspace` from stdin JSON in `_stop_hook()` and passing it as `start_dir` to `_find_marker()`. Future-proofs against cwd drift. Not blocking for current release.
- **Status**: ❌ Not auto-fixed (single source, manual-only). Noted for future improvement.

---

## 🤝 Disagreements

None — all severity disagreements resolved via consensus rules above.

---

## Iteration Record

### Iteration 1 (Grade: B → A)

Fixes applied: 1

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Plant marker above .git-as-file boundary to prove walk stops | `tests/unit/hooks/test_loop_gate.py:79` | Applied |

Remaining consensus-passed: 0 | New issues introduced: 0

Build verification: `uv run pytest tests/unit/hooks/ -v` → 9 passed ✅

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1         | —   |
| 2 (fix)   | A     | 1             | 0         | 0   |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false

### Notable manual-only item for next iteration
`MO-1` (workspace path vs cwd in loop_gate.py) is worth addressing before the Stop hook sees wide deployment. Low risk in current Claude Code environments but a defensiveness improvement worth tracking.
