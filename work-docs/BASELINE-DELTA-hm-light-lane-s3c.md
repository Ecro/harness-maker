# BASELINE-DELTA — hm-light-lane-s3c

Re-frozen inside this task, after its own tests were green (ADR-010,
`ratchet-rebaselined-by-its-own-subject`). Every number below is measured on this repo's own
`harness.yaml` render (`_surface_baseline.measure_surface()`), against `a7403f2f`, which equals
`c3096d4c` for every rendered byte (the commits between them touch only `specs/` and
`work-docs/`).

Direction: `aggregate_chars.claude` **fell** by 26716 chars (266773 → 240057), and
`aggregate_chars.codex` **rose** by 2822 chars (292228 → 295050). The Claude drop is the
preamble leaving six commands, plus the full PLAN text and the full machine.yaml schema leaving
execute and spec. The Codex rise is the light PLAN block and the minimal schema, which Codex
carries inline next to the full text it keeps. The three new `.claude/hm/` files are outside
this baseline: `stage-preamble.md` 4795, `execute-plan.md` 5452, `spec-machine-full.md` 3336.

## §A — one preamble

The preamble span (loop-mode check, start banner, autopilot picker, output language; 4362 chars
on this render) became a 578-char pointer to `.claude/hm/stage-preamble.md`, so A is −3784 on
each Claude stage command. The moved text is byte-identical in all 16 A arms (AC-002). Codex
skills, `CLAUDE.md` and `AGENTS.md` keep it inline (AC-003).

| Key | Before → After | A | B | C | SPEC bound |
|---|---|---|---|---|---|
| `surface.claude.research.chars` (`research`) | 20461 → 16677 | −3784 | 0 | 0 | ≤ 16749 |
| `surface.claude.spec.chars` (`spec`) | 43234 → 37941 | −3784 | +248 | −1757 | ≤ 38822 |
| `surface.claude.execute.chars`, `.round_trips` (`execute`) | 45572 → 39285, 18 → 19 | −3784 | 0 | −2503 | ≤ 39360 |
| `surface.claude.review.chars` (`review`) | 60617 → 56833 | −3784 | 0 | 0 | ≤ 56905 |
| `surface.claude.verify.chars` (`verify`) | 16435 → 12651 | −3784 | 0 | 0 | ≤ 12723 |
| `surface.claude.wrapup.chars` (`wrapup`) | 33099 → 29315 | −3784 | 0 | 0 | ≤ 29387 |
| `surface.codex.hm-execute.chars`, `.round_trips` (`hm-execute`) | 62541 → 64316, 26 → 27 | 0 | 0 | +1775 | ≤ +2500 |
| `surface.codex.hm-spec.chars` (`hm-spec`) | 45284 → 46331 | 0 | +248 | +799 | ≤ +300 / ≤ +800 |
| `aggregate_chars.claude`, `.codex` (`aggregate_chars`) | 266773 → 240057, 292228 → 295050 | | | | the rows above |
| `payload_digest`, `render_sha` | mechanical | | | | `render_sha` is the merge-base `a7403f2f` (= `origin/main`) |

The margins are thin by design of the bounds, not by accident of the render: execute C is
−2503 against ≤ −2500, Codex hm-spec C is +799 against ≤ +800, and spec B is +248 against
≤ +300. A later edit to the light block or the minimal schema has almost no room.

`/hm:health`: `workflow_clarity` checks `.claude/hm/stage-preamble.md` and its two markers only
when a stage command names the file, so an a7403f2f render (inline preamble, no file) scores
exactly as it did (AC-004).

## §B — a quiet check

`hm spec_machine check --all` prints one line whenever no gate failed, and a failure payload
prints each error once. On the AC-006 fixtures (`tests/fixtures/light_lane_s3c/check/`):

| Case | a7403f2f chars | now |
|---|---|---|
| clean pass | 50 | 50 |
| weak pass (one dim < 40) | 781 | 127 |
| low pass (`overall` < 60) | 755 | 212 |
| scoring exception, gates pass | 453 | 213 |
| nine failure fixtures, total | 13343 | 4165 (−69%) |

