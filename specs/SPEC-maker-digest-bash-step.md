---
type: spec
task_slug: maker-digest-bash-step
status: approved
created: 2026-11-23
tags: [correctness, maker, world-model, permissions, claude-code]
test_framework: pytest
interview_rounds: 0
summary: The Claude Maker runs its briefing digest as its first Bash step instead of a `!` injection, so it loads when Claude Code ignores repository skill grants (CLAUDE_CODE_IGNORE_PERSISTED_TRUST).
---

# SPEC — maker-digest-bash-step

## Intent

Maker injects its briefing at skill load with a `!` command. Claude Code checks that command against
permission rules before it runs, and the only rule that matches it is the skill's own
`allowed-tools`. Since Claude Code 2.1.326 a process with `CLAUDE_CODE_IGNORE_PERSISTED_TRUST` set
ignores repository settings, and a repository skill's `allowed-tools` with them. The variable is set
in claude.ai cloud containers, by self-hosted runners started with `--trust-workspace false`, and by
the VS Code extension for a folder the user has not trusted. There the load fails before the model
sees anything:

```
Shell command permission check failed for pattern "!`uv run … hm world_model digest …`": This Bash
command contains multiple operations. The following parts require approval: …
```

0 model turns, $0 (weekly research 2026-11-23, HR-023; reproduced again for this SPEC on Claude Code
2.1.330 with a 0.66.0 render). Without the variable the same render loads. The same SKILL.md under the
user-level skills folder loads with the variable set, so only the repository skill's grant is lost.
The live boundary test from SPEC-maker-digest-session-id builds its env with `bench.agent_env()`, an
allowlist that drops the variable, so it could not see this.

A model-issued Bash call goes through the session's normal permission flow instead: pre-approved by
`allowed-tools` where the grant is honoured, prompted in an interactive default-mode session, allowed
in auto or bypass mode, denied in a headless default-mode run. Prototype on 2.1.330 with the variable
set: default mode, Maker loads (2 turns) and reports the denied digest; `--permission-mode auto`,
the digest runs and its `maker_load` row carries the CLI's session id. Without the variable, default
mode: the digest runs pre-approved by `allowed-tools`, 2 turns, row carries the session id.
`${CLAUDE_SESSION_ID}` is substituted in the skill body, not only in `!` commands (the denied command
in the prototype held the literal id).

## Outcomes

- `/maker` loads in every trust state; the digest's permission follows the session mode.
- `other_session` is still decided from the caller's session id.
- The live boundary test covers the variable.

## In-Scope Scenarios

- S1 (normal): Claude target. The rendered Maker has no `!` line; its digest command is a fenced
  bash block the skill tells the model to run first on every call, whatever the route.
- S2 (unchanged): the Claude digest command keeps SPEC-maker-digest-session-id's contract: session id
  from `${CLAUDE_SESSION_ID}`, home prefix `~`, no shell expansion, and the `allowed-tools` rule is a
  literal prefix (its AC-001 and AC-003 keep passing on the bash block).
- S3 (unchanged): Codex target. Same block and command as today.
- S4 (live, trusted): `claude -p "/maker"` in default mode without the variable runs the digest
  (existing boundary test).
- S5 (live, untrusted): the same with `CLAUDE_CODE_IGNORE_PERSISTED_TRUST=1` reaches the model (≥ 1
  turn, no "permission check failed"), and the digest command with the substituted session id was
  either run (a `maker_load` row with that id) or asked for (a `permission_denials` entry).

## Non-Goals

- Moving Maker to a plugin (user-scope) skill to keep the injection (HR-023 option B). It changes the
  render layout and handle, and whether plugin skills keep their grant in this mode is unverified.
- Rendering the digest grant into user or managed settings. hm does not write outside the project.
- Other skills or stage commands that carry `allowed-tools`. Those grants only save a prompt; they do
  not gate the load.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| Maker SKILL.md size | ≤ 4,689 chars on every target (existing cap) |
| Maker `allowed-tools` | unchanged: `hm world_model:*`, `tail`, `grep`, `printf` |
| digest CLI | unchanged |
| cost | one extra tool turn per `/maker` call (accepted on the HR-023 card) |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the Claude Maker has no injection and runs the digest as a first step
For the Claude target (en and ko configs), no line of the rendered Maker skill starts with `!` and
holds the digest; the digest command appears exactly once, in a fenced bash block, and the sentence
that introduces the block says to run it first on every call, whatever the route. The Codex Maker
renders the same introducing sentence.
- oracle_source: golden. Host behaviour observed on Claude Code 2.1.330 on 2026-11-23: an injected
  command under `CLAUDE_CODE_IGNORE_PERSISTED_TRUST=1` gives 0 model turns, a bash step ≥ 1. The
  phrase is fixed here before the template change.

## Verification

| scenario | mode | test |
|---|---|---|
| S1 | render | AC-001 |
| S2 | render + bash | `tests/render/test_render_maker_digest_session_id.py` (AC-001, AC-003 of SPEC-maker-digest-session-id) |
| S3 | render | same file, AC-002; `tests/render/test_render_world_model_followups.py` AC-007 |
| S4, S5 | integration, live, advisory (`INTEGRATION=1`, `claude` on PATH) | `tests/integration/test_boundary_maker_default_permissions.py` |
| regression | render | `tests/render/test_render_maker_front_door.py` (fail-soft chain, `allowed-tools`, size cap) |

S4 and S5 are not bound to an AC: they need a signed-in `claude` CLI, and `hm check` counts a
skipped test as a failure.

## Open Questions

none

## Refinement Decisions

- Approval (DRI, 2026-11-23): the DRI tapped option A ("첫 단계로 실행") on the HR-023 card in the
  weekly research thread. The SPEC is approved on that; no further card.
- Default (agent): one block and sentence for both targets. The Codex Maker already runs the digest
  as a bash step; sharing it removes a template branch, and "first on every call" keeps the
  `maker_load` count and the Resume fields the injection gave for free.
- Default (agent): keep the Claude `allowed-tools` grant. Where it is honoured it still saves the
  prompt.
- Default (agent): S2's earlier tests keep their names ("injection") and now read the bash block;
  renaming them would orphan SPEC-maker-digest-session-id's `test_ids`.
- Default (agent): SPEC-world-model-followups AC-007's Claude expectation changes from
  `!digest` + fallback line to one `bash:digest`, the Codex shape; "a single digest with a fallback"
  still holds (the chain's `printf` is the fallback).
- Default (agent): the untrusted live arm runs in default mode, the mode the bug showed, and accepts
  a run or a denial of the right command; auto mode depends on the account and model.
- Default (agent): no intent picked. HM-LIGHT-LANE is about cost; this is a load failure.
- Default (agent): spec-validator skipped (1 live AC; `validator: skip`).
