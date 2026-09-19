---
type: review
task_slug: observed-harness-gaps-salvage
status: APPROVED
created: 2026-09-19
reviewers_invoked: [code-reviewer (design+functionality+robustness+consistency), security-reviewer, concurrency-reviewer, test-reviewer, codex, code-verifier (mode B)]
consensus_method: cross-check
run_id: 9c64b0abbf20
review_base: 374a512549c2ff056619b4d589256a87204b00b6
drift_verdict:
  result: scope_violation
  scope_violations: [tests/render/test_render_roundtrip_collapse.py]
  scenario_misses: []
  task_slug: observed-harness-gaps-salvage
  computed_at: 2026-09-19T03:36:00Z
---

# REVIEW — observed-harness-gaps-salvage (2026-09-19)

## 🎯 Round 1 Summary

**Grade A** (`review_consensus finalize`: P0 0 · P1 0 · P2 4 consensus-passed · `errors: []`).
`human_review_needed: false` — no `manual-only` / `weak-consensus` finding at P0/P1. Lens
coverage: all 7 exercised, `blocks_approval: false`. Fixes pending: none (no P0/P1; P2 is not
auto-fix eligible at grade A — every P2 is dispositioned `accepted` and carried, below).

`review_base` resolved to `374a5125` rather than HEAD `555ca933`: the one commit between them
adds only two `.claude/observability/` telemetry rows, so the span is the task's diff plus two
non-code lines. Reviewers were given `git diff HEAD` (source/tests/docs; ratchet, snapshot and
golden files excluded from the prompt on purpose and covered by the suite).

## 🔍 Drift Findings

| Severity | File | Finding |
|---|---|---|
| P1 (drift) | `tests/render/test_render_roundtrip_collapse.py` | Not named in any PLAN phase scope. It is the wrapup git-tail **call-sequence** golden, which fired in Phase 6 and was re-based by adding `proposals summary` at the head, with attribution in its docstring and in the BASELINE-DELTA. Recorded in the PLAN's execution notes as the one gate outside the enumerated set. Scope drift by the letter; the change is the funded call asserted in position, as that test's docstring requires. |

No PLAN phase left unimplemented. Every SPEC scenario S1–S8 has coverage (A.5 round 2 PASS).

## ✅ Consensus Findings (`consensus-passed`)

All P2 — none lowers the grade. Each has one reviewer-lens voice (ADR-007: one lens votes alone).

| id | Sev | Lens | File | Finding | Disposition |
|---|---|---|---|---|---|
| `10f04873b3a00a58` | P2 | concurrency | `templates/stages/wrapup.md.j2:489` | The new `hm proposals summary` reader consumes `pending-proposals.md`, which Step 5.3 still writes with a raw, unlocked Edit/Write — unlike 5.1/5.2, moved to the locked `hm memory_md` CLI after 5 wiki entries were lost. Concurrent fleet wrapups can lose a proposal; the new warning then under-counts. **Pre-existing**, Step 5.3 is untouched and explicitly out of scope (ADR-004); Pass 2 downgraded it from P1 (advisory count, parser-tolerant). | accepted — carry; follow-up |
| `42e9355127940734` | P2 | tests | `tests/unit/test_memory_retrieve_count_floor.py:230` | `test_excerpt_keeps_multiple_whole_blocks_when_they_fit` uses a 47-byte body under a 4000-byte cap, so `_excerpt_recent_blocks` returns on its early exit and the whole-block selection loop it names is never entered. | accepted — carry |
| `d1fb99ca17b216f0` | P2 | tests | `tests/integration/test_memory_retrieve_cli.py:202` | `test_cli_no_count_floor_reproduces_the_pre_floor_output` only proves `--no-count-floor` == `--count-floor 0` (same `store_const` path); it does not pin pre-floor output as its name claims. (codex `cad4f352` is the same defect.) | accepted — carry |
| `aadf45beeb071e8b` | P2 | design | `templates/stages/execute.md.j2:79` | Warm-tier item 3 (unfiltered `wiki.md` head skim) now overlaps item 2, which this task switched to `hm memory_retrieve` — which already surfaces wiki bodies. Two wiki reads per execute run, no stated reason. | accepted — carry |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | File | Finding | Disposition |
|---|---|---|---|---|---|
| `60a1e75242fc9e10` | P2 | codex (PIDA accepted) | `src/harness_maker/memory_retrieve.py:329` | `--floor-entry-bytes 0` is accepted and `[-0:]` returns the whole body (budget ignored, or the entry silently dropped by the section cap); negatives slice wrongly. Reproduced: `_excerpt_recent_blocks('abcdef', 0) == ('abcdef', 0)`, `(…, -2) == ('cdef', 2)`; the CLI arg is a bare `type=int`. Real; a single cross-model voice is `manual-only` by rule. | accepted — carry |
| `cad4f352bbe7be7f` | P3 | codex (PIDA accepted) | `tests/integration/test_memory_retrieve_cli.py:202` | Same as `d1fb99ca`. | duplicate |
| `dccf472045a274ed` | P3 | codex (PIDA unresolved) | `PRIVACY.md:95` | "never `0`" is unconditional while the schema accepts a measured 0 (`ge=0`, and `test_null_is_distinct_from_zero` asserts it). Reads either as "do not substitute 0 for unmeasured" or as a contradiction; no `.md` oracle. The `unverified_severe` carve-out applies (and it is P3). | unresolved — no-contract |

