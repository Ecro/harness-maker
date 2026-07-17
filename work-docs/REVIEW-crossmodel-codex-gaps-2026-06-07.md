---
type: review
task_slug: crossmodel-codex-gaps
status: APPROVED
created: 2026-06-07
reviewers_invoked: [code-reviewer, security-reviewer, performance-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: crossmodel-codex-gaps
  computed_at: 2026-06-07T00:00:00Z
---

# REVIEW — crossmodel-codex-gaps (2026-06-07)

Reviewed the uncommitted P1–P6 diff (19 files, ~842 insertions). 3 reviewers
(code / security / performance) ran on the changed files. Each reviewer is the sole
holder of its scope, so findings are tagged `consensus-passed-by-scope` (arbiter Step
4a-bis) — authoritative single-source. Security P1s were auto-fixed by orchestrator
decision (a real shell-injection class warrants it despite `auto_fix_scoped` default-off).

## 🎯 Round 1 Summary

- **Initial grade: D** — 2 scope-exempt **P1** (shell injection) drove the grade gate
  into the auto-fix loop. Treated as grade-relevant rather than hidden behind the
  single-source `manual-only` technicality.
- Drift: **clean** (every changed file maps to a PLAN phase scope).

## 🔍 Drift Findings

None. P1→P6 file set matches PLAN phase scopes (ledger/schema/health→P1; high_diff→P2;
second_opinion partial→P3+P5; codex_adapter→P4a; review.md.j2 + consensus-arbiter→P4b;
CLAUDE.md→P6; tests→respective). `test_render_codex_partial_include.py` modification is
the documented ADR-002 superseded-invariant update.

## ✅ Consensus Findings (consensus-passed-by-scope)

### P1 — fixed this round
1. **Shell injection — `review.md.j2:273` skip-relay echo** (security-reviewer).
   `echo '{...,"skip_reason":"<cause>"}' | codex_ledger emit` inlined attacker-influenceable
   text into a single-quoted shell literal. **Fixed:** added an arg-based `emit`
   (`--slug/--stage/--finding-ref/--disposition/--codex-status/--skip-reason`) so JSON is
   built in Python from separate argv; recipe now passes `--skip-reason "$reason"`.
2. **Shell injection — `second_opinion_codex.md.j2:145` skip-receipt echo** (security-reviewer).
   Same vector. **Fixed:** same arg-based recipe + explicit "never inline untrusted text" note.

### P2 — fixed this round
3. **Predictable `/tmp/hm-codex-smoke.json` sink — `health.md.j2`** (security-reviewer):
   symlink-clobber TOCTOU. **Fixed:** `out_tmp=$(mktemp)`.
4. **Fixed `/tmp/hm-codex-review.json` + inline diff in double-quoted printf — `review.md.j2:260`**
   (security-reviewer): `$(...)` in adversarial diff would expand. **Fixed:** diff into a
   `content` shell var first, `printf '%s' "$content"` to a `mktemp` prompt file, `mktemp`
   output sink.

### P2 — accepted with rationale (not fixed)
5. **Atomic-append retry loop — `codex_ledger.py:69`** (performance-reviewer): the
   partial-write retry can theoretically interleave concurrent writers, weakening the
   per-`write(2)` O_APPEND atomicity. **Accepted:** the function is copied verbatim from
   the already-audited `review_telemetry.py`; diverging one module is inconsistent, and a
   repo-wide fix is out of this PLAN's scope. Recorded for a future telemetry-hardening PLAN.
6. **PIPE_BUF guard vs summed `max_length` — `codex_ledger.py:59`** (performance-reviewer):
   worst-case multibyte rows could exceed 4096 and raise. **Accepted:** real ledger rows are
   tiny (<120 chars); the guard is a safety rail, not a hot constraint. Same pattern as
   `review_telemetry`.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only / P3

- `high_diff.py:124` — `client: object | None` + `type: ignore` (code-reviewer). **Fixed:**
  typed as `JudgeClient | None` (TYPE_CHECKING import), dropped the ignore.
- `test_codex_mandatory_matrix.py` byte-zero asserts used `.strip()` (code-reviewer). **Fixed:**
  tightened to `== ""` so a whitespace-control regression is actually caught.
- `high_diff.py:26` over-broad security/contract substrings (code-reviewer). **Accepted:**
  fail-safe direction — over-match only causes extra Codex calls, never a missed high-diff.
  Documented as intentional.

## 🤝 Disagreements

None — reviewers covered disjoint scopes; no severity conflicts.

## Iteration 1 (Grade: D → A)
Fixes applied: 6 (2×P1, 2×P2, 2×P3); accepted: 3 (2×P2, 1×P3)

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | shell injection (skip relay) | review.md.j2 | Fixed (arg-based emit) |
| 2 | P1 | shell injection (skip receipt) | second_opinion_codex.md.j2 | Fixed (arg-based emit) |
| 3 | P2 | predictable /tmp sink | health.md.j2 | Fixed (mktemp) |
| 4 | P2 | /tmp sink + inline diff expansion | review.md.j2 | Fixed (mktemp + $content) |
| 5 | P2 | atomic-append retry loop | codex_ledger.py | Accepted (mirrors review_telemetry) |
| 6 | P2 | PIPE_BUF vs max_length | codex_ledger.py | Accepted (rows tiny) |
| 7 | P3 | object-typed LLM client | high_diff.py | Fixed (JudgeClient) |
| 8 | P3 | loose byte-zero assert | test_codex_mandatory_matrix.py | Fixed (== "") |
| 9 | P3 | over-broad substrings | high_diff.py | Accepted (fail-safe) |

Remaining (grade-relevant): 0 | New issues introduced: 0

## 🧊 Round 3 — Deeper cold-eyed pass (prose↔module wiring)

Round 1 reviewed modules in isolation; this pass audited the **seam between rendered
prose and the Python modules** and found 4 real defects Round 1 missed:

- **A (P2) — `git diff --name-only` misses staged changes.** Post-execute the diff is
  staged, so the bare command returns nothing (verified: 9 vs `HEAD` 13 in this tree) →
  Side high-diff gate under-counts → Codex under-triggers. **Fixed:** `git diff … HEAD`
  in both `review.md.j2` and the partial.
- **B (P2) — no `--added-lines` → `boundary` never fires.** The prose piped filenames only,
  so `high_diff.classify` could never set `boundary=True`; the LLM-boundary path +
  `judge_boundary_llm` + the INTEGRATION accuracy-floor test (the whole W4/ADR-003 boundary
  half) were **unreachable in the real flow**. **Fixed:** prose now computes `--numstat HEAD`
  added-line sum and passes `--added-lines`.
- **C (P3) — `codex_adapter` had no runtime caller.** review.md.j2 only *referenced* it as a
  prose "contract"; the validator's pass-2-critical deterministic severity-map was still
  LLM-applied. **Fixed:** added `codex_adapter adapt` CLI (reads the codex output file →
  emits the adapted list, keeping untrusted content out of the shell); review prose now
  actually invokes it. Determinism is now real, not theater.
- **D (P3) — `codex-ledger.schema.json` has no consumer.** Rendered into every harness's
  `.claude/schemas/` but nothing reads it (ledger is pydantic-written; smoke uses
  codex-finding schema). **Accepted (documented):** retained as a model↔schema consistency
  anchor (`test_json_schema_matches_model_fields`), not claimed load-bearing. Candidate for
  removal in a future cleanup PLAN.

### Iteration 2 (Round 3 fixes; Grade: A → A)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| A | P2 | staged-diff miss (`HEAD`) | review.md.j2, second_opinion_codex.md.j2 | Fixed |
| B | P2 | no added-lines → boundary dead | review.md.j2, second_opinion_codex.md.j2 | Fixed |
| C | P3 | adapter never invoked | codex_adapter.py (+CLI), review.md.j2 | Fixed |
| D | P3 | ledger schema no consumer | codex-ledger.schema.json | Accepted (documented) |

Remaining (grade-relevant): 0 | New issues introduced: 0

> Honest note: A and B are the consequential ones — without them the high-diff gate the
> user explicitly designed ("Side high-diff 일 때만") was effectively inert (under-triggering
> on staged diffs, boundary never reachable). The first review's grade-A was correct on the
> modules but blind to the wiring. This is exactly why the second cold-eyed pass was asked for.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 2 P1      | —   |
| 2         | A     | 6             | 0         | 0   |
| 3 (deeper)| A     | 3 (+1 accepted) | 0       | 0   |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false

Verification after fixes: full `pytest` + `ruff` + `mypy --strict` re-run (see Telemetry).
Reviewer agents stayed read-only; the stage orchestrator applied all fixes via Edit. No `git commit` from this stage.
