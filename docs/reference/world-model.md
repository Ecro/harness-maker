# World model (Maker) — the front door

> Maintainer reference for the named world-model router. CLAUDE.md keeps a short list of the
> invariants that break most often and links here; this file is the recorded *why*.
> Governing SPECs: `specs/SPEC-world-model-name.md`, `specs/SPEC-world-model-followups.md`,
> `specs/SPEC-maker-front-door-improvements.md`. Release status: on `main`, listed under
> CHANGELOG `[Unreleased]`.

## Purpose

The **world model** is three things the operator otherwise holds in their head: the intent
layer (goals, metrics, questions), project knowledge (facts the code does not show) and task
state. Maker is its one front door — a thin router skill that briefs, starts or resumes work,
records facts and edits goals, and hands every real change to the procedure that already owns
it. It routes; every gate, consent rule and approval of the target stays in force. The work
serves intent `WORLD-INTENT-CLOSED-LOOP` (feedback reaches the next decision without being
re-instructed).

## Naming, rendering, reserved handles (SPEC-world-model-name)

- `harness.yaml` carries `world_model: {name, handle}` (IRR-001). Absent key → `Maker` /
  `maker`, rendered byte-identically to the explicit default (AC-004). Onboarding asks the
  name right after locale; `--ci world_model_name=` / `world_model_handle=` and the
  `--world-model-name` / `--world-model-handle` flags set it non-interactively (IRR-002).
- The handle is the NFKD→ASCII slug of the name (`world_model.derive_handle`). A name with no
  ASCII handle (e.g. 비비) asks for one. `world_model.handle_error` refuses a handle that
  collides with any shipped skill name (`RESERVED_HANDLES`), starts with `hm-`, breaks the
  skill-name grammar, or is too long — without touching `harness.yaml` (AC-006). The model
  validator re-checks at load, so a hand-edited reserved handle is caught too.
- One template, `templates/skills/world-model/SKILL.md.j2`, renders at the user-chosen path
  (IRR-003): `.claude/skills/<handle>/SKILL.md` (Claude Code, and Cursor which reads
  `.claude/skills`) and `.agents/skills/<handle>/SKILL.md` (Codex). Invocation: `/maker`,
  `$maker` (Codex), or addressing it by name ("maker야 …").
- Rename removes the pristine old router skill and keeps an edited one (AC-005). Modular add
  of the world-model skill is refused, so no second router can appear
  (SPEC-world-model-followups AC-011). Rendered size ≤ 4,500 chars on every target.

## The only entrance (SPEC-maker-front-door-improvements IRR-001/002)

Before this, `intent-layer` and `project-knowledge` triggered themselves from their own
descriptions, so an unnamed goal or fact request could enter by three doors with three
different contexts. Now:

- Both skills render with `disable-model-invocation: true` (Claude Code / Cursor). Codex gets
  `.agents/skills/<n>/agents/openai.yaml` with `policy.allow_implicit_invocation: false`
  (template `skills/_codex/openai.yaml.j2`, a new owned path that ownership and the orphan
  sweep must track).
  Typing `/intent-layer` or `$intent-layer` still runs them.
- Maker reaches them by **Reading their SKILL.md before any write**; the consent rules inside
  are unchanged. Read-only goal and status questions are answered from the briefing — a
  procedure is read only to change something (AC-005).
- `/hm:` stage descriptions end with `Only when typed, or via <Name>, autopilot or /hm:loop.`
  (Codex: `$hm-loop`). This is **advisory** gating: Maker handoff, autopilot advance and
  `/hm:loop` all invoke stages model-side, so a hard flag would break them (AC-003).
- The always-loaded `## World model` pointer (CLAUDE.md / AGENTS.md /
  `.cursor/rules/harness.mdc`, ≤ 400 chars per variant at NAME_MAX/HANDLE_MAX) routes goal,
  metric, fact and status asks to Maker even unnamed or mid-stage; ordinary build/fix asks do
  not go there. It also carries decision capture and the aside rule. The 400 cap supersedes
  SPEC-world-model-followups AC-013's 200. The `## Project knowledge` pointer (≤ 300 chars)
  names the Maker invocation and the procedure file path, because the skill no longer
  triggers on its own (AC-004, AC-014).
- `/hm:help` lists `intent-layer` / `project-knowledge` as `typed only`.

Adding another self-triggering entrance — or making either skill model-invocable again —
reopens the multi-door problem this SPEC closed.

## Routes

| Request | Route |
|---|---|
| empty, "status", "where are we" | Briefing (read-only) |
| "add / fix / investigate X", "research / spec / build X" | Start |
| "continue", "이어서", "resume" | Resume |
| goal, metric, assumption, intent; a project fact | Goals and facts |
| "what next?" | Briefing + 2–4 options; starts no stage |