## 🤝 Disagreements

- `10f04873` (Step 5.3 writer race): concurrency (owner) **kept at P2**; code-reviewer Pass 2
  **dropped** it as pre-existing and out of scope; security dropped it as not a security
  concern. The owning lens's verdict stands; the disagreement is about scope, not about whether
  the race is real — all three agree it is.
- `d1fb99ca` / `cad4f352` (pre-floor test name): tests lens P2, code-reviewer P3, codex P3.
  Kept as separate tiers (never bridged); the tests-lens P2 is the consensus record, codex's is
  a duplicate.

## 🧊 Cross-model findings (frozen @ round 1)

```yaml
frozen_at_round: 1
models: [codex]
findings:
  - id: 60a1e75242fc9e10
    source: codex
    severity: P2
    file: src/harness_maker/memory_retrieve.py
    line: 329
    summary: "--floor-entry-bytes 0 accepted; [-0:] returns the whole body; negatives slice wrongly"
    evidence: "_excerpt_recent_blocks('abcdef', 0) returns ('abcdef', 0)"
    needs_relaxation: false
    disposition: accepted
    oracle_result: "Repro: whole body at 0; 'cdef' at -2; --floor-entry-bytes has no positivity check"
    status: pending
    invalidation_reason: null
  - id: cad4f352bbe7be7f
    source: codex
    severity: P3
    file: tests/integration/test_memory_retrieve_cli.py
    line: 202
    summary: "pre-floor test only checks two disable flags agree"
    evidence: "both calls use the changed renderer; the only assertion is a.stdout == b.stdout"
    needs_relaxation: false
    disposition: accepted
    oracle_result: "No pre-floor baseline in the test; pytest pass does not refute a coverage claim"
    status: pending
    invalidation_reason: null
  - id: dccf472045a274ed
    source: codex
    severity: P3
    file: PRIVACY.md
    line: 95
    summary: "unconditional 'never 0' vs a schema that accepts a measured 0"
    evidence: "ReviewTelemetryRecord wall_time_ms Field(default=None, ge=0); test_null_is_distinct_from_zero"
    needs_relaxation: false
    disposition: unresolved
    oracle_result: null
    status: pending
    invalidation_reason: null
```

## ✔️ Confirmation Pass (confirm-1)

Frozen at `54e8a8b5` (`refs/hm-freeze/v1/observed-harness-gaps-salvage-confirm-1`, reaped after
the pass); span `374a5125..54e8a8b5` — the whole review. All 7 lenses dispatched as 4, coverage
`blocks_approval: false`. No fixes applied in the pass. Cross-model voters re-read from Section 7,
not re-invoked.

**New findings: 2, both P2 → zero new consensus-passed P0/P1 → APPROVED.**

| id | Sev | Lens | File | Finding | Disposition |
|---|---|---|---|---|---|
| `2f800768df27fe47` | P2 | tests | `tests/unit/test_render_wrapup_backlog_warning.py` | The "before the halt rule" ordering check anchors on `surface verbatim and halt`, which the new paragraph itself quotes ("the … rule below covers the commit and land calls only"), so it matches the paragraph's own sentence, not the section's real halt clause (≈:707). A paragraph moved below the real halt would still pass this assertion. The ordering is independently pinned by `test_render_roundtrip_collapse::test_the_wrapup_git_tail_is_the_expected_call_sequence` (`proposals summary` first), so AC-003 is covered — this assertion is weaker than its comment claims. | accepted — carry |
| `7edb61e2156a5294` | P2 | consistency | `src/harness_maker/proposals.py:104` | `_read` catches only not-found shapes and `main` has no top-level guard, so a non-UTF-8 or unreadable backlog raises a traceback and exits non-zero — unlike `memory_retrieve.main` in the same diff — and `test_wrapup_backlog_degrade.py`'s docstring ("no path that exits non-zero") is false for that input. The wrapup degrade contract does cover a non-zero exit, so the user-visible effect is one failure line, not a halt. | accepted — carry |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 7 P2 carried (4 consensus-passed + 1 manual-only codex + 2 confirm-1) · 2 P3 | — |
| confirm-1 | A     | —             | —         | 2 (P2) |

