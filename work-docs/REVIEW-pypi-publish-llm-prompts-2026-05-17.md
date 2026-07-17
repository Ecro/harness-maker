---
type: review
task_slug: pypi-publish-llm-prompts
status: APPROVED
created: 2026-05-17
reviewers_invoked: [code-reviewer, security-reviewer, performance-reviewer, ux-reviewer]
consensus_method: cross-check
---

## 🎯 Round 2 Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 3 P1 consensus-passed | — |
| 2         | A     | 3 P1 + 5 P2 ancillary | 0 consensus-passed | 0 |

**Final grade:** A
**Iterations used:** 2 / 3
**Status:** APPROVED
**human_review_needed:** true (5 manual-only P1s require user judgment — see below)

## 🔍 Drift Findings

In-PLAN-scope (Phase 1–5): 11 files (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `tests/integration/test_package_artifacts.py`, `scripts/release_smoke.py`, `.github/workflows/release.yml`, `docs/release-checklist.md`, `README.md`). ✅

Out-of-PLAN-scope, user-authorized (`이것이 이번 변경과 무관하더라도 고쳐야 하는 이슈라면 같이 고쳐`):
- `tests/e2e/sandbox/` and `tests/e2e/sandbox-plugin-test/` — regenerated to add missing `commands/hm/health.md` (consolidation landed in 0.13.0 but sandbox snapshots were stale) and absorb post-0.13.0 schema additions (`schema_version`, `interview.deep_gate`, `interview.main_loop`). Fix unblocks `tests/e2e/test_dogfood_sandbox.py::test_commands_file_present[health]` which would have failed otherwise.

## ✅ Consensus Findings — Round 1 (all fixed in Round 2)

### P1: `_run(**kwargs: object)` defeats timeout type-check
**Reviewers:** code-reviewer + security-reviewer + performance-reviewer (3/4)
**File:** `scripts/release_smoke.py:32`
**Fix applied:** Keyword-only `timeout: float` (required) + explicit `cwd: str | None = None`. Removed `# type: ignore[call-overload]`. mypy --strict now enforces every call site supplies a timeout.

### P1: `uv build` subprocess inside unit test suite
**Reviewers:** code-reviewer + security-reviewer (2/4)
**File:** `tests/unit/test_package_artifacts.py:29` (was)
**Fix applied:** Moved to `tests/integration/test_package_artifacts.py`. Added `pytestmark = pytest.mark.skipif(not os.getenv("INTEGRATION") == "1", ...)` per the project's integration-test convention. Without `INTEGRATION=1`, the 12 tests are skipped — unit suite stays fast and offline. Verified: skip path 0.03s, INTEGRATION=1 path 0.27s passing.

### P1: PowerShell `(Get-Location)` unquoted — breaks paths with spaces
**Reviewers:** code-reviewer + ux-reviewer (2/4)
**File:** `README.md:103, 119`
**Fix applied:** Replaced bare `(Get-Location)` with `"$((Get-Location).Path)"` in both PowerShell variants. `.Path` returns a string and the outer quotes preserve spaces in paths like `C:\Users\John Smith\project`.

## 📝 Manual-Only Findings — Round 1 (do not affect grade; need user judgment)

These are real defects/concerns but single-source, so the consensus filter recorded them as `manual-only`. Several were also fixed in Round 2 as low-risk cleanups; the remainder require explicit user choice.

### Fixed in Round 2 (cheap + uncontroversial)

| Source | File:Line | Finding | Fix |
|--------|-----------|---------|-----|
| security P1 | `release.yml:73, 124` | TestPyPI publish reachable from branch via `workflow_dispatch dry_run=false` | Tightened `if:` to `startsWith(github.ref, 'refs/tags/v')` only. `workflow_dispatch` is now build/test-only regardless of `dry_run` input (matching PLAN intent). Input description updated. |
| security P2 | `release.yml:79, 92` | `quality-gate` and `build` jobs lacked explicit `permissions:` | Added `permissions: contents: read` (defense-in-depth). |
| security P2 | `release_smoke.py:155` | `except Exception` swallowed unexpected errors | Narrowed to `TimeoutExpired` + `(RuntimeError, OSError)`. Surfaces unexpected exceptions with stack trace. |
| performance P2 | `release.yml:107` | TestPyPI smoke install no step timeout | Added `timeout-minutes: 5` to the smoke install step. |
| code P2 | `release.yml:63` | `uv build` no explicit `--out-dir` | Added `--out-dir dist/` for self-documentation. |
| performance P1 | `test_package_artifacts.py:29` | Module-scoped build fixture | Promoted to `scope="session"`. |
| ux P1 | `README.md:88` | WSL detection case-sensitive `"microsoft"` | Now `"microsoft" or "Microsoft" (case-insensitive)`. |
| ux P1 | `README.md:83` | "preferred language" had no fallback rule | Added explicit "detect from first reply; default to English if you cannot tell." |
| ux P2 | `README.md:86` | `uname` succeeding with unknown value not handled | OS rule now covers "value outside {Linux/Darwin/CYGWIN*/MINGW*} → native Windows". |
| code P2 | `test_package_artifacts.py:13` | sdist needle comment unclear about prefix | Clarified docstring: wheel prefix vs sdist `harness_maker-<X.Y.Z>/src/...` prefix documented. |

