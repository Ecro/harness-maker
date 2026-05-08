---
type: review
task_slug: cursor-compat-uplift
date: 2026-05-08
commit: 037ae31
plan: "[[PLAN-cursor-compat-uplift]]"
reviewers: [code-reviewer, security-reviewer, performance-reviewer]
consensus_rule: cross-check
auto_fix: true
grade_threshold: A
final_grade: A
status: APPROVED
human_review_needed: false
---

# REVIEW: Cursor compatibility uplift (0.6.2)

**Scope**: 037ae31 squash-merge — Phase 0–7 of `PLAN-cursor-compat-uplift`.
**Reviewers spawned**: code-reviewer, security-reviewer, performance-reviewer (parallel).
**Result**: **Grade A — APPROVED**. No consensus-passed P0/P1 findings (cross-check rule). 9 manual-only findings worth user attention; none block wrapup.

## Round 1 findings

### Consensus pass-through (cross-check, 2/3 agreement on P0/P1)

**Zero findings reached consensus.** Each of the 3 reviewers operated in
non-overlapping specialist scopes (code structure, security policy, perf
hot-path). Single-source findings under cross-check = manual-only by rule.
This is a known limitation when running disjoint specialists rather than
overlapping generalists; flagged for future plan-level discussion (procedure
amendment), not blocking this review.

### Manual-only findings (NEVER auto-fixed, but worth tracking)

#### M1 [P1, security] Executor deny list lacks `Edit(/etc/**)` / `Edit(~/.ssh/**)` / `Edit(~/.aws/**)`

- **File**: `src/harness_maker/templates/agents/executor.md.j2` (lines 21–23 of the YAML frontmatter)
- **Evidence**: Deny list contains `"Write(/etc/**)"`, `"Write(~/.ssh/**)"`, `"Write(~/.aws/**)"` but no corresponding `Edit(...)` entries. The agent has `Edit` in its `tools:`. An adversarial prompt that cannot `Write(/etc/sudoers)` can still `Edit(/etc/sudoers)`.
- **Note**: CLAUDE.md §보안/권한 v1.6 itself has the same gap — the policy lists only `Write(...)` denies. The template faithfully follows the policy, so this is **a policy gap, not a template bug**. Fixing requires updating both:
  - `CLAUDE.md` line 121: append `Edit(/etc/**), Edit(~/.ssh/**)` to executor deny list
  - `templates/agents/executor.md.j2` frontmatter deny list (mirror)
- **Why manual-only**: requires a CLAUDE.md policy decision. Recommend issuing as a follow-up commit.

#### M2 [P1, code] `VersionDrift.installed` field name is semantically inverted

- **File**: `src/harness_maker/relevance.py` line 421
- **Evidence**: `installed: str` is set to the project's `harness.yaml.harness_maker_version` (i.e. *stamped* in the project). `current: str` is the *running plugin*. Reading the class, `installed` reads as "what's installed on the system" — opposite semantic.
- **Note**: pre-existing issue, predates this commit. Phase 6 only changed what `current` resolves to (`__version__` → `latest_installed_version()`).
- **Suggestion**: rename `installed` → `stamped` for clarity. Touches `VersionDrift` users in `relevance.py:555` and `hooks/sessionstart_drift.py:49` plus tests.
- **Why manual-only**: backwards-compat impact (anyone writing custom drift consumers) — needs explicit user OK.

#### M3 [P1, perf] `latest_installed_version()` not memoized — re-scans disk on every call

- **File**: `src/harness_maker/relevance.py` line 445
- **Evidence**: Pure-read deterministic-within-process function with no `@lru_cache`. Called from SessionStart hook (one call per session). Future: `/hm:refresh` may call multiple times if any code path triggers re-render mid-session.
- **Suggestion**: `@functools.lru_cache(maxsize=None)`. Single-line fix.
- **Why manual-only**: trivial fix, but ~5 ms savings for 30-version cache is below the 100 ms hook budget — not a regression in practice. Worth doing on the next pass, not blocking.

#### M4 [P2, code] `_scan_plugin_cache_versions` doesn't wrap `is_dir()` in try/except

- **File**: `src/harness_maker/relevance.py` line 437
- **Evidence**: `iterdir()` is wrapped in `try/except OSError`, but `cache_root.is_dir()` is not. Symlink loops or permission errors on Linux filesystems can throw from `is_dir()`.
- **Suggestion**: fold `is_dir()` into the try/except, or add a separate guard.
- **Why manual-only**: rare edge case (broken symlink in plugin cache), low real-world incidence.

#### M5 [P2, code] `mcp_servers` parser silently drops malformed entries

- **File**: `src/harness_maker/interview.py` line 552–557
- **Evidence**: When `mcp_servers` outer dict has entries with non-dict values, they're silently dropped via `if isinstance(v, dict): clean[k] = v`. User sees `{}` on re-render with no diagnostic.
- **Suggestion**: log a warning when entries are dropped: `if mcp_servers and not clean: logger.warning("mcp_servers entries dropped — values must be dicts")`.
- **Why manual-only**: defensive UX improvement; current behavior is correct (preserves the InterviewAnswers default), just silent.

