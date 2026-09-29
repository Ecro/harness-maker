---
type: spec
task_slug: top-issues-2026-09
status: approved
created: 2026-09-30
tier: 2
tags: [harness-maker, spec, python, review-loop, verification-cache, context-lint]
test_framework: pytest
interview_rounds: 0
research_doc: "[[RESEARCH-top-issues-2026-09]]"
summary: "Move review fix-attribution, verify pass-markers and CLAUDE.md size from prose into code"
---

# SPEC — top-issues-2026-09

## 🎯 Intent

Three load-bearing quantities in harness-maker are decided by prose, so nothing measures or
enforces them:

1. **Review fix attribution.** The review auto-fix loop's `caused_by` is never persisted. 67 of
   69 persisted payloads have no `caused_by` key, and the other 2 have `null`. The payload is
   persisted before the prose step that "determines" the value.
2. **The verification pass-marker.** The LLM writes it by calling `mark-pass` after saying the
   suite passed. On 2026-09-20 this route landed an uncollectable test on main.
3. **CLAUDE.md size.** It is linted in lines only, so a 65 KB (~18k-token) CLAUDE.md passes a
   500-line limit.

This SPEC moves each quantity into deterministic code.

## 🌅 Outcomes

- **Fix attribution.** After every main-loop review round, the persisted payload says for each
  finding whether the fix the loop applied just before that round's re-review (pinned `r<N>`) introduced it (`fix-r<N>`), did not (`none`), or cannot be
  told (`unknown`). `hm review_churn fix-defect-rate` reports the rate across persisted reviews.
  The REVIEW iteration record and the batch trigger read that stamped value; no second owner
  derives it.
- **Pass markers.** `/hm:verify` and `/hm:wrapup` accept a cached pass only from a marker written
  by `verification_cache run`. That marker is written only when the CI-derived primary gate
  commands all exit 0 on a tree that did not change during the run, and it records the commands
  it actually ran. A marker written by `mark-pass`, or by `run` with a different command list,
  never satisfies `run`'s cached path.
- **Character budget.** A CLAUDE.md or AGENTS.md over its character budget is flagged by the
  render-time lint for both presets, even when it is under its line budget. `/hm:health` flags
  CLAUDE.md (readiness reads only CLAUDE.md today). This repo's CLAUDE.md is under 40,000
  characters, and every line of the relocated sections is still present in CLAUDE.md or
  `docs/reference/`.
- **Stays unmeasured:** confirmation-pass attribution. Confirm-pass payloads are not persisted
  today, so this SPEC's rate covers main-loop rounds ≥ 2 only and does not answer the
  confirm-pass premise.

## 📋 In-Scope Scenarios

Round labels follow the Auto-Fix Loop: iteration N pins its fixes as `r{N}-pre/post` and its
re-review produces round N's findings, so round N is attributed against `r{N}`.
Coordinates: attribution uses **new-side** line numbers of `git diff -U0 r{N}-pre r{N}-post`,
which are the lines of the tree the round-N reviewers read. A hunk `+c,d` with `d > 0` covers
lines `c..c+d-1`. A deletion-only hunk `+c,0` covers lines `c` and `c+1`, the two lines adjacent
to the removal. A finding matches when its line is within ±3 of a covered line.

### S1: fix-introduced finding is attributed
**Given** refs `refs/hm-churn/v1/<slug>-r2-pre` and `-r2-post` exist, and iteration 2's fix inserted ten lines after line 2 of `a.py` (new-side 3–12) and edited original lines 30–32 (new-side 40–42)
**When** `hm review_churn attribute --slug <slug> --run-id <run> --round 2 --findings-file F` runs on a round-2 finding at `a.py:41` whose `caused_by` is null or absent
**Then** F is rewritten with that finding's `caused_by == "fix-r2"`
**And** stdout is one JSON line with per-value counts

### S2: non-attributable cases are explicit, never null
**Given** round-2 findings outside the covered lines, or with a null `line` in a changed file, or a slug whose r2 refs do not exist, or any round-1 finding
**When** `attribute` runs
**Then** each gets `none` (outside, or round 1) or `unknown` (null line in a changed file, or missing refs), and no finding leaves with `caused_by` null or absent
**And** a finding at the line adjacent to a deletion-only hunk gets `fix-r2`, a round-2 finding when only `r1` refs exist gets `unknown`, and a finding at an old-side-only line (`a.py:31`, 9 lines from any new-side covered line) gets `none`