## Briefing digest (`hm world_model digest`)

`hm world_model digest --root . --session-id "$HM_SESSION_ID"` (`world_model_digest.py`,
SPEC-world-model-followups IRR-001, extended by front-door IRR-003/004).

- **Read-only on world state, ≤ 1,500 bytes (`MAX_BYTES`), always exits 0** with one JSON
  object; failure surfaces as `unavailable`, never as an exit code (followups AC-001/002).
- **Fields**: `tasks` (≤ 5, newest first: `slug`, `next_stage`, `last_stage`, `last_seen`,
  `other_session`, `parked`, `latest_artifact {name, at}`), `more`, `autopilot`, `intents`
  (`counts`, `items`, `active[] {id, metric_id, last, target, gap}` — values mirrored from
  `hm intent status`, `—` when absent), `recent` commits.
- `next_stage` is derived from artifacts, not spans: approved SPEC → REVIEW → APPROVED REVIEW
  → verify marker. Past the 5 s artifact budget (`DEADLINE_S`) a task reports `null`.
- Only `hm/<slug>` task worktrees are listed (`worktree.enabled`). Root resolves to the base,
  so the digest reads the base ledger from any worktree.
- **`parked`**: RESEARCH is the task's only artifact, its frontmatter `created` is older than
  7 days (`PARK_DAYS`), and there is no commit beyond base. Parked tasks sort last. An absent
  `created` is **not** parked — unknown is never parked.
- **Trim order over the cap**: drop `recent` → intents beyond 3 → tasks down to 3 →
  `last_seen`/`last_stage` → `latest_artifact`. **`other_session` is never dropped**: Maker
  reads its absence as "unknown, ask once", so dropping it would cost a question on every
  resume. A new field must slot into this order (or be cheaper than everything above it), or
  the cap starts cutting what Resume depends on.
- **`maker_load`**: each run appends `{ts, event: "maker_load", session_id}` to
  `.claude/observability/world-model.jsonl` — no request text, best-effort (IRR-004). Measured
  at the digest so Maker use is countable on every runtime, including those without hooks.

## Injected command and `allowed-tools`

Claude Code injects the briefing at skill load with `!`:

```
<hm> world_model digest --root . --session-id "$HM_SESSION_ID" 2>/dev/null | tail -n 1 | grep '^{.*}$' || printf '{"unavailable":"digest"}\n'
```

where `<hm>` = `uv run --with <plugin path> hm`. The chain yields exactly one JSON line even
when the digest fails mid-output (AC-010).

- **Why no `{ …; }` group**: a permission matcher splits the command on `|` / `||`, and a
  piece starting with `{` matches no rule, so a grouped fallback would prompt (or fail) on
  every load.
- **Why `world_model:*`, not `hm *`**: frontmatter `allowed-tools` is
  `Bash(<hm> world_model:*)`, `Bash(<hm> autopilot narrow:*)`, `Bash(tail:*)`,
  `Bash(grep:*)`, `Bash(printf:*)`. A bare `Bash(uv run:*)` pre-approved any `uv run`
  (REVIEW 24451777); `hm *` still pre-approved every `hm` verb (confirm-1). The scope is the
  two verbs Maker actually runs.
- Codex runs the same command as a bash block (no `allowed-tools`). Cursor `!` support is
  unverified; the skill tells the model to run the command itself when no JSON appears.

## Start → scope (`hm autopilot narrow`, IRR-005/007/008)

Maker picks the end stage from the ask (research cues → research; spec cues → spec;
build/만들어/고쳐 → full pipeline; unclear → research) and names entry and end point in one
route line. A research-only ask enters research, never spec (AC-007). While autopilot is
active Maker runs `hm autopilot narrow --until <end> --root . --session-id "$HM_SESSION_ID"`
on every ask (`wrapup` for the full pipeline). Also available as
`harness-maker autopilot narrow --until <stage>`. IRR-005 reverses PLAN-world-model-name
ADR-008 ("routes only"): the router now changes autonomy state, so the contract is narrow.

**`narrow` (`autopilot.narrow`) — invariants:**

- **Never arms, never widens.** Base = `restore_pipeline` if set, else `pipeline`; it writes
  `pipeline = base[..end]` and `restore_pipeline = base`. Recomputing from the saved armed
  pipeline means a second narrow can only select a prefix of what was armed (AC-009).
- Never changes level, `created_at` or session.
- **No-op cases** (exit 0, JSON `reason`, nothing written): no marker, foreign/stale/invalid
  marker, level `gated` (every boundary halts at kill_switch, so the restore branch could never
  fire and the write would only leave a latent `restore_pipeline`), stage not in the armed
  pipeline, pipeline already ends there, or the marker changed during the update
  (byte-identity write).
