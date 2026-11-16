---
type: review
task_slug: maker-digest-session-id
created: 2026-11-16
spec: "[[SPEC-maker-digest-session-id]]"
plan: "[[PLAN-maker-digest-session-id]]"
rounds: 2
reviewers: [code-reviewer]
summary: "Two code-reviewer rounds: 7 findings (4 minor, 3 nit), then 2 (1 minor, 1 nit) and 1 note. Eight accepted and fixed, one settled by a live run; nothing unresolved."
---

# REVIEW — maker-digest-session-id

Two code-reviewer rounds on the uncommitted diff. Round 1 raised 7 findings, none critical or
major; round 2 confirmed all seven resolved and raised 2 more plus one note. The reviewer
mutation-tested the template in a scratch copy: reverting the session token, keeping `$HOME`,
dropping the quotes and dropping the braces were all killed in round 1; "Codex also given `~`"
survived round 1 and is killed after F1's fix. The cross-model second opinion was requested once
and skipped (`CLI not installed: codex`). No `Do not change` path was crossed: `world_model.py`,
`world_model_digest.py`, `hooks/sessionid_envfile.py` and
`tests/render/test_render_maker_front_door.py` are untouched.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | minor | tests/render/test_render_maker_digest_session_id.py (AC-002) | No test pinned S3's "Codex keeps `$HOME`": AC-002 normalised the `hm` prefix away, so a template that gave Codex `~` passed everything. Fix: AC-002 asserts ` --with $HOME/` in the Codex `hm` prefix | accepted | SPEC S3, PLAN ADR-002 |
| F2 | minor | tests/integration/test_boundary_maker_default_permissions.py; SPEC Intent | The live evidence used a short checkout path. A plugin-cache path makes `yaml.safe_dump` fold the `allowed-tools` value inside the rule, a shape no test or live run had exercised | accepted | Settled by a live run, not a code change: a render from `~/<15 chars>/cache/harness-maker/harness-maker/0.65.4` (folded rule) loaded in default mode, wrote `maker_load` and reported no denial. Recorded in SPEC Refinement Decisions |
| F3 | minor | work-docs/PLAN-maker-digest-session-id.md | The PLAN described one template token and never recorded the `$HOME` to `~` rewrite; its risk line was wrong. Fix: summary, phase line and ADR-005; the SPEC Constraints row says "same scope" | accepted | PLAN is the scope record |
| F4 | minor | docs/reference/world-model.md; SPEC Intent | "Equals the id `HM_SESSION_ID` holds" was stated as observed. It is inferred from the hook code and holds for UUID-shaped ids. Fix: both texts label it as inferred and name the id-shape condition | accepted | `loop_marker.sanitize_session_id` |
| F5 | nit | docs/reference/world-model.md | The new paragraph split the code block from its "where `<hm>` =" line, and two places still said Codex runs "the same command". Fix: paragraph moved, wording corrected | accepted | style |
| F6 | nit | tests/render/test_render_maker_digest_session_id.py (`_EXPANSION`) | The regex missed positional and special parameters (`$1`, `$?`, `$@`) and `$[…]`. Fix: widened; a `$1` mutant is now killed | accepted | SPEC AC-001 |
| F7 | nit | tests/render/test_render_maker_digest_session_id.py (AC-003) | The unreplaced-token row never asserted the token was in the command, so it passed on the unfixed template. Fix: the assertion runs for every row | accepted | SPEC AC-003 |
| G1 | minor | specs/SPEC-maker-digest-session-id.md | The follow-up note gave a byte count as chars. Fix: 4,806 chars (4,891 bytes) | accepted | cap is `len(text)` |
| G2 | nit | work-docs/PLAN-maker-digest-session-id.md | Rollback named one template line where two expressions changed; ADR-005 sat before ADR-004. Fix: both | accepted | style |
| G3 | nit | tests/integration/test_boundary_maker_default_permissions.py (docstring) | From a checkout outside the home directory the project `settings.json` rule also matches the absolute command, so the live test proves the variable is gone but not that the skill's own grant matches. Fix: the docstring says so | accepted | reviewer note |

Left for a follow-up, outside this task: with a real plugin-cache path the rendered Claude Maker is
4,806 chars, over the 4,689-char cap that the render tests check under a short pinned path. It was
about 4,813 before this change. Reported to the weekly research log.

The approval stamp on this SPEC reads `approved_by: Claude`: the agent stamped it on the DRI's
card choice ("둘 다 고치기") and the standing instruction of 2026-11-10, including the re-approval
after the `$HOME` finding. The SPEC's Refinement Decisions say so.