Final grade: A
Iterations used: 1 / 3
Exit reason: converged

## 📏 Size & Complexity

No repair round ran, so no 5c complexity rows were measured — nothing to report (not `0`).

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0

### Carried P2s — for a human sweep (not auto-fix eligible at grade A)

All seven are cheap and local; none changes a public contract:

1. `60a1e752` — reject non-positive `--floor-entry-bytes` (CLI) and guard `_excerpt_recent_blocks` for `max_bytes <= 0`, with boundary tests.
2. `7edb61e2` — broaden `proposals._read` to `OSError`/`UnicodeDecodeError` (or guard `main`), fix the degrade-test docstring, add a non-UTF-8 case.
3. `42e93551` — give `test_excerpt_keeps_multiple_whole_blocks_when_they_fit` a body over the cap so the loop runs.
4. `d1fb99ca` — rename the pre-floor test to what it checks (flag-alias equivalence), or add a real pre-feature golden.
5. `2f800768` — anchor the halt-ordering assertion after the call's paragraph (or on the real clause).
6. `aadf45be` — drop execute warm-tier item 3, or state why an unfiltered wiki read is still needed.
7. `10f04873` — pre-existing Step 5.3 unlocked writer: a follow-up PLAN (locked `hm memory_md` verb), not this diff.

Plus `dccf4720` (P3, unresolved): tighten "never `0`" to "do not substitute `0` for an unmeasured value" in `PRIVACY.md` / `review.md.j2`.

## Telemetry

Terminal row emitted to `.claude/observability/review-2026-09-19.jsonl` (base root) with
`--measured` finalize payload; `wall_time_ms` = 1 021 097, measured from the run's `opened_at`
(2026-09-19T03:32:36Z) — not estimated. Run `9c64b0abbf20` closed `APPROVED`.

## 🔧 Post-approval repair round (user-directed, 2026-09-19)

The review had approved at grade A. The user then chose to fix six of the seven carried P2s
plus the P3 now, and to file the seventh (`10f04873`, pre-existing Step 5.3 writer) as a
follow-up. This is **not** an auto-fix-loop round: `iteration_count` is unchanged and the run
(`9c64b0abbf20`) had already closed `APPROVED`.

| id | Fix | Verdict (re-review) |
|---|---|---|
| `60a1e752` | `_excerpt_recent_blocks` returns `("", total)` for `max_bytes <= 0` before any slicing; `--floor-entry-bytes` is a `_positive_int` argparse type (exit 2 on 0/negative); unit + CLI boundary tests | fixed |
| `7edb61e2` | `proposals.main` wraps `_run`; `OSError`/`UnicodeDecodeError` → one stderr line + exit 1 (not-found stays an empty backlog); degrade-test docstring corrected; non-UTF-8 test for `count` and `summary` | fixed |
| `42e93551` | excerpt test now binds the cap (3 × 900-byte blocks under 2000) with a precondition assert | fixed |
| `d1fb99ca` | renamed `test_cli_no_count_floor_flag_is_equivalent_to_count_floor_zero`, docstring states what it does not pin | fixed |
| `2f800768` | placement test anchors on the full clause "Any other non-zero exit: surface verbatim and halt" | fixed |
| `aadf45be` | execute warm-tier item 3 (wiki head skim) removed; item 2 states the fence carries wiki entries | fixed |
| `dccf4720` | "never `0` for an unmeasured round" (review.md.j2) / "never `0` in its place" (PRIVACY.md) | fixed |
| `10f04873` | filed as a pending proposal ("route wrapup Step 5.3's proposal writes through a locked memory CLI verb") | carried — follow-up |

- **Churn:** `r2-pre..r2-post` ratio **0.29** (21 files measured, 0 excluded). The churn gate
  (`review_consensus plan`, threshold 0.3) returned no dispatch — `churn 0.29 < 0.30`. A focused
  re-review ran anyway because the user's choice included one; one reviewer over the repair diff,
  all seven fixes judged **fixed**, **0 new findings**.
- **Ratchets moved by the repair:** execute −29 / review +25 chars (claude), aggregate
  436 659 → 436 655 / 371 722 → 371 718; `surface_baseline.json` re-frozen, snapshots
  regenerated, autopilot golden re-captured (only `execute`/`review` moved); BASELINE-DELTA
  updated in place.
- **Verification:** `ruff check .` clean · `ruff format --check .` clean · `mypy --strict src tests`
  clean · full `pytest` **rc=0 — 8806 passed, 97 skipped, 3 xfailed**.

Status stays **APPROVED**; `human_review_needed: false`.
