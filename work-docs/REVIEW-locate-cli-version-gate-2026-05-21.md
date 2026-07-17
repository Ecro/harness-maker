---
type: review
task_slug: locate-cli-version-gate
status: APPROVED
created: 2026-05-21
reviewers_invoked: [code-reviewer, security-reviewer, security-auditor, performance-reviewer, concurrency-reviewer, ux-reviewer]
consensus_method: cross-check
auto_fix: true
grade_threshold: A
max_review_rounds: 3
rounds_used: 2
final_grade: A
human_review_needed: false
drift_verdict:
  result: scenario_miss
  scope_violations: []
  scenario_misses:
    - "tests/snapshot/test_cli_help.py was listed in PLAN §Testing Strategy but absent from execute output"
  task_slug: locate-cli-version-gate
  computed_at: 2026-05-21T14:35:00Z
  resolved_in_round: 2
notes: |
  User asked for "again and deeper" — invoked 6 reviewers via always-all routing
  (vs configured "code, security" pair). Round 1 grade was C (3 P1 consensus).
  Round 2 fixed all consensus-passed PLUS 8 additional manual-only findings the
  orchestrator judged credible (P0 KeyError, P1 Unicode-digit bypass, P1 Jinja
  word-split, P1 Cursor BOOTSTRAP inconsistency, etc.). Final grade A. The
  remaining manual-only findings are documented below for user awareness.
---

## 🎯 Round 1 Summary

| Aspect | Value |
|--------|-------|
| Reviewers invoked | 6 (always-all routing per user "deeper" ask) |
| Total findings | 24 (deduped) |
| Consensus-passed | 4 (3 P1, 1 P2) |
| Weak-consensus | 0 |
| Manual-only | 20 |
| Drift findings | 1 |
| **Round 1 grade** | **C** (0 P0, 3 P1 consensus-passed) |

Grade C is below threshold A → entered auto-fix loop.

## 🔍 Drift Findings (Step 2)

| # | Severity | File | Finding |
|---|----------|------|---------|
| D1 | P1 | `tests/snapshot/test_cli_help.py` | PLAN §Technical Design "Affected components" + §Testing Strategy listed this file; execute did not create it. Resolved Round 2: file created with 3 token-presence assertions (locate --help exit codes, make --help --require-version, priority rules). |

No scope violations (every file changed in execute is within PLAN scope).

## ✅ Consensus Findings (Round 1)

### P1 (3 findings)

| ID | File:line | Reviewers | Summary | Fix in Round 2 |
|----|-----------|-----------|---------|----------------|
| F2 | `cli.py:212` | code + ux (2/6) | `make --require-version` exits **2** when no install found — wrong contract (locate uses exit 3 for same condition) | ✅ Changed to `Exit(3)` |
| F3 | `locate.py:10` | code + security + perf + concurrency (4/6) | `DEFAULT_INSTALLED_PLUGINS_JSON = Path.home() / ...` evaluated at module import time — breaks test isolation; tests that monkeypatch HOME after import silently read developer's real file | ✅ Converted to lazy `_default_plugins_json()` function; test fixture updated to patch the function |
| F10 | `locate.py:80` | code + concurrency (2/6) | Silent swallow of `OSError` / `JSONDecodeError` makes torn-read race (concurrent `claude plugin install` writing the JSON) indistinguishable from "not installed" | ✅ Added stderr warning before returning None; new test `test_corrupt_json_emits_warning_and_returns_none` |

### P2 (1 finding)

| ID | File:line | Reviewers | Summary | Fix in Round 2 |
|----|-----------|-----------|---------|----------------|
| F7 | `cli.py:205` | code + ux (2/6) | `make --require-version` resolves against `Path.cwd()` not the `target` arg — wrong when target differs from cwd | ✅ Changed to `target.resolve()` |

## ⚠️ Weak Consensus

None — every finding either passed strong consensus (CONCLUDE clauses aligned) or stayed single-source.

## 📝 Manual-Only Findings (Round 1)

Single-source findings that did NOT auto-apply. **Orchestrator applied 8 of these in Round 2** based on concrete reproducer + low-risk fix; the remaining 4 are surfaced for user judgment.

### Applied in Round 2 (orchestrator override)

