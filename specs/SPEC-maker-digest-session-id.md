---
type: spec
task_slug: maker-digest-session-id
status: approved
created: 2026-11-16
tags: [correctness, maker, world-model, permissions, claude-code]
test_framework: pytest
interview_rounds: 0
summary: Maker's injected briefing command takes the session id from the host's skill substitution instead of a shell variable, so Claude Code's permission check can read the whole command and Maker loads in default permission mode again.
---

# SPEC — maker-digest-session-id

## Intent

Maker injects its briefing at skill load with a `!` command. That command passes
`--session-id "$HM_SESSION_ID"`. Claude Code 2.1.325 checks an injected command before it runs
and refuses one that holds a shell variable: `claude -p "/maker"` in default permission mode ends
with `Shell command permission check failed … A variable in this command can't be checked before it
runs`, 0 model turns, and the skill body never loads (weekly research 2026-11-16, HR-022;
reproduced again for this SPEC on 0.65.4, Side preset, Claude target). The bench runs with
`--dangerously-skip-permissions`, so it never saw this. Maker is the only front door to the intent
layer, project knowledge and task state, so a Maker that does not load in the default mode is a
broken product for a new user.

With `"${CLAUDE_SESSION_ID}"` in its place the same run loads the skill and briefs (1 turn).
`${CLAUDE_SESSION_ID}` is a skill string substitution: the host replaces it with the session id before
the command reaches the shell or the permission check. The `maker_load` row that run wrote carries the
CLI's own session id. That it equals what `HM_SESSION_ID` holds is inferred from the hook code, not
observed: the SessionStart hook stores the payload id unchanged when it is UUID-shaped, which is what
Claude Code issues. So `other_session` is decided as before. The `| tail | grep || printf` chain was accepted
under `allowed-tools` in both runs, which settles the "unverified ungrouped chain" note in CLAUDE.md.

