---
type: spec
task_slug: review-after-fixes
status: approved
created: 2026-10-17
tags: [harness-maker, spec, templates, execute, review, resume]
test_framework: pytest
interview_rounds: 1
lane: full
parent_spec: "[[SPEC-maker-advance]]"
summary: "execute writes the REVIEW file only after its fix loop, so a REVIEW on disk means execute finished and a Resume after an interrupted execute re-enters execute instead of wrapup"
---

# SPEC — review-after-fixes (the REVIEW is execute's completion record)

## 🎯 Intent

REVIEW-maker-advance F5: `world_model_digest.next_stage` returns `wrapup` as soon as any
`REVIEW-<slug>-<date>.md` exists (SPEC-maker-advance AC-006). execute writes that file *before* it
fixes the accepted findings, so an execute interrupted mid-fix leaves a REVIEW, and Maker's Resume
(with the Advance rule) enters wrapup. Wrapup's `hm check` blocks `unresolved` findings and failing
tests, but not an `accepted` finding nobody fixed. On a card (2026-10-17) the DRI chose "지금 고침"
(fix it now).

Default picked: no new state. Instead of a new "execute finished" field, execute writes the REVIEW
last, after the fix loop. The REVIEW's existence then *is* the completion record, the digest is
unchanged, and SPEC-maker-advance AC-006 stays true.

## 📐 Outcomes

- In every rendered execute (Claude command and Codex skill, Side and Production), Step 6 runs the
  fix loop first: dispositions, fix the accepted findings, rerun `hm check`, review again, up to the
  round cap. Only then is `work-docs/REVIEW-<slug>-<YYYY-MM-DD>.md` written. It carries every round's
  findings with their final dispositions, so its `accepted` rows are already fixed when it lands on
  disk. No extra `hm check` follows it; wrapup's `hm check` gates it, as today.
- An execute re-entered after it passed Bind (no REVIEW yet, every testable AC already
  `pending_test: false`) does not redo Phase A or RED. It reruns Bind's gate and continues at Step 4.
- The digest is unchanged. Any REVIEW still means `wrapup` (SPEC-maker-advance AC-006), and that is
  now true only after the fixes.
- execute stays inside its AC-004 budget (SPEC-hm-overhaul-p1) in every arm.

## 🧩 In-Scope Scenarios

- **S1 (two rounds).** Given round 1 returns two accepted findings, they are fixed, and round 2 returns none, when execute finishes, then the REVIEW lists both round-1 findings as `accepted`, not `none`.
- **S2 (interrupted after review).** Given execute stops after Bind and the reviewer but before the fixes, when Maker resumes the task, then the digest says `execute` (no REVIEW yet), and execute reruns Bind's gate and goes to Step 4 and Step 6 without rerunning RED on the implemented code.
- **S3 (cap reached).** Given findings remain open after `reviewers.max_review_rounds`, when execute writes the REVIEW, then those rows are `unresolved`, Maker's Advance rule stops, and wrapup's `hm check` fails on them, as before. execute never edits a disposition after the REVIEW is written.

## 🚫 Non-Goals

- No new REVIEW field, marker or ledger, and no change to `world_model_digest` or `hm check`.
- Resuming an execute interrupted before Bind (mid Phase A or C) is unchanged.
- No guard on a manual `/hm:wrapup` after an interrupted execute; typing it is the user's call.
- No change to the REVIEW table format or the disposition vocabulary.

## 🔒 Constraints

| constraint | source |
|---|---|
| Test framework: pytest | repo |
| execute ≤ its AC-004 budget per arm (`tests/unit/test_overhaul_p1_surface.py::test_ac004_char_budgets`) | SPEC-hm-overhaul-p1 |
| The first `hm check --slug <slug>` in execute stays Bind's, with `long_gate` (`tests/unit/test_overhaul_p1_kept.py`) | SPEC-hm-overhaul-p1 |
| Step 6 keeps its heading, "disposition", "never edit a test file to resolve a finding whose target is not that test", `subagent_type="code-reviewer"` and `reviewers.max_review_rounds` | kept-feature tests |
| `hm check`'s review section with no REVIEW stays ok and non-gating, so the in-loop reruns pass | `check.review_section` |
| Surface growth is held as a PLAN `surface_allowance` and folded after merge | ADR-010 |