| ID | Severity | File | Reviewer | Summary | Fix |
|----|----------|------|----------|---------|-----|
| F1 | **P0** | `locate.py:50` | code | `_to_entry` raises KeyError on entries missing `version` / `installPath` — single corrupt entry crashes resolver instead of cleanly returning None | Added `_is_well_formed` filter applied PER TIER (tier_1 with only malformed entries now falls through to tier_2 rather than yielding nothing); `_to_entry` wrapped in try/except returning Optional; 3 new tests added |
| F11 | P1 | `make.md.j2:35` | security | `${HM:-{{ harness_maker_src_path }}}` Jinja substitution unquoted → bash word-split when HOME contains spaces (legitimate on WSL2 / macOS) | Single-quoted both Jinja substitutions in the bash one-liner |
| F12 | P1 | `locate.py:128` | security | `str.isdigit()` accepts Arabic-Indic digits (`٠–٩`) and fullwidth digits (`０–９`); `int()` then silently converts → user-controlled `installed_plugins.json` could bypass `--require-version` gate | Replaced `isdigit()` with `_ASCII_DIGITS_RE.fullmatch(p)` regex; 2 new tests verifying Unicode digit rejection |
| F17 | P1 | `cli.py:219` | ux | Version-mismatch error says only `claude plugin update harness-maker` — wrong command for Cursor (`git pull`) and Codex (`codex plugin update`) users | Multi-IDE error message now lists all 3 update commands + surfaces `marketplace` field |
| F18 | P1 | `cli.py:440` | ux | `locate` no-install error gives no actionable next step | Added `See docs/BOOTSTRAP.md for install instructions per IDE.` |
| F19 | P1 | `BOOTSTRAP.md:33` | ux | Cursor Step 1 (git clone) does NOT populate `installed_plugins.json` — Step 2's `harness-maker locate` would exit 3, breaking the documented flow | Added explicit Cursor note explaining the registry mismatch + alternate `HM_DIR="$HOME/.cursor/..."` snippet for Cursor-only environments |
| F20 | P1 | `BOOTSTRAP.md:112` | ux | Exit-2 recovery cell only mentioned `claude plugin update` | Expanded to list all 3 IDE update commands |
| F22 | P2 | `BOOTSTRAP.md:194` | ux | Migration block used `diff` format with `-` / `+` prefixes — copy-paste produces invalid shell | Replaced with Before / After pair of plain code blocks |
| F24 | P2 | `BOOTSTRAP.md:58` | ux | Shell example hardcoded `exit 3` instead of `exit $?` — loses real exit code | Changed to `exit $?` |
| F6 | P2 | `locate.py:16` | code | `LocateEntry.plugin` field was always `PLUGIN_NAME` constant; dead state | Removed field from NamedTuple and `_to_entry` |
| F4 (drift) | P1 | `tests/snapshot/test_cli_help.py` | code | PLAN-required file absent | Created with 3 token-presence assertions |
| F5 (gap) | P1 | `tests/unit/test_locate.py` | code | No regression test for F1 KeyError | Added 3 malformed-entry tests + 1 tier-fall-through test |
| F9 (gap) | P2 | `tests/unit/test_locate.py:113` | code | tier-1 tiebreak (two project-scope marketplaces both matching cwd) was untested | Added `test_tier_1_tiebreak_most_recent_installed_at_wins` |

### NOT applied — surfaced for user judgment

| ID | Severity | File | Reviewer | Summary | Rationale to skip |
|----|----------|------|----------|---------|-------------------|
| F13 | P2 | `locate.py:46` | security | No path-traversal validation on `installPath` / `projectPath` from `installed_plugins.json` | Defense-in-depth ask. The JSON is user-owned; any path the user puts there is one they could already access. Adding `is_relative_to(home/.claude/plugins)` would tighten the contract but break legitimate user-symlinked install paths. Mark as future hardening. |
| F14 | P2 | `cli.py:467` | security-auditor | `marketplace` field in `locate` JSON output could carry prompt-injection payload if user-controlled JSON is echoed verbatim into an LLM context | Self-attack only (attacker == user who owns the JSON file). Primary `--plain` use path is unaffected. Document in BOOTSTRAP.md or future hardening. |
| F15 | P1 | `make.md.j2:35` | performance | Added a second `uv run` cold-start to every `/hm:make` invocation (~300-700ms on WSL2/NTFS) | Intentional defense-in-depth per ADR-001 (locate gives canonical resolution; glob alone could pick wrong cache). Accepted regression — frequency of `/hm:make` is low. |
| F21 | P2 | `cli.py:451` | ux | `--require-version` parse error uses exit 2 (same as "version mismatch") | Real but low-priority; a third exit code (e.g. 1) would help scripts distinguish "you wrote a bad constraint" from "the install is stale". Defer to follow-up. |
| F23 | P2 | `BOOTSTRAP.md` | ux | No Troubleshooting section | Scope creep for this PLAN. Track for a follow-up doc PR. |
| F8 | P2 | `PLAN-locate-cli-version-gate.md:133` | code | PLAN §Phase 4 scope text says `locate --json`, implementation + Success Criteria say `--plain` | PLAN is gitignored (work-docs/); historical record. Internal contradiction, not user-facing. Optional cleanup. |