### Remaining — user judgment required

1. **security P1: unpinned third-party action SHAs** (`release.yml:80-94, …`)
   - `astral-sh/setup-uv@v5`, `actions/checkout@v4`, `actions/upload-artifact@v4`, `actions/download-artifact@v4` are mutable tags.
   - In jobs holding `id-token: write` (publish-testpypi, publish-pypi) a compromised action could mint an OIDC token under the Trusted Publisher subject.
   - **Why not auto-fixed:** Pinning to full SHAs is a meaningful churn; teams typically defer until pre-launch hardening. Optionally use Dependabot to manage pin updates.
   - **Recommendation:** Pin before the first real `v*` tag is pushed (acceptable while infrastructure-only; risk is theoretical until the workflow actually runs against PyPI).

2. **security P1: personal email in PyPI metadata** (`pyproject.toml:9`)
   - `authors = [{ name = "Ecro", email = "e839638@gmail.com" }]` — once published the email is permanently in PyPI METADATA + sdist PKG-INFO and indexed by mirrors.
   - **Why not auto-fixed:** It's a deliberate maintainer choice. PEP 621 allows name-only authors.
   - **Recommendation:** If the address is intentional → keep. If not → drop the `email = "..."` field. Address can be added later but cannot be retracted from a published release.

3. **security P2: LLM bootstrap prompt directs autonomous `curl … | sh` / `irm … | iex`** (`README.md:88-91`)
   - This is the standard `uv` install pattern — astral.sh is a controlled vendor — but the README instructs the LLM to execute these autonomously.
   - **Why not auto-fixed:** ADR-006 explicitly chose LLM-autonomous detection. Adding a "ask the user before installing uv" step contradicts the design.
   - **Recommendation:** Accept as the documented design choice; mention in `docs/release-checklist.md` Phase 4 as an audit point.

4. **code P2: `Python :: 3.13` classifier without CI matrix** (`pyproject.toml:36`)
   - `requires-python = ">=3.12"` allows 3.13, but CI installs 3.12 only.
   - **Why not auto-fixed:** Adding a 3.13 matrix is a CI expansion; removing the classifier is a marketing statement change.
   - **Recommendation:** Either add 3.13 to the CI matrix (`uv python install 3.12 3.13`) or drop the 3.13 classifier before the first PyPI tag.

## 🤝 Disagreements

None. All consensus-passed findings had agreed severity (P1).

## Telemetry

```json
{"slug": "pypi-publish-llm-prompts", "round": 1, "pass1_n": 28, "pass2_kept_n": 28, "consensus_passed_n": 3, "build_break_count": 0, "auto_fix_reverted_n": 0, "fallback": null}
{"slug": "pypi-publish-llm-prompts", "round": 2, "pass1_n": 8, "pass2_kept_n": 8, "consensus_passed_n": 0, "build_break_count": 0, "auto_fix_reverted_n": 0, "fallback": null}
```

## Notes for /hm:wrapup

- Final grade A; status APPROVED. Proceed to wrapup.
- `human_review_needed = true` because 4 manual-only items remain (action pinning, email, prompt-execution design, 3.13 classifier) — list in wrapup commit body so the user sees them again before pushing a v-tag.
- Pre-flight reminder: Phase 0 (PyPI/TestPyPI project + Trusted Publisher registration) has already been completed by the user per the session record.
- The infrastructure lands now but the actual publish only fires when a `v*` tag is pushed — likely after in-progress 0.14.0 work merges. The release.yml is dormant until then.