- **Undo path**: on a narrowed marker, `--until <armed end>` — or `--until wrapup` when the
  armed pipeline lacks wrapup — restores the armed pipeline. Only the literal `wrapup` counts
  as the absent-stage undo; a typo or invented stage leaves a deliberate narrowing alone.

**Restore at the boundary** (`autopilot_caps`, `autopilot.restore_narrowed`): at the narrowed
end the boundary restores the armed pipeline and reports `narrow_end: true` instead of
clearing the marker (AC-008), so the session stays armed for its next run. A skipped restore
names its cause: `no_marker`, `not_narrowed`, `superseded` (a newer narrow won), `invalid`,
`raced` (two byte-identity misses).

**Marker field `restore_pipeline`** (IRR-008): optional `list[AtomicStage] | None` on
`AutopilotMarker`; `None` = not narrowed, the absent-case default that keeps pre-upgrade markers
valid under `extra="forbid"`. **Every `.hm-autopilot*` reader must accept it** — the same rule
as the loop-marker header in [`multi-session-worktree.md`](multi-session-worktree.md): a reader
that parses the marker on its own and rejects unknown keys turns every narrowed session into an
"invalid marker".

## Resume, decision capture, mid-stage aside

- **Resume** names the task's `latest_artifact` and its time before entering `next_stage`. A
  missing or null artifact → "no artifact recorded" plus a listing of `work-docs/` / `specs/`
  files. A missing `other_session` is "unknown" → ask once. Resume first runs
  `narrow --until wrapup` to undo a leftover narrowing.
- **Decision capture** (AC-016): a decision or scope change made in conversation about an
  in-flight task is written to its most downstream artifact (PLAN, else SPEC, else RESEARCH)
  **before replying** — otherwise a pause loses it, and the digest's `latest_artifact` is what
  makes it findable again (AC-015).
- **Mid-stage aside** (AC-017): opens `<Name> —`, at most 6 lines; decisions recorded as
  above; new work goes under `## Queued asks` in that artifact and is offered at the stage's
  STOP — never started mid-stage; ends with one `↩ <stage> · <step>` line and the stage
  continues.

## memory_retrieve (same release, IRR-006)

The stage warm tier changed alongside Maker: one 8,192-byte cap for the whole output; lexical
hits first; the count floor (max 3 high-recurrence failures) only fills slots left when
eligible lexical hits < k; a cap-dropped lexical hit is never re-admitted as floor; each dated
entry shows only its newest dated bullet, undated entries their first paragraph; the fenced
topic is clipped to 200 codepoints. `--floor-entry-bytes` / `--floor-byte-cap` were removed
(AC-013).

## Which tests pin what

| Test | Pins |
|---|---|
| `tests/render/test_render_world_model.py` | render path, absent-key default, rename sweep, pointer in every always-loaded variant, onboarding order, `--ci` / flag forwarding, configure dimension (SPEC-world-model-name) |
| `tests/render/test_render_world_model_followups.py` | router briefs from one digest, resume fields, localized errors, modular add/remove refusal, name round-trip, router name / Codex token, help listing (SPEC-world-model-followups) |
| `tests/render/test_render_maker_front_door.py` | only-entrance flags, Codex `openai.yaml`, stage description gate, pointer routing and caps (400 / 300), help `typed only`, procedure reads, ask → end stage, injected command fail-soft and `allowed-tools`, Maker ≤ 4,500 chars, decision capture, aside |
| `tests/unit/test_world_model_digest.py` | the followups digest contract: byte cap, exit 0, `next_stage` from artifacts, ordering and cap, base resolution |
| `tests/unit/test_maker_digest.py` | active intents within the cap, worst-case floors, trim order keeping `other_session`, `maker_load` row (incl. no id / unwritable dir), `parked` last, `latest_artifact` |
| `tests/unit/test_autopilot_narrow.py` | stop and restore, never widens, pre-upgrade marker validates, double narrow, undo path (armed end and absent `wrapup`), unknown stage keeps a narrowing, distinct restore causes, `superseded` |
| `tests/unit/test_memory_retrieve_bounded.py` | 8,192-byte cap (incl. huge Hangul body / topic), lexical-first, floor fills only empty slots |

## Open item

**Permission-matcher acceptance of the ungrouped chain is unverified.** The `| tail | grep ||
printf` form was chosen so each piece matches an `allowed-tools` rule, but whether Claude
Code's matcher actually pre-approves the injected `!` line without a prompt can only be seen in
a live session after release (the rendered harness runs the released plugin cache). Until then,
a prompt or a `{"unavailable":"digest"}` briefing on load is the expected failure signal.