A second variable sits in the same line on every plugin-cache install. The plugin path is rendered
with a `$HOME` prefix (`_portablize_ref`), so the real command is
`uv run --no-project --with $HOME/.claude/plugins/… hm world_model digest …`. The research
reproduction ran from a checkout outside the home directory and never rendered it; this task's first
render test did. Tried live with the session token already in place: the load still fails, now with
`This Bash command contains multiple operations. The following part requires approval: uv run
--no-project --with $HOME/… hm world_model digest …`, 0 turns. The `allowed-tools` rule that names the
same `$HOME` path does not match a command that holds the variable. Written as `~/…` in both the
command and the rule, the load passes (1 turn, the `maker_load` row carries the CLI's session id).

## Outcomes

- `/maker` loads and briefs in Claude Code's default permission mode.
- `other_session` is still decided from the caller's session id.
- A live check exists that would have caught this, and the docs no longer call the chain unverified.

## In-Scope Scenarios

- S1 (normal): Claude target, plugin under the home directory. The injected line holds no shell
  expansion (home prefix `~`, session id from the host token) and its `allowed-tools` rule is a literal
  prefix of it; the host puts the session id in, the digest gets it, and a task last touched by
  another session shows `other_session: true`.
- S2 (edge): a host that does not substitute `${CLAUDE_SESSION_ID}`. The shell expands it to an empty
  string, the digest treats that as no id, `other_session` is null (Maker asks once), exit 0, one JSON
  line.
- S3 (unchanged): Codex target. Its Maker runs the digest as a model-issued shell command, where a
  variable is allowed and no host substitution exists; the command still passes `"$HM_SESSION_ID"`.
- S4 (live): `claude -p "/maker"` with no permission flag on a fresh render has at least one model
  turn and the `maker_load` row carries the CLI's session id.

## Non-Goals

- Rendering `Skill(<handle>)` into `permissions.allow` for unattended `/loop /maker` runs. It widens
  what runs without a prompt and is a separate decision.
- Stage commands that pass `"$HM_SESSION_ID"` or a `$HOME` plugin path in a model-issued Bash call,
  and the `$HOME`-form rules in `settings.json` `permissions.allow`. Those are ordinary tool calls
  under the normal permission flow: a rule that does not match costs a prompt, not a failed load.
  Whether those rules match at all is logged as a follow-up for the weekly research log.
- A minimum host version in `plugin.json`.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| Maker SKILL.md size | ≤ 4,689 chars on every target (existing cap) |
| Maker `allowed-tools` | same scope: `hm world_model:*`, `tail`, `grep`, `printf` (the Claude rule's home prefix is written `~`) |
| digest CLI | unchanged: `--session-id` stays optional, empty means none |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the Claude injection holds no shell expansion
For the Claude target (en and ko configs, plugin path under the home directory), the single `!` line
of the rendered Maker skill passes `--session-id "${CLAUDE_SESSION_ID}"`, and once that host token is
removed the line holds no `$name`, `${…}`, `$(…)` or backtick. The `world_model` entry of
`allowed-tools`, without its `:*`, is a literal prefix of that line.
- oracle_source: golden. The refusal rule, the rule matching and the substitution are the host's
  behaviour, observed on Claude Code 2.1.325 on 2026-11-16 (0 turns with either variable, 1 turn with
  `~` and the token).

### AC-002: the Codex command is unchanged
For the Codex target, the Maker skill's digest command is byte-identical to today's, with the `hm`
prefix normalised to `<hm>`.
- oracle_source: golden. The row was read from the render of origin/main 0ccfcf09 before any change.

### AC-003: the substituted id decides other_session
The rendered Claude injected line is run under bash against a repository whose task `demo` was last
touched by session `s1`, with `${CLAUDE_SESSION_ID}` replaced the way the host does it. Replaced by
`s1` → `other_session` false; by `s2` → true; left unreplaced with no such shell variable → null. Every
run exits 0 with exactly one JSON line.
- oracle_source: golden. The expected values follow from SPEC-world-model-followups AC-004's rule
  (same id → false, different → true, missing → null), written before this change.

## Verification

| scenario | mode | test |
|---|---|---|
| S1 | render | AC-001, AC-003 |
| S2 | render + bash | AC-003 (unreplaced row) |
| S3 | render | AC-002 |
| S4 | integration, live, advisory (`INTEGRATION=1`, `claude` on PATH) | `tests/integration/test_boundary_maker_default_permissions.py` |
| regression | render | `tests/render/test_render_maker_front_door.py` stays green (fail-soft chain, `allowed-tools`, size cap) |

S4 is not bound to an AC: it needs a signed-in `claude` CLI and costs about a cent, and `hm check`
counts a skipped test as a failure. It runs with the other boundary tests (`release.yml`
`boundary-advisory`, where it skips without a `claude` binary) and by hand before a release.

## Open Questions

none

## Refinement Decisions

- Approval (DRI, 2026-11-16): the DRI picked "둘 다 고치기" on the weekly research card for HR-021 and
  HR-022, under the standing instruction of 2026-11-10 13:26Z ("나에게 묻지말고 이제부터는 모두 너의
  추천대로 wrapup 후 push to. Main까지 진행해"). The SPEC is approved on that; no further card.
- Default (agent): `${CLAUDE_SESSION_ID}` over a session-id file read by the digest. It is one token in
  the template, needs no new file or reader, and was verified live. A file would add a writer, a
  reader and a staleness rule (the SessionStart hook's env file is per session and its path is not
  known to a subprocess). Cost to undo: one template line.
- Default (agent): the Codex variant keeps `"$HM_SESSION_ID"`. Codex has no `!` injection and no
  `${CLAUDE_SESSION_ID}`; changing it would lose its session id.
- Correction (agent, during execute): the first draft named the session variable as the only cause.
  AC-001's test failed on `$HOME` in the rendered plugin path, and a live run confirmed that form
  fails too. The Claude Maker now writes the home prefix as `~` in its `hm` prefix (the injected line,
  `allowed-tools` and the "`hm` below means" line together, so the rule stays a literal prefix of the
  command). `~` is as portable across machines as `$HOME`. A path outside the home directory is
  unchanged. The SPEC was re-approved on the standing instruction above. Cost to undo: one template
  expression.
- Default (agent): no irreversible decision. `allowed-tools`, the digest CLI and the permission
  surface are unchanged; only where the id comes from moves.
- Default (agent): no intent picked. HM-LIGHT-LANE is about cost; this is a load failure.
- Default (agent): spec-validator skipped (3 live ACs; `validator: skip`).
- Checked after review (2026-11-16): a plugin-cache-shaped path
  (`~/<15 chars>/cache/harness-maker/harness-maker/0.65.4`) makes the frontmatter `allowed-tools`
  value fold across two lines inside the rule. A live default-mode `/maker` on that render loaded,
  wrote its `maker_load` row and reported no denial, so the fold is read as one rule. Seen on the same
  render and not part of this task: that Maker skill is 4,806 chars (4,891 bytes), over the 4,689-char cap the render
  tests check with a short pinned path.
- Found while writing the docs: `docs/reference/world-model.md` kept an "Open item" saying the chain's
  acceptance is unverified. It is replaced by what the two live runs showed.