## ⚠️ Irreversible Decisions

None. The REVIEW format and its readers (`check.review_section`, `review_effect.parse_review`,
`light_lane.review_records`, wrapup's land glob) are unchanged; only when execute writes it moves.

## ✅ Acceptance Criteria

### AC-001: execute writes one cumulative REVIEW after its fix loop
In Step 6 of the rendered execute for every ARM (Claude command and Codex skill), no `REVIEW-`
appears before "review again"; after it, the text contains `REVIEW-<slug>-<YYYY-MM-DD>.md`, the
literal "the record that execute finished" and the literal "every round's findings"; and no
`hm check --` invocation appears between that REVIEW sentence and "then STOP" (the final print still
names "the `hm check` result").
- oracle_source: golden. The ordering and the cumulative rule come from the DRI's fix-now choice
  applied to F5's failure path and to spec-validator round 1 (a REVIEW must not exist before its
  fixes, and it must not drop fixed findings), not from the template.

### AC-002: an execute re-entered after Bind skips to Step 4
In every rendered execute, one line before `## Step 0` (the Session Context Loading hot tier, where
execute already resumes) holds the literal "every testable AC is `pending_test: false`", followed on
the same line by "rerun Bind's gate" and "Step 4"; that line contains no `hm check --slug`, so the
first one is still Bind's.
- oracle_source: golden. The `pending_test: false` signal is what `hm spec_machine mark-tested`
  writes at Bind (SPEC-hm-overhaul-p1), and S2 is the failure path, not read from the template.

## 🧪 Verification

| AC | mode | test |
|---|---|---|
| AC-001 | unit (render) | `tests/render/test_review_after_fixes.py::test_ac_001_review_written_after_fix_loop` |
| AC-002 | unit (render) | `tests/render/test_review_after_fixes.py::test_ac_002_resume_after_bind_skips_red` |

## ❓ Open Questions

None.

## 🔧 Refinement Decisions

- "Write the REVIEW last" was chosen over a new `execute: open|done` field (default; inferred). It
  needs no new state, keeps the digest and AC-006 as they are, and makes `accepted` mean fixed. The
  cost is that an interruption loses the in-context findings, and the resumed execute reviews again.
- spec-validator round 1 (MAJOR_REVISION, 6 critiques), all taken:
  - The post-REVIEW `hm check` was dropped. In S3 it fails by design, and execute's exit-1 rule
    ("fix and rerun") would break the round cap or flip `unresolved` rows. It also cost one more
    full suite per execute, which wrapup's check already covers.
  - The REVIEW must carry every round's findings, so `review_effect` keeps counting findings that
    were fixed in-loop.
  - The digest AC was dropped. It passed on today's code and duplicated SPEC-world-model-followups
    AC-003.
  - S2 needed a resume path: execute restarts at RED, which fails on implemented code. AC-002
    adds it, keyed on `pending_test: false` from Bind. It sits in the hot tier, which already holds
    execute's other resume rule. That line is a kept feature (SPEC-hm-overhaul-p1 AC-009), so the
    clause is appended to it rather than rewriting it.
- To keep execute within its 7,000-char AC-004 budget (about 30 chars of headroom before), these were
  trimmed: "The PLAN holds no ACs; it points at the SPEC." (only the PLAN's `spec:` frontmatter now points at
  the SPEC; the no-ACs invariant stays in SPEC-hm-overhaul-p1), "if passed," in the `--no-tdd` notice,
  "It covers every testable AC, so it runs here and nowhere else." after RED, and the Step 0.3, Step 1
  and Step 2 wording (Step 2's RESEARCH sentence moved into Step 1). The shipped surface nets 0 chars per
  variant.
- code-reviewer round 1 (7 findings), applied before the REVIEW was written:
  - The resume rule needs at least one testable AC (F1), runs after Step 2 (F2), and is its own
    `**Resume.**` paragraph ahead of Session Context Loading rather than the hot-tier bullet (F3). It
    still sits before `## Step 0`, as AC-002 requires.
  - Step 6 says `none` only when no round found anything (F5), and "what stays open" replaces "the rest" (F6).
  - Accepted as a cost (F4): a compaction mid-loop can lose earlier rounds' findings before the REVIEW is
    written. This is the same trade-off recorded above.