### S3: attribution never rewrites unrelated data
**Given** a findings file (list shape or `{"findings": [...]}` shape) where some findings already carry a string `caused_by`, some carry `null` or no key, and some ids appear in an earlier persisted payload of the **same slug and run id** (`<run-id>-round<k>-merged.json`, k < N)
**When** `attribute` runs
**Then** already-stamped string values are unchanged
**And** carried ids copy the earlier round's string value, or get `unknown` when that value was null or absent, even when they sit inside the fix delta
**And** an id that appears only under a different run id is not treated as carried
**And** every other field of every finding, and the top-level shape, are unchanged
**And** a malformed file exits 1 and leaves the file byte-identical

### S4: fix-defect rate is reported
**Given** persisted payloads `<store>/<slug>/<run-id>-round<N>-merged.json`, where run ids may contain hyphens
**When** `hm review_churn fix-defect-rate` runs
**Then** it prints JSON with, per slug and in total, counts of P0/P1 findings first seen in round ≥ 2, grouped as `fix` (any `fix-r*`), `none`, `unknown` and `unstamped` (null or absent), and `rate = fix / (fix + none)` (null when the denominator is 0)
**And** P2/P3 findings, round-1 findings and carried ids are excluded

### S5: verification gate runs itself and marks only on success
**Given** a repo whose `.github/workflows` yields primary commands `[c1, c2]`
**When** `hm observability.verification_cache run --root .` runs
**Then** if a marker for the current key was written by `run` with the same command list, it runs nothing, prints `cached: true` and exits 0
**And** otherwise it runs each command (`shlex.split`, `shell=False`, per-command `--timeout-s`, default 540 s, within a whole-run `--deadline-s`, default 570 s — sized for a foreground call; the Claude Code recipe runs in the background with both lifted to 3600 s and reads the JSON `exit` field), and on the first non-zero exit or timeout it stops, writes no marker, prints that command's output tail to stderr and exits 1
**And** if every command exits 0 but the relevant key changed during the run, it writes no marker and exits 4 with the changed paths on stderr
**And** if every command exits 0 on an unchanged key, it writes a marker with `writer: "run"`, the executed commands and their hash, and exits 0
**And** if the plan is degraded it runs nothing, writes no marker and exits 3

### S6: stage templates use one owner per quantity
**Given** a rendered harness (claude and codex variants)
**When** `/hm:verify` Check 2 and `/hm:wrapup`'s verification step are rendered
**Then** they call `verification_cache run`, say how to handle exit 1/3/4 and a host-killed call, and mention `mark-pass` only inside the degraded (exit 3) fallback
**And** `/hm:review` Step 3.4 runs `review_churn attribute --findings-file X` and then `persist-payload --file X` with the same temp-file token
**And** the Auto-Fix Loop and the second-opinion-gate skill read `caused_by` from that stamp. Arm (b) fires on a `fix-r*` value, and the REVIEW grammar is `caused_by=fix-r<N>|none|unknown`.

### S7: character budget for CLAUDE.md / AGENTS.md
**Given** a CLAUDE.md or AGENTS.md whose body is under the line budget but over the character budget (Production 40,000; Side 16,000)
**When** `context_lint.lint` runs for that asset type and preset, or readiness computes `claude_md_within_limit` for CLAUDE.md
**Then** a warning names the character count and budget, and the readiness signal fails

### S8: this repo's CLAUDE.md is relocated, not cut
**Given** the CLAUDE.md at the task base commit `3b718d91` (65,108 bytes)
**When** the relocation lands
**Then** CLAUDE.md is ≤ 40,000 characters
**And** every non-blank line of each relocated section of the old file appears verbatim in the new CLAUDE.md or in a `docs/reference/*.md` file that CLAUDE.md links to
**And** the sections other tests pin stay in CLAUDE.md: `릴리스 절차`, `Context discipline`, `Step sensitivity classes`

## 🚫 Non-Goals

