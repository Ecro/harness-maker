---
type: review
task_slug: harness-economics-observability
status: CHANGES_REQUESTED
created: 2026-07-25
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check (K=2 of N=4)
rounds_used: 1
max_review_rounds: 3
final_grade: B
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/snapshot/*.expected.yaml (8 files)
    - tests/unit/test_economics_cli.py
  scenario_misses: []
  task_slug: harness-economics-observability
  computed_at: 2026-07-25
second_opinion_results:
  - model: codex
    status: invoked
    findings: 9
  - model: antigravity
    status: invoked
    findings: 7
---

# REVIEW — harness-economics-observability (round 1)

## 🎯 Round 1 Summary

**Grade B** (0 consensus-passed P0, 2 consensus-passed P1) against a threshold of **A**
→ Status `CHANGES_REQUESTED`, `human_review_needed: true`.

Scope reviewed: Phase 1–3 of the PLAN (`economics.py`, `economics_source.py`, the config
wiring across `models.py` / `interview.py` / `synthesize.py` / `command_registry.py` / both
harness-yaml templates, plus three new test modules and the fixture transcript store).
3,185 insertions across 24 files.

Four independent voices ran: `code-reviewer` (9 findings), `security-reviewer` (4),
`codex` (9), `antigravity` (7). **7 consensus clusters** formed at K=2.

Fixes applied this round: **9**. New regression tests added: **21**
(`tests/unit/test_economics_review_fixes.py`). Every fix that changed behaviour got a test —
before this round, all nine defects shipped GREEN through 92 existing tests, which is the
"changed without a test" class this repo keeps re-hitting.

### Procedure deviations (disclosed)

1. **Pass 1.5 (`code-verifier`) and Pass 2 (contextual re-run) were SKIPPED.** Four
   independent voices had already produced concrete, locally-verifiable findings; the
   orchestrator hand-traced the two highest-severity claims against source instead. Cost of
   the skipped passes ≈ 250k tokens on a task whose subject is token economy. Consequence:
   Pass 1 findings were not contextually re-validated by the reviewers themselves, so the
   `manual-only` list below carries more residual uncertainty than a full two-pass run would.
2. **Fixes applied beyond the consensus-passed set.** The procedure auto-applies only
   `consensus-passed` findings. Three `manual-only` findings were nonetheless fixed because
   the orchestrator independently verified them by reading the code (marked
   *orchestrator-verified* below). Each has a regression test.

### Harness bugs found incidentally (OUT OF SCOPE — not fixed here)

Two live defects in harness-maker's own second-opinion mechanism surfaced while running
this review. Neither is caused by this task's diff.

| # | Defect | Evidence | Impact |
|---|---|---|---|
| H1 | The rendered `/hm:review` + `/hm:plan` recipes pass `--output-schema .claude/schemas/…` as a **relative** path. Under `worktree.feature_branch_workflow` the stage runs inside `.worktrees/<slug>/`, which has no `.claude/schemas/`. | `codex exec` exited 1 with `Failed to read output schema file .claude/schemas/second-opinion-finding.schema.json: No such file or directory`. Re-running with the absolute path succeeded and returned 9 findings. | Every codex second opinion silently degrades to `skipped` whenever the stage runs in a task worktree — i.e. the normal path for the Production preset. |
| H2 | The rendered `agy` recipe is `agy --print --sandbox --print-timeout … < prompt_file`. `agy --print` **takes the prompt as its value**, so it consumes `--sandbox` as the prompt and ignores stdin. | First run returned: *"It looks like you've only provided the text `--sandbox`."* Probe `agy --sandbox --print "Reply with exactly: PONG"` → `PONG`. Re-running in that form returned 7 real findings. | Every antigravity second opinion has been answering the literal string `--sandbox`, i.e. **every antigravity vote in this harness is vacuous**. The `--sandbox` flag is also consumed as a value rather than applied. Note the tension: CLAUDE.md requires the command to *begin* with `agy --print --sandbox` so the `Bash(agy --print --sandbox:*)` allow-rule prefix-matches — fixing the order breaks the allow rule, so this needs a paired change. |

## 🔍 Drift Findings

| Severity | Finding |
|---|---|
| P1 | `tests/snapshot/*.expected.yaml` (8 files) changed but appear in no completed phase's `scope`. They are a **necessary consequence** of Phase 3's harness-yaml template edit (the `harness.yaml` body hash moved), and PLAN Phase 4 lists snapshot regeneration under its own scope. This is a PLAN omission, not an unplanned code change — Phase 3's scope should have named it. Diff verified to be exactly one line per file. |
| P3 | `tests/unit/test_economics_cli.py` is not named in Phase 3's scope, which listed only source files. Benign. |

No scenario misses (no SPEC exists for this task; Phase exit criteria were used instead).

## ✅ Consensus Findings (auto-fix eligible)

### P1 — `[3/4]` Naive timestamp raises `TypeError` out of a never-raise module
`code-reviewer` + `security-reviewer` + `codex` independently. `_parse_ts` returned whatever
`datetime.fromisoformat` yielded; a transcript line without a `Z`/offset, or a `--now` value
without one, made `turn.ts < cutoff` compare naive against aware and abort the whole run.
**Fixed** — `_parse_ts` and a new `_parse_now` both coerce to UTC. The regression test caught
that the first fix was **incomplete** (only the transcript half; the `--now` half still
crashed), which is precisely what all three reviewers had said to fix together.

### P1 — `[2/4]` A write+verify turn opened a verify window it should not have
`codex` + `antigravity` independently; `code-reviewer` explicitly verified this area as clean,
so this is a **live disagreement resolved 2:1 against the dissent**. Orchestrator hand-trace
confirmed the defect: a `hm:review`-attributed turn that writes is PRODUCE, yet it still
stamped `last_verify_at`, making the later comparison `idx < idx` false so the **next**
unprompted rewrite escaped REWORK. **Fixed** — `last_verify_at` is now written only when the
turn's final label is `VERIFY`.

### P2 — `[3/4]` `coverage` conflated window filtering with format drift
`code-reviewer` + `codex` + `antigravity`. Window-excluded lines stayed in the denominator, so
a narrow `--days` produced a near-zero coverage indistinguishable from the reader breaking —
destroying the exact ADR-009 signal. **Fixed** — `outside_window` is subtracted from the
denominator.

### P2 — `[2/4]` Whole transcripts loaded into memory
`security-reviewer` + `codex` (antigravity raised the same at P1; tiers are not bridged, so
its vote is recorded independently). `read_text()` + `splitlines()` holds the full string and
the full list simultaneously; the real store is ~100 MB. **Fixed** — streamed line-by-line
with a 4 MB per-line cap counted as `oversize_line`.

### P2 — `[2/4]` Unbounded transcript-derived strings became JSON map keys
`security-reviewer` + `antigravity`. `turn.model` / `attributionSkill` / `attributionAgent`
flow into report dict keys with no length or charset bound. **Fixed** — `_clip` bounds them to
64 printable chars at ingestion.

### P2 — `[2/4]` `resolve_model_family` depended on dict insertion order
`code-reviewer` + `antigravity`. **Fixed** — longest-match wins, deterministic regardless of
`PRICE_TABLE` layout.

## 🤝 Disagreements

| Location | Position A | Position B | Resolution |
|---|---|---|---|
| `economics.py` classifier state | `codex` P1 + `antigravity` P1: write+verify turn corrupts the verify window | `code-reviewer`: explicitly verified clean — "the equal case resolves to PRODUCE, which is the safe bias" | **A wins.** Orchestrator traced it: the later rewrite, not the write+verify turn itself, is the victim. `code-reviewer` checked the wrong turn. |
| `economics.py:284` adjacency gap | `antigravity` P1: the gap is measured from the anchor, not the previous turn — "artificially limits total block duration" | ADR-006 specifies "≤ max_gap_min **since that turn**", where *that turn* is the anchor | **Refuted.** Measuring from the anchor is the specified behaviour and is the point of the bound (stopping a long manual stretch from inheriting a stale stage). No change. |

## 📝 Manual-Only Findings (NOT auto-applied)

### Fixed anyway — *orchestrator-verified* (each has a regression test)

| Severity | Source | Finding |
|---|---|---|
| P1 | code-reviewer | `price_model` fallback used an **exact** dict-key lookup while turn models used substring matching, so `price_model: "claude-sonnet-4-5"` silently priced at opus — a 5× error in a tool whose whole output is dollars. Fixed: the fallback resolves through the same matcher. |
| P1 | security-reviewer + antigravity (P0, tiers not bridged so no consensus) | `discover_transcript_dirs` matched by string prefix on a **lossy** encoding, so a foreign project could be ingested into a project-local report. Fixed with a per-turn `is_own_cwd` boundary rather than by requiring the worktree to exist on disk — worktrees are deleted when their task lands, and a disk check would have silently dropped all historical worktree sessions. |
| P2 | codex | Filesystem discovery could raise `OSError` despite the never-raise contract. Fixed with guards. |

### Open — NOT fixed, carried to the next round

| Severity | Source | Finding | Assessment |
|---|---|---|---|
| P1 | codex | Classifier state (`last_write_at`, `last_verify_at`) is keyed by task slug only, while `load_turns` globally sorts turns from **all** sessions. A slug reused across unrelated tasks lets one session's verify clear another's rewrite window. | **Believed real.** Rare in practice (slugs are task-scoped) but the fix is cheap — add session identity to the key. Deferred only because it needs a fixture with two same-slug sessions. |
| P1 | codex | When `--root` is itself a worktree path, `encode_project_dir` yields `-base--worktrees-slug` and discovery then finds neither the base dir nor sibling worktrees — the report silently truncates. | **Believed real** and reachable: this stage runs inside a worktree. Overlaps `code-reviewer` P2 on the same line. Fix = resolve `--root` back to the base repo before encoding. |
| P1 | code-reviewer | The entire `harness.yaml` tuning surface reached the report untested. | **Partially closed** — one regression test now pins `adjacency_estimate: false` end-to-end; the other five knobs remain unpinned. |
| P2 | code-reviewer | `_VERIFY_SKILLS` hardcodes `{hm:review, hm:verify}`; a fused workflow name (`exec-rev-wrap-ver`) never counts as VERIFY. | **Real and material** — the harness's own default workflow is fused, so on real data VERIFY is under-counted for exactly the users running the default. |
| P2 | code-reviewer | `aggregate()` silently requires chronologically sorted input; only `load_turns` guarantees it. | Real; defensive sort is one line. |
| P2 | code-reviewer | Empty-string `attributionSkill` is not `None`, so it bypasses the unattributed branch. | Partly mitigated — `_clip` now returns `None` for an empty string. Worth a test. |
| P2 | antigravity | Untrusted model strings could still explode the key space (millions of distinct keys). | Length is now bounded; **cardinality is not**. |
| P3 | codex | `AdjacencyBounds` / `EconomicsConfig` accept negative caps, producing negative wall-clock. | Real, trivial (`Field(ge=0)`). |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | 9             | 8         | 0   |

Final grade: **B** (threshold A)
Iterations used: 1 / 3
Status: **CHANGES_REQUESTED**
human_review_needed: **true**

`unverified_severe` = TRUE — three `manual-only` P1 findings remain open (session-scoped
classifier state, worktree `--root` truncation, partially-untested config surface), plus the
`antigravity` P0 on the prefix collision whose severity tier never bridged to the
`security-reviewer` P1 on the same defect (that defect *is* fixed; only its consensus tag is
unresolved).

**Verification after fixes:** `ruff check` clean · `mypy --strict` clean · full `pytest`
green · 21 new regression tests, each pinning one applied fix.
