---
type: review
task_slug: install-without-claude-code
status: APPROVED
created: 2026-05-12
reviewers_invoked: [code-reviewer, security-reviewer, performance-reviewer]
consensus_method: cross-check
---

# Review: install-without-claude-code

## Round 1 Summary — Grade: B

Initial grade **B** (0 P0, 1 P1 consensus-passed). Threshold: A.

### Drift Findings

None. All changes fall within PLAN phases 1–5.

### Consensus Findings (consensus-passed)

| # | Sev | File | Summary | Fix |
|---|-----|------|---------|-----|
| F1 | P1 | `synthesize.py:46-58` | After `distribution()` succeeds, a JSON parse error in `direct_url.json` fell through the broad `except Exception` to `_HARNESS_MAKER_PKG_ROOT`. On a wheel install, that resolves to `site-packages` parents — an invalid `--with` ref. | Split `try/except` into two blocks: outer for `distribution()` not-found (→ local path), inner for JSON errors (→ `"harness-maker"`). |
| F2 | P2 | `synthesize.py` + `workflow_fuse.py` (5 sites) | `_compute_install_ref()` called redundantly in loops (7× in `_atomic_command_files`, 7× in `_codex_stage_skills`, N× in `fuse()`, N× in FileEntry comprehension). Each call hits `importlib.metadata.distribution()` + `read_text()`. | Hoisted `install_ref = _compute_install_ref()` once per function, passed as local var to loop bodies. |

### Manual-Only Findings

| # | Sev | Source | Summary | Disposition |
|---|-----|--------|---------|-------------|
| M1 | P1 | code-reviewer | Editable installs without `direct_url.json` return `"harness-maker"` (wrong) | Accepted risk: PEP 610 requires `direct_url.json` for all non-registry installs. Legacy editable installs without it are increasingly rare with modern pip/uv. ADR-002 detection rule is locked to `direct_url.json`. |
| M2 | P2 | code-reviewer | `test_codex_stage_procedures` helpers still use `_HARNESS_MAKER_PKG_ROOT` | Pre-existing — those test helpers render with known paths for deterministic assertions. Not a regression from this change. |
| M3 | P2 | code-reviewer | Unused `monkeypatch` fixture params | Fixed in auto-fix round. |
| M4 | P2 | security-reviewer | `curl \| sh` in README conflicts with project's no-pipe-shell policy for executor agents | Acknowledged. The `curl \| sh` is Astral's official uv installer and appears in user-facing documentation (not in agent-executed hooks). The policy applies to executor agent commands, not README instructions. Added as a documentation note. |
| M5 | P2 | security-reviewer | `installed_plugins.json` installPath trusted without fingerprint | Same-user local file trust. Hardening deferred — not a regression. |
| M6 | P3 | security-reviewer | Empty `$HOME` edge case in Cursor path | Fails closed (directory check fails, falls through to CLI_FALLBACK). No action needed. |

## Iteration 2 (Grade: B → A)

Fixes applied: 3

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Split try/except to narrow JSON error handling | synthesize.py | Applied |
| 2 | P2 | Hoist _compute_install_ref() in 4 functions | synthesize.py + workflow_fuse.py | Applied |
| 3 | P2 | Remove unused monkeypatch params | test_install_ref.py | Applied |

New test added: `test_returns_package_name_when_direct_url_json_corrupted` — verifies that corrupted `direct_url.json` returns `"harness-maker"` (not local path).

Remaining: 0 consensus-passed | New issues introduced: 0

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 2         | —   |
| 2         | A     | 3             | 0         | 0   |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false
