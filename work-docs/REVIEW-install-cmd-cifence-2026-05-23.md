---
type: review
task_slug: install-cmd-cifence
status: APPROVED
created: 2026-05-23
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scope_expansions:
    - file: tests/unit/test_readme_one_prompt_structure.py
      reason: phantom test from pre-truthification era; would block Phase D unit suite. PLAN scope OUT was specified before the conflicting test was discovered.
    - file: uv.lock
      reason: auto-updated from pyproject.toml version bump (0.23.4 → 0.23.5). Mechanical.
  scenario_misses: []
  task_slug: install-cmd-cifence
  computed_at: 2026-05-23T15:30:00Z
---

# REVIEW — install-cmd-cifence (ADR-001 Q4 trigger fire)

## 🎯 Round 1 Summary

| Metric | Value |
|---|---|
| Grade | **A** |
| Threshold | A |
| Consensus-passed P0/P1 | 0 / 0 |
| Manual-only findings | 10 (3 security P1 + 2 security P2 + 5 code P2) |
| Fixes applied this round | 9 manual orchestrator fixes (one P2 deferred — UV_TOOL_DIR isolation runtime assertion) |
| Status | **APPROVED** |
| human_review_needed | false |

Single reviewer of each type → all findings are `manual-only` by definition.
Per consensus rubric, no consensus-passed P0/P1 → Grade A. But security
reviewer's 3 P1 findings are real exploits (npm supply-chain, copytree
symlink traversal, masked install failure) and were applied as orchestrator
manual fixes before wrapup (same pattern as
`REVIEW-codex-compat-fixes-2026-05-22` and
`REVIEW-readme-codex-truthification-2026-05-22`).

## 🔍 Drift Findings

Two documented scope expansions, both justified — see frontmatter
`drift_verdict.scope_expansions`. No surprise edits.

## ✅ Consensus Findings

None (single reviewer of each type).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (9 applied + 1 deferred)

### security-reviewer (3 P1 + 2 P2)

**P1-1 — `.github/workflows/ci.yml:85` — Unpinned `npm install -g @openai/codex` (supply chain)**
- OBSERVE: `npm install -g @openai/codex` runs on every PR build with no version constraint.
- INFER: A compromised future version of `@openai/codex` would execute arbitrary `postinstall` scripts on the CI runner; PR forks can trigger this.
- CONCLUDE: Classic unpinned-npm supply-chain vector.
- **Applied fix**: Pinned to `@openai/codex@0.133.0` (version exercised at execute time).

