---
type: review
task_slug: test-fidelity-gap
status: APPROVED
created: 2026-05-19
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: test-fidelity-gap
  computed_at: "2026-05-19T20:50:00+00:00"
---

# REVIEW — Test Fidelity Gap (Layer 1)

## 🎯 Round 1 Summary

- **Reviewers invoked**: `code-reviewer`, `security-reviewer` (conditional routing — Python test code + GitHub Actions workflow + docs).
- **2-pass redaction skipped**: the diff under review is uncommitted staged content with no PR title / description / author metadata. The Phase 0 ablation's anchoring concern (+47pp precision) is moot when there is no anchoring metadata. Pass 1.5 verifier also skipped (no anchor to verify against).
- **Findings**: 7 total (3 from code-reviewer, 4 from security-reviewer). 1 consensus-passed P1, 1 dropped as false positive, 5 manual-only.
- **Grade (Round 1)**: B (P0=0, consensus-passed P1=1).

## 🔍 Drift Findings

`drift_verdict.result: clean`. The staged diff is a strict subset of PLAN Phase 0-4 scope (boundary tests + helpers + conftest marker + release.yml advisory job + CLAUDE.md release-procedure paragraph + CHANGELOG entry). No files modified outside PLAN scope. PLAN frontmatter has no `common_ground_marks` array — Step 2.5 silent-intent-miss hook does not fire for this task.

## ✅ Consensus Findings

### CP1 — release.yml: `$?` after `tee` captures tee's exit code, not pytest's [P1] [2/2 consensus]

**File**: `.github/workflows/release.yml` line 230-231 (pre-fix).
**Reviewers**: code-reviewer + security-reviewer (independent surface match; identical reasoning chain).

**OBSERVE**: `uv run pytest ... 2>&1 | tee /tmp/boundary.txt` followed by `echo "exit_code=$?" >> "$GITHUB_OUTPUT"`. `set +e` precedes the pipeline.
**INFER**: In bash without `pipefail`, `$?` after a pipeline reflects only the rightmost command (tee). tee exits 0 on any successful disk write regardless of pytest's outcome. Without `${PIPESTATUS[0]}`, a real boundary failure is captured as exit_code=0.
**CONCLUDE**: The advisory mechanism is structurally broken — the FAIL branch of the status label is unreachable. Every release would report PASS, even on genuine regressions. This defeats ADR-004's entire purpose.

**Fix applied (Round 2)**: `echo "exit_code=${PIPESTATUS[0]}" >> "$GITHUB_OUTPUT"`. Verified via YAML lint + boundary suite re-run (49/49 pass).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### M1 — release.yml: `gh release view` failure silently overwrites Release notes [P1] [single: security-reviewer]

**File**: `.github/workflows/release.yml` line 247 (pre-fix).

**OBSERVE**: `gh release view "$TAG" --json body -q .body > "$NEW_NOTES"` with no error guard. If the command fails, `$NEW_NOTES` is empty. The subsequent `gh release edit "$TAG" --notes-file "$NEW_NOTES"` would then replace the Release body with only the advisory section appended to an empty file.
**INFER**: A partial-failure of the `github-release` job, a transient `gh` API outage, or any auth slip would cascade into Release-notes data loss — the CHANGELOG-derived notes would be permanently overwritten with advisory boilerplate alone.
**CONCLUDE**: Catastrophic blast radius for a low-probability fault. The fix is a one-line guard.

**Fix applied (Round 2)**: `set -euo pipefail` at top of step; `if ! gh release view ... ; then echo WARNING ...; exit 0; fi` guard. On fetch failure the advisory is skipped (notes preserved); operator can append manually.

### M2 — release.yml: ANSI codes from `pytest -v` corrupt markdown in Release body [P2] [single: security-reviewer]

**File**: `.github/workflows/release.yml` line 245 (pre-fix).

**OBSERVE**: `tail -30 /tmp/boundary.txt` embeds raw pytest output verbatim inside a fenced block. `pytest -v` may emit ANSI color escapes even when stdout is redirected on some runners.
**INFER**: ANSI sequences render as garbage in the GitHub Release UI (no terminal interpretation). The fenced block prevents markdown injection, but the body becomes unreadable.
**CONCLUDE**: Cosmetic; no security or correctness impact. Cheap to fix.

**Fix applied (Round 2)**: `sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g'` strips CSI sequences from the tail.

### M3 — release.yml: `boundary-advisory` permissions lack explicit `id-token: none` [P2] [single: security-reviewer]

**File**: `.github/workflows/release.yml` line 211 (pre-fix).

**OBSERVE**: `permissions:` declares only `contents: write`. `id-token` is implicit (default-deny).
**INFER**: Implicit denial is the GitHub Actions default and is functionally correct. Adding `id-token: none` is defense-in-depth — making the OIDC non-issuance auditable and resilient to a future global-default change.
**CONCLUDE**: Defense-in-depth; no current risk. Trivial to add.

