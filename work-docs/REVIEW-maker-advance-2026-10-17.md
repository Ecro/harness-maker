---
type: review
task_slug: maker-advance
created: 2026-10-17
spec: "[[SPEC-maker-advance]]"
plan: "[[PLAN-maker-advance]]"
summary: "One code-reviewer pass over the Advance rule, the hand-off lines, the digest fix and the live AC-005 test; 9 findings, 6 accepted, 3 rejected"
---

# REVIEW — maker-advance

Reviewer: code-reviewer (read-only), against SPEC-maker-advance (approved 838897bf) and
PLAN-maker-advance, after the live AC-005 run passed (exempt: 1 commit on main, no push; unstamped:
0 commits).

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P1 | templates/claude-md/*.md.j2:7, commands/hm/help.*.md.j2, README.md:385 | Always-loaded CLAUDE.md, `/hm:help` and README still said the user types every next stage | accepted | Fixed: each now names Maker's Advance rule (world-model name from config) |
| F2 | P1 | tests/integration/test_maker_advance_live.py `_run` | A crash, auth failure or budget stop also lands 0 and passed the unstamped case | accepted | Fixed: the CLI result must exist, not be an error, and be `success`; the docstring says the unstamped case does not isolate which stop fired |
| F3 | P2 | tests/integration/test_maker_advance_live.py seed | `lane: light` sent the exempt run through the light check, not Step 6 review | accepted | Fixed: both seeds use `lane: full` |
| F4 | P2 | tests/integration/test_maker_advance_live.py prompt | The prompt pre-answers Maker's other-session ask | rejected | That ask is a pre-existing Resume rule outside this SPEC; the operator's pre-answer is legitimate input, and the docstring now says so |
| F5 | P2 | src/harness_maker/world_model_digest.py next_stage | Any REVIEW means wrapup, so a Resume after an interrupted execute enters wrapup with accepted findings maybe unfixed | rejected | SPEC-maker-advance AC-006 (approved) pins `wrapup` for every REVIEW status; wrapup's `hm check` still blocks `unresolved` findings and failing tests. Raised to the DRI as a follow-up |
| F6 | P2 | specs/SPEC-world-model-followups.machine.yaml, specs/SPEC-hm-light-lane-s3a.machine.yaml | Golden-row edits invalidate the approval stamps | rejected | Already re-stamped after DRI cards: followups 61d10c70, s3a a29b1fff |
| F7 | P2 | tests/integration/test_maker_advance_live.py assertions | One commit of any content satisfied the exempt case | accepted | Fixed: `main:calc.py` must contain `def add` |
| F8 | P2 | tests/unit/test_light_lane.py digest test | The test name still claims it separates checked from unchecked light tasks | accepted | Docstring states that any REVIEW means wrapup since 0.64.0; the name is kept because SPEC-hm-light-lane-s3a lists it as a test id |
| F9 | P2 | tests/integration/test_maker_advance_live.py `_run`, `_bench` | The timeout killed only the direct child; `sys.modules["bench"]` leaked | accepted | Fixed: own process group killed on a 1,800 s timeout; the module entry is popped |

Out of scope, noted for phase 2: `docs/ARCHITECTURE.md:138` lists six stages; `io_utils.py:260`
points at `/hm:loop` and autopilot; HOW-IT-WORKS §4 needs the rewrite already on the backlog.