- Changing the review loop's control flow (confirm-pass policy, fix selection, round caps). Only the source of `caused_by` changes, and the batch trigger keeps its meaning.
- Persisting confirmation-pass payloads, or attributing confirm-pass findings. This deliberately deviates from RESEARCH Open Question 2's default; see Refinement Decisions.
- Per-fix-number attribution (`#7`). It is replaced by round-level `fix-r<N>`.
- Changing the verification-cache fingerprint (`compute_relevant_skip_key`), or explaining the 2026-09-20 fresh-marker cause.
- Removing `mark-pass`. It stays for the degraded path and for the `verify-before-completion` skill, whose markers `run` now ignores.
- Running `additional_commands`. `run` executes `primary_commands()` and lists the additional ones on stderr as not run.
- Switching `context_lint` agent/skill/workflow units to characters, or extending readiness to AGENTS.md.
- Splitting stage command templates (review.md is 88k characters), or retiring the legacy stash/finalize worktree model.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | repo standard |
| Subprocess | `shell=False`, explicit `timeout=`; `run` defaults 540 s/gate, 570 s/run (foreground-safe); recipes lift both in the background | implementation-patterns.md; a real suite (this repo: 425–702 s) outlives the 600 s foreground cap |
| File writes | atomic (tmp + `os.replace`) | implementation-patterns.md |
| Char budget | CLAUDE.md/AGENTS.md: Production 40,000, Side 16,000 body chars | ~5k-token always-loaded guidance ≈ 16k chars for Side; Production 2.5× |
| Lint severity | warn, never fail render | prior ADR-004 (token-efficiency): render must not break existing harnesses |
| Compatibility | Python 3.12, `mypy --strict`, `ruff` | repo standard |
| Dogfood | this repo's rendered `.claude/` pins plugin 0.60.6 and is not re-rendered here | memory: rendered harness pins the released plugin |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Persisted review payloads carry `caused_by ∈ {"none","unknown","fix-r<N>"}` written by `review_churn attribute`; REVIEW grammar changes from `#N` to the same literals | schema/file format/storage layout | the payload corpus is append-only history; readers key on these literals |
| IRR-002 | New CLI verbs `review_churn attribute` (requires `--run-id`), `review_churn fix-defect-rate`, `observability.verification_cache run` (exit 0/1/3/4) | public API/CLI contract | rendered templates in every consumer harness call them by name and branch on the exit codes |
| IRR-003 | Verification markers gain `writer` and `commands_sha256`; `run` treats markers without `writer: "run"` and the matching hash as not fresh | schema/file format/storage layout | markers are shared across harness versions in `~/.cache/harness-maker/verify` |

## ✅ Verification Criteria

### AC-001: attribute stamps fix-r(N) on findings inside the round's fix delta
### AC-002: attribute stamps none or unknown for every non-attributable case
### AC-003: attribute preserves shape, stamped values and all other fields
### AC-004: attribute exits 1 on a malformed file and leaves it untouched
### AC-005: fix-defect-rate reports per-slug and total counts and rate
### AC-006: review template stamps and persists the same temp file in both variants
### AC-007: verification_cache run marks only when every command passes on an unchanged key
### AC-008: verification_cache run reports cached only for its own marker with the same commands
### AC-009: verification_cache run exits 3 without running or marking on a degraded plan
### AC-010: verify and wrapup templates call run and confine mark-pass to the degraded fallback
### AC-011: context_lint warns on CLAUDE.md and AGENTS.md over the character budget
### AC-012: readiness claude_md_within_limit fails on character overflow
### AC-013: repo CLAUDE.md is at most 40000 characters
### AC-014: attribute copies the earlier round value for carried ids of the same run
### AC-015: review loop and gate skill read caused_by from the stamp
### AC-016: relocated CLAUDE.md sections survive verbatim