## 🤝 Disagreements

None — when multiple reviewers flagged the same file:line, their CONCLUDE clauses aligned (all 4 reviewers flagging F3 agreed it was a test-isolation issue; both reviewers on F10 agreed swallowing OSError silently was the problem).

---

### Iteration 2 (Grade: C → A)

Fixes applied: **13** (4 consensus-passed + 8 manual-only orchestrator-overrides + 1 drift + new tests)

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P0 (M1) | `_to_entry` KeyError | `locate.py:50` | Applied — try/except + per-tier malformed filter + 4 new tests |
| 2 | P1 (C2) | Wrong exit code in `make --require-version` no-install | `cli.py:212` | Applied — Exit(3) instead of Exit(2) |
| 3 | P1 (C3) | Import-time `Path.home()` | `locate.py:10` | Applied — lazy `_default_plugins_json()` |
| 4 | P1 (C10) | Silent OSError swallow | `locate.py:80` | Applied — stderr warning + new test |
| 5 | P1 (M11) | Jinja word-split | `make.md.j2:35` | Applied — single-quoted substitutions |
| 6 | P1 (M12) | Unicode digit bypass | `locate.py:128` | Applied — ASCII-only regex + 2 new tests |
| 7 | P1 (M17) | Single-IDE update message | `cli.py:219`, `cli.py:464` | Applied — multi-IDE message with marketplace |
| 8 | P1 (M18) | Non-actionable no-install | `cli.py:440`, `cli.py:208` | Applied — BOOTSTRAP.md pointer |
| 9 | P1 (M19) | Cursor BOOTSTRAP broken | `BOOTSTRAP.md:30` | Applied — explicit Cursor note + alternate path |
| 10 | P1 (M20) | Single-IDE recovery table | `BOOTSTRAP.md:112` | Applied — 3-IDE column |
| 11 | P2 (C7) | `make --require-version` uses cwd not target | `cli.py:205` | Applied — `target.resolve()` |
| 12 | P2 (M22) | Diff-block format | `BOOTSTRAP.md:194` | Applied — Before/After pairs |
| 13 | P2 (M24) | Hardcoded `exit 3` | `BOOTSTRAP.md:58` | Applied — `exit $?` |
| — | drift | Missing snapshot test | `tests/snapshot/test_cli_help.py` | Created — 3 assertions |
| — | gap | F9 tier-1 tiebreak test | `tests/unit/test_locate.py` | Added |
| — | dead code | `LocateEntry.plugin` field | `locate.py:17` | Removed |

**Phase D verification** (post-fixes):
- `uv run ruff check src/ tests/` → All checks passed!
- `uv run mypy src/harness_maker/` → Success: no issues found in 100 source files
- `uv run pytest tests/unit/ tests/snapshot/` → all green (full suite, including 36 new/updated locate tests)
- Snapshot regenerated (8 fixtures × 1 SHA per fixture — `make.md` only)

**Remaining: 0 consensus-passed** | **New issues introduced: 0**

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 4         | —   |
| 2         | **A** | 13 + drift fix + test additions | **0**     | 0   |

**Final grade: A**
**Iterations used: 2 / 3**
**Status: APPROVED**
**human_review_needed: false**

### What the user should still know

1. **Stash incident** during this review: a parallel `/hm:execute` (timestamp `0453Z`) ran while reviewers were producing findings. Its finalize tool stashed all execute-stage staging into `stash@{1}` (now popped) and overlaid a different feature's staging (help-skill templates). I detected this, paused before touching anything, stashed the help-skill work into `stash@{0}` for preservation, then popped the locate work back to continue Round 2. **The help-skill work is in `stash@{0}` — pop it with `git stash pop stash@{0}` when ready, or `git stash apply` to keep the stash entry.**

2. **6 manual-only findings deliberately NOT applied** (F8, F13, F14, F15, F21, F23) — all P2 or intentional trade-offs. See "NOT applied" table above for each rationale.

3. **Phase 5b (tag push + release workflow) is still deferred** — needs explicit user authorization per CLAUDE.md release procedure. Wrapup commits the staged changes; release is a separate authorized step.