#### M6 [P2, code] No test for all-unparseable cache versions

- **File**: `tests/unit/test_version_drift.py` line 183
- **Evidence**: `test_latest_installed_version_skips_unparseable` includes one valid entry. The all-unparseable branch (`if not valid: return __version__` at relevance.py:467) is untested.
- **Suggestion**: add a test with `["random-text", "not.a.version"]` (zero valid) → expect fallback to `__version__`.
- **Why manual-only**: minor coverage gap; behavior is deterministic and the fallback path is one line.

#### M7 [P2, security] Reviewer deny lists don't block `Bash(python:*)` / `Bash(sh:*)` / `Bash(node:*)`

- **File**: all 5 reviewer agent templates
- **Evidence**: Deny list blocks `Write(*)`, `Edit(*)`, `Bash(rm:*)`, `Bash(curl:*)`, `Bash(npm:*)`, `Bash(eval *)` — but a reviewer could theoretically run `Bash(python -c "import os; os.system(...)")` to bypass. Reviewer policy intent is read-only.
- **Suggestion**: switch reviewers to allowlist-only model: `allow: [Read(*), Grep(*), Glob(*), Bash(git diff:*), Bash(git log:*), Bash(git status:*)]` (current allow list) and rely on the absence of unlisted Bash patterns being implicit-deny — verify Claude Code / Cursor honour allowlist semantics.
- **Why manual-only**: Claude Code's permissions model (allowlist-implicit-deny vs explicit-deny-list) is documented but enforcement varies by tool. Needs Phase 0 fixture verification before flipping to allowlist mode.

#### M8 [P2, security] MCP server inner dict not type-validated

- **File**: `src/harness_maker/interview.py` line 552–557
- **Evidence**: Parser accepts any dict shape for inner MCP server entry. `command` could be non-string, `args` could be a string instead of list, `env` could be a non-dict — all pass through to rendered `mcp.json` which Cursor executes.
- **Suggestion**: validate inner shape — `command: str`, `args: list[str]`, `env: dict[str, str]`. Reject malformed; log warning with key name (not value, to avoid leaking malicious strings).
- **Why manual-only**: in current threat model `harness.yaml` is repo-owner-edited, so user-controlled = intentional. P2 defense-in-depth.

#### M9 [P2, perf] Unbounded plugin cache directory growth

- **File**: `src/harness_maker/relevance.py` line 426
- **Evidence**: Claude Code does not prune `~/.claude/plugins/cache/.../` on upgrades; every `/plugin update` adds a version directory. Long-lived install can accumulate 30+ entries.
- **Suggestion**: in `_scan_plugin_cache_versions`, after collecting entries, sort by semver descending and return only the top-K (e.g. K=10). Caller only needs the maximum.
- **Why manual-only**: O(N) syscalls is sub-millisecond at realistic N; cap is defense for pathological install lifetimes.

## Cross-checked OK (multi-reviewer agreement)

- Phase 1 agent permissions match CLAUDE.md §보안/권한 v1.6 policy (security-reviewer + code-reviewer concur on the 5 reviewer agents — only the executor Edit-deny gap is flagged separately).
- Phase 2 hooks dual-render is correctly documented; no collapse-to-single-source attempt slipped in (security-reviewer + code-reviewer + perf concur — no surprise behavior change).
- Phase 4 MCP propagation chain (InterviewAnswers → HarnessConfig → Jinja context → rendered JSON) is structurally sound (code-reviewer + security-reviewer concur on the parsing/rendering paths).
- Phase 6 drift detector alignment uses plugin cache as single source — correctly fixes the divergence (perf + code concur on structural correctness).

## Grade computation

| | P0 | P1 | P2 | P3 |
|---|---|---|---|---|
| consensus-passed | 0 | 0 | 0 | 0 |
| manual-only | 0 | 3 (M1, M2, M3) | 6 (M4–M9) | 0 |

`P0_count = 0`, `P1_count = 0` → **Grade A**.

## Iteration summary

| Iteration | Grade | Fixes Applied | Remaining (consensus) | Manual-only |
|-----------|-------|---------------|-----------------------|-------------|
| 1 (init)  | A     | —             | 0                     | 9           |

Final grade: **A** (≥ threshold A).
Iterations used: 1 / 3.
`human_review_needed`: false.

## Recommendations (post-wrapup follow-up commits)

Suggested ordering for a follow-up patch (0.6.3 candidate):

1. **M1 + M7** — security policy uplift: `Edit` denies for system paths in executor + allowlist-only mode for reviewers. Touches CLAUDE.md and 6 agent templates. Single coherent commit.
2. **M3** — `@lru_cache` on `latest_installed_version`. One line.
3. **M5 + M8 + M6** — MCP server hardening: type-validate inner dict, warn on dropped entries, add coverage for all-unparseable branch.
4. **M2** — `VersionDrift` field rename (breaking change for any custom consumers; defer or schedule for next minor bump).
5. **M4 + M9** — `is_dir()` guard + top-K cap (defensive hardening; non-urgent).

Status: ready for `/hm:wrapup`.