| Scenario | AC | Verification mode | Test name |
|---|---|---|---|
| S1 | AC-001 | unit (real git fixture) | `tests/unit/test_review_churn_attribute.py::test_finding_inside_fix_delta_is_fix_r1` |
| S2 | AC-002 | unit (parametric) | `tests/unit/test_review_churn_attribute.py::test_non_attributable_cases` |
| S3 | AC-003 | unit (property) | `tests/unit/test_review_churn_attribute.py::test_attribute_changes_only_unstamped_caused_by` |
| S3 | AC-004 | unit | `tests/unit/test_review_churn_attribute.py::test_malformed_file_untouched` |
| S3 | AC-014 | unit | `tests/unit/test_review_churn_attribute.py::test_carried_ids_same_run_only` |
| S4 | AC-005 | unit | `tests/unit/test_review_churn_attribute.py::test_fix_defect_rate_report` |
| S6 | AC-006 | render | `tests/render/test_render_review_attribution.py::test_attribute_and_persist_share_file` |
| S6 | AC-015 | render | `tests/render/test_render_review_attribution.py::test_caused_by_single_owner` |
| S5 | AC-007 | unit (stub commands) | `tests/unit/test_verification_cache_run.py::test_marks_only_when_all_pass_and_key_stable` |
| S5 | AC-008 | unit | `tests/unit/test_verification_cache_run.py::test_cached_only_for_own_marker` |
| S5 | AC-009 | unit | `tests/unit/test_verification_cache_run.py::test_degraded_plan_exit_3` |
| S6 | AC-010 | render | `tests/render/test_render_verification_run.py::test_stages_call_run` |
| S7 | AC-011 | unit (parametric files × presets) | `tests/unit/test_context_lint_chars.py::test_char_budget_warns_under_line_budget` |
| S7 | AC-012 | unit | `tests/unit/test_context_lint_chars.py::test_readiness_char_overflow_fails` |
| S8 | AC-013 | unit | `tests/unit/test_context_lint_chars.py::test_repo_claude_md_within_char_budget` |
| S8 | AC-016 | unit (differential vs base blob; skips when `3b718d91` is absent, e.g. shallow clone) | `tests/unit/test_claude_md_relocation.py::test_relocated_sections_survive` |

## ❓ Open Questions

(none. Resolved by the RESEARCH defaults and the spec-validator pass; see Refinement Decisions.)

## 🔎 Spec Validation

spec-validator (1 pass, advisory): **MAJOR_REVISION**, with 2 critical, 9 warning and
1 suggestion findings. The Codex second opinion was `skipped` (CLI usage limit until
2026-10-04). Every finding was folded into this revision:

- **Absent key ≡ null** (critical): S1–S4, AC-002 row, AC-003 relation.
- **Marker provenance** (critical): S5, AC-008, IRR-003.
- **New-side coordinates and deletion-only hunks**: the preamble in the In-Scope Scenarios section, S1, AC-002 rows. (Revised during execute: the first fixture — two lines inserted at the top, lines 10–12 edited — could not tell old-side from new-side under the ±3 tolerance, so S1 now uses a ten-line insertion that separates the two sides by more than the tolerance.)
- **`--run-id` and carried-id scoping**: S3, AC-014.
- **Single owner of `caused_by`**: S6, AC-015.
- **AC-006 binds both commands to one file token.**
- **Key drift gets exit 4; per-command timeout of 540 s; host-kill handling**: S5, S6.
- **Primary vs. additional commands made explicit**: Outcomes, Non-Goals.
- **AC-011 parametrized over files × presets**: the readiness Outcome is narrowed to CLAUDE.md.
- **Content-loss oracle is a re-runnable test (AC-016)**, and pinned sections stay in CLAUDE.md.
- **Confirm-pass deviation made explicit**: Outcomes and Non-Goals.
- **AC-005 fixture widened**: P2, round-1 and carried rows, per-slug output, hyphenated run id.

## 🔍 Refinement Decisions

- **No interview (0 rounds).** Mid-pipeline, the user instructed verbatim:
  "절대 멈추지 말고, 너의 추천안대로 wraup 까지 끝까지 진행해." ("Never stop; carry my
  recommendation all the way through wrapup.") and "나에게 묻지말고 진행해" ("Proceed without
  asking me."). The RESEARCH recommendation is taken as the accepted direction.
- **RESEARCH defaults applied:** round-level attribution; `run` exits 3 on a degraded plan;
  Production/Side character budgets of 40,000/16,000, warn-only.
- **Round-label correction (review round 1, re-approved).** The approved text said round N reads
  `r{N-1}`. The Auto-Fix Loop actually pins iteration N's fixes as `r{N}` before round N's re-review,
  so that text would have stamped every real round-2 finding `unknown`. Found while dogfooding
  `attribute` in this task's own `/hm:review`; S1, S2 and AC-001/002/014 now follow the loop's labels.
- **Deviation from RESEARCH Open Question 2** (confirm-pass attribution "yes when refs exist"):
  deferred. Confirm-pass payloads are never persisted, so there is no file to stamp. Persisting
  them changes the review loop's dispatch steps, which this SPEC keeps out of scope. The rate is
  therefore main-loop only, and the confirm-pass premise stays unmeasured.
- **Intent (Step 0.5):** none. No active intent covers these slices.
- **Readiness:** the character check folds into the existing `claude_md_within_limit` signal
  rather than a new one, so structural weights and baselines do not move.