The per-run figure (the SPEC's ≈ −7.0k from a bench replay) is not re-measured here: it depends
on how often a run fails a gate, which the stage 4 bench measures. The spec Step 4 text grew 248
chars on both variants to describe the new output (AC-009, bound +300).

## §C — less paperwork on light

- Execute Step 0 keeps its 980-char head inline, adds the `approval-status` call (the one new
  round trip on each variant) and the routing sentence, and points at `.claude/hm/execute-plan.md`
  for the rest of Step 0 and the Step 0.3 body (Codex: the same two parts inline). The light
  block is one `@hm:light-plan` span; the Step 0.3 heading carries the SPEC's sentence.
- Spec Step 3.5 shows only the minimal schema and points at `.claude/hm/spec-machine-full.md` on
  `lane: full` (Codex: the full schema inline after the minimal one).
- The light PLAN filled from the template with the S9 values is 936 chars after Step 0.1
  (AC-013, bound 1200).

## Carried per run

Instruction text only: what each stage turn carries, plus each `.claude/hm/` file a run Reads
once, with the Read tool's line-number prefix counted at 7 chars a line (stage-preamble 79 lines
→ 5348; execute-plan 96 → 6124; spec-machine-full 66 → 3798).

| Cut | Light run (spec → execute → wrapup) | Full run (5 stage turns) | SPEC estimate (light / full) |
|---|---|---|---|
| A | 3 × −3784 + 5348 = **−6004** | 5 × −3784 + 5348 = **−13572** | −6.3k / −13.9k |
| B | not measured (+248 instruction chars, both) | not measured (+248) | −7.0k / −7.0k |
| C, instructions | −2503 − 1757 = **−4260** | (−2503 + 6124) + (−1757 + 3798) = **+5662** | −3.8k / +4.6k |
| C, artifacts | light PLAN 936 written, read back twice; yaml not measured | — | −3.6k / — |

Measured instruction total: **−10264** on a light run and **−7910** on a full run. With the
SPEC's unmeasured B and artifact estimates added, the light run lands near the SPEC's −20.7k;
the full run is about 1.4k worse than its −16.3k, because the two full-lane Reads cost more than
estimated (C full +5662 against +4.6k).

## Other re-captures

Each has a dated entry in its module:
- `tests/structural/autopilot_gate_golden.json`: the six stage commands, all four arms; nothing
  else moved.
- The synthesize snapshots, via `tests/snapshot/regenerate.py` (66 → 69 files).
- `test_loop_opt_in._LOOP_ON_RECAPTURES`: the six commands plus `stages/execute.md` and
  `stages/spec.md`.
- `tests/fixtures/wrapup_intent_hardening/goldens.json`: the two Claude arms, after checking
  that putting the preamble back reproduces the old hash.
- `test_command_size_budget._ATOMIC_RATCHET`: the six stage commands.
- `test_roundtrip_budget._CLAUDE_ROUND_TRIPS`: execute 25 → 26 (the approval-status call).
- `test_synthesize.test_side_file_count_in_range`: 68 → 71.

Older byte-identity tests that pin text 3c moved now undo the move and compare with their
existing goldens, rather than being re-captured: s3a's typed stages (all 32 arms reproduce the
e7dd6648 bytes once the preamble is put back), s2b's undelegated commands and Codex skills, and
the frozen Claude-arm dispatch lines. `tests/stage_surface.stage_text` expands the three new
pointers in place, so the render tests that read a stage's text see the pre-move order.

Freeze path: `_surface_baseline.main()` refuses because this checkout has no current local
`main` ref. That is the same cause as the known `test_the_recorded_sha_is_base_reachable`
environment failure. `a7403f2f` was checked to be on `origin/main`
(`git merge-base --is-ancestor`). The file was written with the generator's own `build_baseline()`
and serialization (`indent=2, sort_keys=True`) and `render_sha` set to that merge-base, as for s3a.