**Fix applied (Round 2)**: `id-token: none` added with rationale comment.

### M4 — test_boundary_harness_yaml.py: function name "rejects" contradicts body asserting acceptance [P2] [single: code-reviewer]

**File**: `tests/integration/test_boundary_harness_yaml.py` line 104 (pre-fix).

**OBSERVE**: `test_canonical_helper_rejects_single_doc_lacking_provenance` body asserts `body == {...}` — a successful load, not a rejection.
**INFER**: Misnomer. The test correctly verifies an inverse-of-negative ("the parser DOES accept this legacy shape"). The marker `@pytest.mark.boundary_negative` is intentional per PLAN convention (the marker tags consumer-parser-boundary tests on synthetic bytes regardless of pass/raise outcome, e.g. `test_codex_hooks_accepts_permission_request` follows the same pattern).
**CONCLUDE**: Rename only; marker stays per convention.

**Fix applied (Round 2)**: renamed to `test_canonical_helper_accepts_single_doc_lacking_provenance`; docstring updated.

### M5 — test_boundary_meta.py: regex assumes nonexistent pytest `--collect-only -q` output format [P1, single: code-reviewer] — **DROPPED as false positive**

**Reviewer claim**: line 87 regex `<filename>:\s*(\d+)` expects `path: count` lines that pytest 9.x doesn't emit; all 5 parametrize cases would fail unconditionally.

**Verification**: my Phase 4 GREEN gate (recorded earlier in execute) showed `7 passed in 7.74s` for `test_boundary_meta.py` — all 5 `test_meta_module_has_boundary_negative[*]` parametrize cases passed. The regex DOES match — pytest 9.0.3 with `-q --collect-only` against a single file path emits `path/to/file.py: N` summary lines. Concrete evidence: an earlier failed-test output (Phase 4 debug) showed literal `tests/integration/test_boundary_settings_json.py: 5` in stdout.

**Conclusion**: Reviewer hallucinated pytest's output format. Drop. (Pass 2 redaction would have caught this had it been run — left as a note that contextual verification matters even when no anchoring metadata is present.)

## 🤝 Disagreements

None substantive. The two reviewers independently identified CP1 with identical reasoning; no severity disagreement.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 P1 (consensus) + 1 P1 (manual) + 3 P2 (manual) — 1 P1 dropped FP | — |
| 2 (auto-fix) | A | 5 (1 consensus + 4 manual) | 0 | 0 |

**Round 2 fixes**:

| # | Severity | Source | Summary | File:Line | Status |
|---|----------|--------|---------|-----------|--------|
| 1 | P1 | consensus | `tee` exit-code → `${PIPESTATUS[0]}` | release.yml:230-231 | Applied |
| 2 | P1 | manual-only | `gh release view` failure guard | release.yml:247 | Applied |
| 3 | P2 | manual-only | strip ANSI from pytest output | release.yml:245 | Applied |
| 4 | P2 | manual-only | explicit `id-token: none` | release.yml:212 | Applied |
| 5 | P2 | manual-only | rename `rejects` → `accepts` | test_boundary_harness_yaml.py:104 | Applied |

**Build verification after Round 2**:

- `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v` → **49/49 passed in 7.20s**.
- `uv run ruff check tests/integration/` → **All checks passed!**
- `uv run python -c "import yaml; ..."` → `release.yml` parses; `boundary-advisory` permissions: `{contents: write, id-token: none}`.
- No new findings introduced.

Final grade: **A** (consensus-passed P0=0, P1=0).
Iterations used: 2 / 3.
Status: **APPROVED**.
`human_review_needed`: false.

## Telemetry

```json
{"ts": "2026-05-19T20:50:00+00:00", "slug": "test-fidelity-gap", "round": 1, "pass1_n": 7, "verifier_kept_n": 0, "verifier_dropped_n": 0, "verifier_false_drop_n": null, "verifier_false_keep_n": null, "fixture_label": null, "pass2_kept_n": 7, "consensus_passed_n": 1, "wall_time_ms": 332000, "build_break_count": 0, "auto_fix_reverted_n": 0, "fallback": "pass1.5_verifier_skipped+pass2_redaction_skipped (no anchoring metadata on uncommitted staged diff)"}
{"ts": "2026-05-19T20:55:00+00:00", "slug": "test-fidelity-gap", "round": 2, "pass1_n": 0, "verifier_kept_n": 0, "verifier_dropped_n": 0, "verifier_false_drop_n": null, "verifier_false_keep_n": null, "fixture_label": null, "pass2_kept_n": 0, "consensus_passed_n": 0, "wall_time_ms": 8000, "build_break_count": 0, "auto_fix_reverted_n": 0, "fallback": "re-review_skipped (build verification + diff inspection + no new logic)"}
```