**P1-2 — `.github/workflows/ci.yml:86` — `continue-on-error: true` on npm install masks compromised-install signal**
- OBSERVE: The npm install step had `continue-on-error: true`.
- INFER: A failed install (network issue OR a compromised package's failing postinstall) appears as green in CI, hiding the signal.
- CONCLUDE: The graceful-degradation rationale doesn't justify masking install failures — the test code's `shutil.which("codex")` skip-guard already handles the "codex absent" case.
- **Applied fix**: Removed `continue-on-error: true` from the npm install step. Kept it on the actual advisory test step (where the rationale stands — the test ITSELF being advisory is the ADR-002 contract).

**P1-3 — `tests/integration/_install_helpers.py:127` — `shutil.copytree` follows symlinks by default (arbitrary file read)**
- OBSERVE: `shutil.copytree(src=repo_root, dst=target_dir, ...)` with no `symlinks` arg.
- INFER: Default `symlinks=False` means copytree calls `shutil.copy2` on each symlink, resolving and copying the TARGET. A PR adding a symlink anywhere in the repo tree (e.g., `src/secrets -> /etc/shadow`) would cause this test to read arbitrary host files into `tmp_path`.
- CONCLUDE: Exploitable from a single-file PR contribution.
- **Applied fix**: Added `symlinks=True` to the copytree call; updated docstring to explain the safety property.

**P2 — Allowlist bypass via single PR (no CODEOWNERS)**
- OBSERVE: `EXPECTED_README_INSTALL_COMMANDS` is in a file an attacker can edit in the same PR that adds a new README command.
- INFER: The allowlist gate has no enforcement beyond the test itself.
- CONCLUDE: Documentation-grade defense, not security-grade.
- **Applied fix**: Created `.github/CODEOWNERS` requiring `@Ecro` review for `README.md`, `README.ko.md`, `_install_helpers.py`, `test_readme_install_commands.py`, `ci.yml`, and `CODEOWNERS` itself. Branch protection must enforce CODEOWNERS (separate manual step the user owns).

**P2 — `UV_TOOL_DIR` isolation not runtime-verified — DEFERRED**
- OBSERVE: Helper sets `UV_TOOL_DIR` + `UV_TOOL_BIN_DIR`; assumes uv honors them.
- INFER: If uv silently ignored them, the dev's real `~/.local/share/uv/tools/` would be polluted.
- CONCLUDE: Real risk on developer machines, lower risk in CI tmp dirs.
- **Deferred** — uv's documented behavior is to honor these env vars; adding a runtime assertion is reasonable but lower-priority than the 3 P1 fixes. Tracked here for follow-up.

### code-reviewer (5 P2)

**P2-1 — `test_readme_install_commands.py:69` — `_repo_root` iterates `here` (file) before `here.parent`**
- OBSERVE: `for parent in (here, *here.parents)` starts at the .py file itself.
- INFER: First iteration checks `file.py/pyproject.toml`, an impossible path. Walk is functionally correct but semantically wrong.
- CONCLUDE: Misleading semantics, no current bug.
- **Applied fix**: Changed loop to start from `here.parents` (skip the file itself).

**P2-2 — `test_readme_install_commands.py:109` — `"make" in result.stdout` too broad**
- OBSERVE: Substring match on entire `--help` output.
- INFER: Future help text containing "make" in prose would false-positive even if the `make` subcommand was renamed.
- CONCLUDE: Latent regression-detection weakness.
- **Applied fix**: Replaced with `re.search(r"(?m)^\s*[│|]?\s*make\b", result.stdout)` — anchored to Typer's command-list line shape.

**P2-3 — `_install_helpers.py:149` — Comment falsely claims "negative lookbehind"**
- OBSERVE: Regex has no lookbehind; protection is structural.
- INFER: Future maintainers reading the comment would look for a non-existent lookbehind.
- CONCLUDE: Misleading documentation.
- **Applied fix**: Rewrote comment to explain the actual structural protection.

**P2-4 — `test_readme_one_prompt_structure.py:127` — `Bash:?` overly permissive**
- OBSERVE: Optional colon matches `Bash word` (single-space prose).
- INFER: Inconsistent with peer branch tests (`test_claude_code_branch_uses_bash_install` uses `Bash:` strict). Future README prose like `Bash run-something` would pollute `bash_lines`.
- CONCLUDE: Latent false-positive risk in the new Invariant 4.
- **Applied fix**: Tightened to `r"^\s*Bash(?::| {2,})"` — colon OR 2+ spaces (matches `_install_helpers.py` extractor).

**P2-5 — `test_readme_one_prompt_structure.py:103` — Scope drift (existing test modified vs PLAN Phase 4 Scope OUT)**
- OBSERVE: PLAN explicitly says "Scope OUT: Modifying existing test files".
- INFER: The modification was necessary (the old test enforced the now-removed `codex plugin marketplace add` behavior; without the update, Phase D unit suite would fail).
- CONCLUDE: Justified scope expansion, but PLAN's rollback section doesn't cover it.
- **Documented** in this REVIEW's `drift_verdict.scope_expansions` and in the wrapup commit body. No code fix needed — the test modification IS the right action; the meta-issue is paper-trail completeness, which this REVIEW provides.

## 🤝 Disagreements

None — code-reviewer and security-reviewer touched disjoint surfaces.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 9 manual orchestrator | 1 (deferred P2) | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false
