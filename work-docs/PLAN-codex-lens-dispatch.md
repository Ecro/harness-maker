---
type: plan
task_slug: codex-lens-dispatch
status: complete
created: 2026-08-16
tags: [harness-maker, plan, python, jinja2, codex, render-gate, subagent-dispatch]
interview_rounds: 4
adrs: 8
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Render Codex-native spawn_agent/request_user_input instead of Claude-only Task(/AskUserQuestion"
---

## 🎯 Executive Summary

**TL;DR** — Every Codex-target stage skill harness-maker renders carries Claude Code's
`Task(subagent_type=…)` call syntax verbatim. Codex CLI has no `Task` tool, so every
subagent dispatch on that target is an instruction the runtime cannot execute. Replace it
with Codex's native `spawn_agent`, do the same for `AskUserQuestion` → `request_user_input`,
and lock both with a structural gate that reads the render blueprint's output paths rather
than a hand-maintained file list.

**What / Why** — Measured on `~/strange_chess` (preset `Side`, `targets: [claude-code, codex]`):

| Claude-only call | Occurrences in rendered `.agents/skills/hm-*/SKILL.md` |
|---|---|
| `Task(` | **25** (`hm-review` alone: 15) |
| `AskUserQuestion` | **7** |
| `Skill(` | **0** — already correctly branched |

The observable failure: a Codex `/hm:review` run produced **zero** files under
`.claude/observability/.hm-lens-results/` (the directory did not exist), so
`hm lens_coverage check` reported `missing: [design, functionality, robustness, consistency]`
— exactly `mandatory_lenses("Side")` — and `blocks_approval: true`. The review was
structurally unapprovable, and the operator-facing explanation blamed the coverage CLI
rather than the dead dispatch.

**Key decisions** — ADR-001 (scope = all three Claude-only call surfaces),
ADR-002 (literal call + intent sentence), ADR-003 (single dispatch macro, one owner),
ADR-004 (gate derives from output path, not a file list), ADR-005 (live e2e as
`INTEGRATION=1` advisory with a runtime-event oracle, not a CI gate), ADR-006 (lens-brief
baseline is a committed fixture, not a git revision), ADR-007 (**withdrawn** — its
premise was probed and unsupported), ADR-008 (Phase 3 is one template block; the brief quote
policy is left open).

**Estimated impact** — 7 template files hold the `Task(` call sites; 13 hold
`AskUserQuestion`. One new partial, one new structural test, one new integration test.
No Python behaviour change outside the render context; no schema change.

## 📚 Prior Work

- `[wiki:architecture] review-axis-seven-lenses-and-the-grade-fail-open` records the
  identical class one layer down: *"On the codex target every new mandated call rendered as
  an inert `!` line — unbranched `!` lines are prose there, so the coverage verdict, the tag,
  the disposition and the grade were all unwired on that target while every render test
  passed."* The prescribed remedy there was per-call-site
  `{% if is_codex %}Bash("…"){% else %}!…{% endif %}`. This PLAN is the same defect for
  **subagent dispatch** instead of **shell calls** — and the fact that it survived a fix
  aimed at the shell-call half is itself the evidence for ADR-003/ADR-004.
- CLAUDE.md, *렌더 컨텍스트 플래그는 출력 경로에서 파생시킬 것 (`is_codex`)*: the flag was
  once hardcoded `False` for wrapper-level partials, so `{% if is_codex %}` branches read
  correctly in source and never fired. `_is_codex_output` fixed the derivation and
  `tests/structural/test_is_codex_matches_output_path.py` guards it. That gate proves the
  **flag** is right; it says nothing about whether a call site consults the flag at all.
  Phase 4 covers the second half.
- CLAUDE.md 체크포인트 2: *"게이트를 만들 때는 자기가 고치던 산출물에만 범위를 맞추지 말 것 —
  같은 결함이 자기 수정을 피해 살아남는다."* The `Task(` call sites are spread across
  `templates/stages/`, `templates/commands/hm/loop.md.j2` and
  `templates/skills/second-opinion-gate/`; a gate scoped to `stages/` would miss two of them.
- CLAUDE.md 체크포인트 8: an integration boundary that unit tests cannot reach needs one
  real execution. ADR-005 applies it here.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Scope of the Claude-only call surface | Scope boundaries | Fix `Task(` only, or also `Skill(` / `AskUserQuestion`? | A. `Task(` only / B. `Task(`+`Skill(` / C. all three | **C — all three** | Live probe then showed `Skill(` already renders 0 on Codex, so it becomes gate-only; `AskUserQuestion` has a confirmed Codex counterpart | ADR-001 |
| 2 | Rendered dispatch shape | Contract shape | Literal call syntax, tool-agnostic prose, or both? | A. literal + intent sentence / B. literal only / C. prose only | **A — literal + intent sentence** | Hedges the observed v1/v2 `spawn_agent` schema divergence: a drifted parameter name stays recoverable because the intent survives | ADR-002 |
| 4 | Plugin's own `commands/*.md` surface (46 `AskUserQuestion`, ships to Codex, invisible to a blueprint gate) | Scope boundaries | Extend gate+fix, gate only, or record as out-of-scope residual? | A. gate + fix / B. gate only / C. residual ADR | **A — gate + fix** | Raised by validator pass 1 as a critical; it is the new-install entry point and the exact miss CLAUDE.md 체크포인트 2 already records once | ADR-007 |
| 3 | Verification depth | Testing depth | Structural gate only, gate + live e2e, or also re-render `~/strange_chess`? | A. gate + live e2e (1 case) / B. gate only / C. gate + e2e + strange_chess / D. end interview | **A — gate + live e2e** | Render-grep proves an instruction is present, never that the runtime honours it — the exact reason this bug shipped | ADR-005 |

## 📐 Architecture Decision Records

### ADR-001: Scope covers all three Claude-only call surfaces, but `Skill(` is gate-only
**Status:** Accepted (2026-08-16, via /hm:plan interview)
**Context:** `Task(` is the call surface with a measured runtime failure. `Skill(` and
`AskUserQuestion` are the same class — Claude Code tool names emitted into a runtime that has
different ones — and a fix scoped to the one that happened to be noticed leaves the others to
be rediscovered separately.
**Decision:** All three are in scope for the **gate**. `Task(` and `AskUserQuestion` also get
rendering work; `Skill(` gets none, because measurement showed it already renders 0 times on
the Codex target (`stage_end_summary.md.j2:22` guards the autopilot-advance block with
`{% if is_codex is defined and not is_codex %}`, and `plan.md.j2:291` has its own branch).
**Consequences:**
- ✅ One gate covers the whole class, so the next Claude-only call name added to a template
  fails at test time rather than at a user's `/hm:review`.
- ✅ No speculative rewrite of a surface that already works.
- ⚠️ `AskUserQuestion` work expands the diff beyond the reported symptom; Phase 3 is separable
  and can be reverted alone if it destabilises the interview stages.
**Rejected alternatives:**
- `Task(` only — Rejected because the gate would then have a shape ("no `Task(` on Codex")
  that invites exactly the "fixed my own symptom" scoping CLAUDE.md 체크포인트 2 warns about.
- Rewrite `Skill(` "for parity" — Rejected because it renders nothing today; adding a branch
  to a correct call site is churn with a regression surface and no benefit. This is the
  `sessionid_envfile`-in-Cursor lesson: shipping a mechanism that provably cannot act.
**Source:** Interview #1

### ADR-002: Codex dispatch renders as a literal `spawn_agent(...)` call **plus** an intent sentence
**Status:** Accepted (2026-08-16, via /hm:plan interview)
**Context:** Two `spawn_agent` schemas were observed in Codex CLI 0.147.0. A live
`codex exec --sandbox read-only` probe reported parameters
`agent_type, fork_context, items, message, model, reasoning_effort, service_tier`. The shipped
binary also contains a `multi_agents_v2` handler set (`spawn.rs`, `wait.rs`, `list_agents.rs`,
`send_message.rs`, `followup_task.rs`, `interrupt_agent.rs`) whose prose describes
`task_name` and `fork_turns`. `list_agents` was **not** exposed in the `exec` session that
answered. A single hardcoded argv shape therefore risks being wrong in a session type we did
not probe.
**Decision:** The **intent sentence is normative** and the literal call is an *example* of it,
in that order — a sentence naming the agent role and the job in runtime-neutral words
("delegate this to the project's `code-reviewer` agent, passing the brief below verbatim, using
your session's subagent tool"), followed by
`spawn_agent(agent_type="code-reviewer", message="<brief>")` as the concrete form and an
explicit instruction to follow the tool's live schema if the parameter names differ.
**Consequences:**
- ✅ A pinnable golden string exists, so the gate can assert the call is present and shaped.
- ✅ Schema drift degrades to "model reads the intent and adapts" rather than a hard failure.
- ⚠️ Slightly longer rendered prose on the Codex target; charged against the surface budget.
- ⚠️ **Only the `codex exec` schema is verified.** Stage skills also run in interactive Codex
  sessions, where the `multi_agents_v2` handlers (`task_name`/`fork_turns`) may be the exposed
  set. Phase 5's e2e covers `exec` only; the interactive half is an accepted residual risk
  recorded in R1, not a claim. Ordering intent before literal is precisely what keeps that
  residual from reproducing the current silent failure. *(Raised by the cross-model second
  opinion as `[ADR-002/R1]`; accepted.)*
**Rejected alternatives:**
- Literal only — Rejected because an unrecoverable wrong parameter name reproduces exactly
  today's failure mode: an instruction that cannot execute, silently.
- Prose only — Rejected because Codex's own `spawn_agent` tool prompt says *"Do not spawn
  sub-agents unless the user or applicable AGENTS.md/skill instructions explicitly ask for
  sub-agents, delegation, or parallel agent work."* A vague instruction risks being read as
  not-explicit and absorbed into local execution — which is the current failure, restated.
**Source:** Interview #2

### ADR-003: One dispatch macro owns every rendered call site
**Status:** Accepted (2026-08-16, via /hm:plan interview)
**Context:** The `Task(` call sites live in 7 template files across three directories
(`stages/`, `commands/hm/`, `skills/`). Per-call-site `{% if is_codex %}` branching — the
remedy the previous round of this class prescribed — is what left 25 of them unbranched.
**Decision:** Introduce a single Jinja macro partial
(`templates/agents/_partials/dispatch.md.j2`) with these exact signatures:

```jinja
{% macro dispatch(is_codex, agent, description, brief) %}
{% macro ask_user(is_codex, questions) %}
```

`questions` is a list of `{id, header, question, options: [{label, description}], multi_select}`
mappings, so the Codex arm can emit `request_user_input`'s full payload and the Claude arm can
emit `AskUserQuestion`'s (including `multiSelect`, which Codex's schema lacks and the Codex arm
drops with a one-line note in the rendered text). Every call site calls the macro and **passes
`is_codex` explicitly**.
**Consequences:**
- ✅ Adding a Codex quirk later is one edit, not 25.
- ✅ The gate has a single thing to assert about, and a new call site that bypasses the macro
  is caught by the Phase 4 gate rather than by a reviewer's memory.
- ✅ **The macro never reads `is_codex` from context.** Jinja's `{% import %}` does not pass
  caller context unless imported `with context`; a macro that read the flag internally would
  silently take the Claude arm in every production render while an isolated unit test passed.
  That is verbatim the `is_codex`-hardcoded-False failure this repo already shipped. An
  explicit parameter makes the omission a Jinja `UndefinedError`, not a silent wrong branch.
  *(Raised by the cross-model second opinion as `[ADR-003/Phase 1]`; accepted.)*
- ⚠️ The brief reaches the macro as an opaque Python-supplied string (`{{ d.brief }}` from
  `conditional_router.LENS_DISPATCH`), so the macro cannot *edit* it — but it **quotes** it,
  into a `spawn_agent(message=…)` argument on one arm and a `Task(prompt=…)` argument on the
  other. That quoting/escaping seam is the real hazard: an embedded `"` or the existing
  `\n\n` separator mangled by the macro silently collapses four lenses into one voice. Phase 1
  captures the briefs as a golden fixture from `conditional_router.py` and Phase 2 diffs the
  **rendered** briefs against it, which is what catches an escaping defect.
- ⚠️ Every call site gains an `is_codex` argument — more verbose than a context-reading macro.
  Accepted: verbosity that fails loudly beats brevity that fails silently.
**Rejected alternatives:**
- Per-call-site branching — Rejected because it is the approach that produced this bug.
- Macro reads `is_codex` from context (`import … with context`) — Rejected: it works only while
  every caller remembers `with context`, and forgetting it produces the silent wrong branch
  rather than an error.
- `ask_user(purpose)` (the first draft's signature) — Rejected: it has no parameter for
  question text, ids, headers or options, so any implementation would have had to discard the
  existing question payloads or leave call sites unmigrated.
**Source:** Interview #2 (implementation consequence; no separate round)

### ADR-004: The gate derives the Codex surface from the render blueprint's output paths
**Status:** Accepted (2026-08-16, via /hm:plan interview)
**Context:** `tests/structural/test_is_codex_matches_output_path.py` exists because a
hand-maintained flag list went stale. A gate that enumerates "the Codex templates" would
repeat that mistake in a new place, and `commands/hm/loop.md.j2` — which feeds the Codex loop
skill through `codex/loop_skill.md.j2` — is precisely the file such a list would omit
(its path says `commands/hm/`, not `codex/`).
**Decision:** The Phase 4 test builds the render blueprint **once per configuration in a
declared matrix** and, for every `FileEntry` whose output path satisfies
`synthesize._is_codex_output`, asserts the rendered body contains none of `Task(`, `Skill(`,
`AskUserQuestion`. It never names a template. The matrix covers `preset` ∈ {Side, Production}
× `targets` ∈ {[codex], [claude-code, codex]}, plus `dev_mode` both values — the axes that
gate whether a conditional producer renders at all.
**Consequences:**
- ✅ A new Codex output added anywhere is covered the day it is added.
- ✅ Reuses the already-trusted `_is_codex_output` predicate; no second source of truth.
- ✅ **The test asserts its own scanned surface is non-empty** before scanning. A blueprint
  that yields zero Codex entries — a plausible outcome of a `targets` regression or a
  refactor of `_is_codex_output` — would otherwise make the gate pass vacuously, which is
  the R3 failure mode stated as a design property rather than left to review.
  *(Raised by the cross-model second opinion as `[ADR-004/Phase 4]`; accepted.)*
- ⚠️ A legitimate future mention of the literal string `Task(` in Codex prose (e.g. a doc
  paragraph explaining the Claude difference) would fail the gate. Accepted: an explicit
  allowlist entry with a reason is cheaper than a gate that pattern-matches intent.
- ⚠️ The matrix is a hand-declared list of *configurations*, not of files — it can go stale if
  a new axis gates a Codex producer. That residual is smaller than a file list's and is the
  cheapest form available without enumerating the config space.
**Rejected alternatives:**
- Grep the rendered `~/strange_chess` tree — Rejected: it tests one user's harness config, so
  a leak that only appears under `preset: Production` or a different `targets` set is invisible.
**Source:** Interview #1/#3 (design consequence)

### ADR-005: The live Codex e2e is an `INTEGRATION=1` advisory, never a CI gate
**Status:** Accepted (2026-08-16, via /hm:plan interview)
**Context:** The structural gate proves the instruction is present and well-formed. It cannot
prove Codex honours it — and "present but not honoured" is this defect's whole shape. But a
live `codex exec` needs network, a login, and a paid model; making it required would make the
suite fail for reasons unrelated to the change under test.
**Decision:** Add exactly one integration test, guarded by
`pytest.mark.skipif(not os.getenv("INTEGRATION"))`, that runs `codex exec --json` against a
rendered fixture harness, feeding it the **shipped** intent sentence and dispatch line lifted
out of the rendered `hm-review` skill, and asserts on a **tamper-resistant oracle**: an
`item.completed` event whose `item.type == "collab_tool_call"` and `item.tool == "spawn_agent"`,
plus the spawned thread's reply in `item.agents_states[…].message`.

> **Oracle corrected 2026-08-16 — measured, not assumed.** This ADR first specified
> `collab_agent_spawn_begin` / `sub_agent_activity`. Both strings exist in the Codex binary and
> **neither is emitted by `codex exec --json`**; the actual record is `collab_tool_call`.
> Asserting on the assumed names would have produced a test that fails for the wrong reason —
> the same "named a thing the runtime does not have" class this whole task exists to close, one
> layer up. Captured output is in `tests/manual/CODEX_SPAWN_AGENT_PROBE.md`.
>
> **Scope narrowed too.** Driving a full `/hm:review` to produce per-lens result files and a
> `blocks_approval: false` verdict would have made one test depend on seven live sub-agent runs
> and the whole review procedure. The claim that needs live proof is narrower: *the shipped
> dispatch instruction is executable*. That is what is asserted, and it passed — Codex spawned
> the `code-reviewer` role from the rendered instruction and the sub-agent replied.
**Consequences:**
- ✅ The runtime claim is checkable by a human on demand, and the command to check it is
  recorded rather than reconstructed.
- ✅ **The oracle cannot be satisfied by the model narrating a dispatch.** Event-stream records
  are emitted by the Codex runtime, not by the model's text — an assertion on "a subagent was
  actually spawned" phrased any other way is satisfiable by an echo, which is how the current
  bug produced confident prose about work that never happened.
  *(Raised by the cross-model second opinion as `[ADR-005/Phase 5]`; accepted.)*
- ⚠️ Default CI stays blind to a runtime regression. Mitigated by Phase 5's exit criterion
  requiring the test to have been run **once, green, locally** before the PLAN is closed —
  an unrun advisory test is indistinguishable from an absent one.
- ⚠️ The event name is read from a live `codex exec --json` run, **not** from the binary's
  strings. Reading the strings is what produced the refuted `collab_agent_spawn_begin`: the
  symbol exists in the binary and is never emitted. If a future Codex renames the record the
  test fails loudly (not silently), which is the correct direction.
- ⚠️ **Every Codex-internal claim in this PLAN — `spawn_agent`'s parameters,
  `request_user_input`'s schema, `agent_roles.rs`, the `multi_agents_v2` handler set, the
  `collab_tool_call` event record — comes from a probe, not documentation.** Phase 5
  records the exact commands and their captured output in
  `tests/manual/CODEX_SPAWN_AGENT_PROBE.md`. This repo has twice built an ADR on a mis-spelled
  flag that read as authoritative once copied (`agy --print --sandbox`,
  `--output-schema`); an unreproducible probe is how that happens.
**Rejected alternatives:**
- Make it required — Rejected: non-deterministic third-party dependency in the quality gate.
- Skip it — Rejected by Interview #3; a gate that cannot see the failure it exists for is the
  H4/`agy --print` failure mode this repo has now shipped twice.
**Source:** Interview #3

### ADR-006: The lens-brief baseline is a committed golden fixture, never a git revision
**Status:** Accepted (2026-08-16, via cross-model second opinion)
**Context:** The first draft's Phase 2 exit criterion diffed the rendered core-lens briefs
against `git show HEAD~:…`. That baseline is wrong twice over: `/hm:execute` does not commit,
so during the phase `HEAD~` is an unrelated repository commit; and once wrapup squash-lands,
`HEAD~` moves again. A criterion whose baseline drifts can both fail correct work and pass
corrupted work.
**Decision:** Phase 1 extracts the four core-lens brief strings from
**`src/harness_maker/conditional_router.py:104` `LENS_DISPATCH`** — their only home — into a
committed fixture (`tests/fixtures/lens_briefs_baseline.json`). Phase 2's exit criterion diffs
the *rendered* briefs against that fixture. Changing a brief intentionally means updating the
fixture in the same commit, which makes the change visible in review.

> **Correction (validator pass 1).** The first revision named "the pre-migration templates" /
> `review.md.j2` as the source. The briefs are not there: `review.md.j2:187` and `:907` only
> interpolate `{{ d.brief }}`, supplied by `conditional_router.lens_dispatch_plan()`
> (`:154-160`). `grep 'boundaries, coupling' src/harness_maker` matches `conditional_router.py`
> alone. An executor following the old wording would have found nothing to extract.
**Consequences:**
- ✅ The baseline is stable under any commit topology, including squash-land.
- ✅ An intentional brief edit is a reviewable diff rather than an invisible pass.
- ⚠️ One more fixture to keep honest. Mitigated: it is generated by a script in Phase 1, not
  hand-transcribed.
**Rejected alternatives:**
- `git show HEAD~:…` — Rejected for the drift above.
- Compare the Codex render to the Claude render of the same run — Rejected as the *sole* check:
  it proves the two arms agree, not that either still matches the original text, so a macro
  that mangled the brief identically on both sides would pass. Kept as an additional assertion.
**Source:** Cross-model second opinion `[Phase 2/R2]`; accepted without a user round because it
corrects a mechanical defect in a criterion rather than reopening a decision.

### ADR-007: The plugin's own `commands/*.md` surface is in scope, for both the fix and the gate
**Status:** ⛔ **WITHDRAWN 2026-08-16 during /hm:execute** — its premise was probed and is
unsupported. Superseded by ADR-008. The text below is kept as the record of what was decided and
why it was reversed; do NOT implement it.

> **Why it was withdrawn.** T5 flagged the reach claim as unverified; two probes settled it.
> (1) `.codex-plugin/plugin.json` is bare metadata — no `commands` key, no asset mapping.
> (2) `codex plugin list` shows only the `openai-curated` marketplace; harness-maker is not a
> Codex-installable plugin here at all, and `README.md:278-294` routes Codex first-run through
> Bash `harness-maker make` precisely because `.agents/skills/` are generated BY that step.
> So there is no evidence Codex ever surfaces `commands/make.md`, and the ADR would have bought
> 46 rewrites plus the R5 degradation of the Claude interview for a surface that may not exist.
> The user was re-asked with this evidence and chose withdrawal.

**Status (original):** Accepted (2026-08-16, via /hm:plan interview round 3)
**Context:** ADR-004's gate iterates the render blueprint's `FileEntry`s. harness-maker's own
plugin commands (`commands/make.md` etc.) are **not** blueprint outputs — they ship directly via
`.claude-plugin/`, `.cursor-plugin/` and `.codex-plugin/plugin.json` — so `_is_codex_output`
can never see them. `commands/make.md` alone holds **46** `AskUserQuestion` occurrences, and it
is the **new-install entry point**: on Codex, the interview that creates a harness at all is
driven by a tool that does not exist there. CLAUDE.md 체크포인트 2 records this exact miss once
before — the positional-parameter gate scanned rendered output and missed `commands/make.md`
for the same structural reason.
**Decision:** Phase 4's gate gets a **second, path-literal arm** covering the plugin's own
`commands/*.md`, and Phase 3 migrates those call sites.
**Consequences:**
- ✅ The class is actually closed rather than declared closed.
- ✅ The highest-blast-radius instance — new installs on Codex — is fixed.
- ⚠️ **These files have no `is_codex` to branch on.** They are a single body served to all
  three runtimes, so the macro's two-arm shape does not apply: they must be rewritten as
  runtime-neutral prose ("ask the user these questions, using your session's structured-question
  tool if it has one") plus a per-runtime example. That is strictly less specific than today's
  Claude-only text, which is a real cost paid by the Claude path to make the Codex path work.
- ⚠️ Diff size grows materially (46 occurrences in one file). Phase 3 stays separately
  revertible for exactly this reason.
**Rejected alternatives:**
- Gate only, fix later — Rejected: the gate goes red on landing, forcing either an `xfail` or an
  allowlist entry, and both are the shape that quietly becomes permanent.
- Out of scope with an ADR-recorded residual — Rejected by the user in round 3: it leaves the
  entry point broken while the class reads as closed.
**Source:** Interview #4

### ADR-008: Phase 3 is one template block, and the brief quote policy is left open
**Status:** Accepted (2026-08-16, during /hm:execute — supersedes ADR-007)
**Context:** Two measurements taken after the terminal validator pass.
1. **T4, settled.** Rendered Codex output contains only **three distinct** unbranched
   `AskUserQuestion` lines: one documentation line naming both tools (not a defect), and two
   lines of the autopilot-picker block in `agents/_partials/step_manifest.md.j2`, replicated into
   7 stage skills. Every other site — `loop.md.j2:206` and its 12 siblings, `spec.md.j2:83`,
   `verify.md.j2:29`, `wrapup.md.j2:643`, `execute.md.j2:507`, `plan.md.j2:109/268-272/348/399` —
   is **already** `is_codex`-branched to `request_user_input`. The PLAN's "13 files" counted
   files containing the token, not unfixed call sites.
2. **T5, settled against ADR-007** — see the withdrawal note above.
**Decision:** Phase 3 un-HOLDs with a scope of **one template block**
(`step_manifest.md.j2`'s autopilot picker) plus a judgement call on the one documentation line.
The plugin's own `commands/*.md` leaves both the fix and the gate. Separately: the macro
interpolates the brief raw into a quoted argument, so a brief containing `"` would render
`message="… " …"`. **No policy is chosen here** — no `LENS_DISPATCH` brief contains a quote, so
the case is latent, and the A.5 gate showed that pinning either answer by test accident is worse
than leaving it open (asserting raw passthrough makes the correct fix read as a regression).
**Consequences:**
- ✅ Phase 3 shrinks from "13 files, 46+30 sites, plus R5 interview degradation" to one block.
- ✅ `ask_user(is_codex, questions)` stays unbuilt and that is now clearly right: two lines in one
  block do not need a macro, and ADR-001 already rejected shipping a mechanism with no consumer.
- ⚠️ The quote policy is deferred, not solved. It becomes live the moment anyone writes a brief
  containing `"`; the test records the gap rather than hiding it.
- ⚠️ `commands/make.md`'s 46 `AskUserQuestion` occurrences stay as they are. If Codex ever gains
  plugin `commands` support this reopens — the probe commands are recorded so it is re-decidable.
**Rejected alternatives:**
- Gate-only on `commands/*.md` — Rejected: the gate lands red immediately, forcing an `xfail` or
  allowlist entry, and those become permanent.
- Keep ADR-007 defensively — Rejected by the user once the probe evidence was presented.
**Source:** /hm:execute measurements + user decision, 2026-08-16.

## 🏗️ Technical Design

### Current state

- `synthesize._is_codex_output(out_path)` returns True for `.codex/`, `.agents/`, `AGENTS.md`
  and drives the `is_codex` render-context flag (`synthesize.py:1055`).
- `templates/agents/_partials/stage_end_summary.md.j2:22` already branches the autopilot
  auto-advance block on `is_codex` — the reason `Skill(` renders 0 times.
- No template branches its **subagent dispatch** on `is_codex`. `{% if is_codex %}` appears
  13× in `review.md.j2`, all of them wrapping `Bash("…")` vs `!…` shell-call syntax.

### Affected components

| Component | Change |
|---|---|
| `templates/agents/_partials/dispatch.md.j2` | **new** — `dispatch()` / `ask_user()` macros |
| `templates/stages/{plan,review,execute,research,wrapup}.md.j2` | `Task(` call sites → macro |
| `templates/commands/hm/loop.md.j2` | 2 `Task(` + 13 `AskUserQuestion` call sites → macro |
| `templates/skills/second-opinion-gate/SKILL.md.j2` | 1 `Task(` call site → macro |
| `templates/stages/{spec,verify}.md.j2`, `templates/commands/hm/{health,make,uninstall,configure}.md.j2`, `templates/skills/autoloop-driver/SKILL.md.j2`, `templates/agents/_partials/step_manifest.md.j2` | `AskUserQuestion` call sites → macro |
| `tests/fixtures/lens_briefs_baseline.json` | **new** — pre-migration core-lens briefs (ADR-006) |
| `tests/structural/test_no_claude_tool_calls_in_codex_output.py` | **new** |
| `tests/integration/test_codex_spawn_agent_live.py` | **new**, `INTEGRATION=1` |
| snapshots under `tests/**/__snapshots__` (per `regenerate.py`) | regenerated |

### Dependencies

None added. Codex CLI ≥ 0.147.0 is required for the live e2e only; the rendered instruction
degrades gracefully on older Codex by ADR-002's intent sentence.

### Architecture

```
harness.yaml.targets ──► synthesize blueprint ──► FileEntry(out_path, context)
                                                        │
                                    _is_codex_output(out_path) ──► context["is_codex"]
                                                        │
                        templates/agents/_partials/dispatch.md.j2  (single owner, ADR-003)
                          ├─ is_codex  → spawn_agent(agent_type=…, message=…) + intent line
                          └─ else      → Task(subagent_type=…, prompt=…)
                                                        │
        .agents/skills/hm-*/SKILL.md          .claude/commands/hm/*.md
                                                        │
      tests/structural/test_no_claude_tool_calls_in_codex_output.py  (ADR-004)
      tests/integration/test_codex_spawn_agent_live.py               (ADR-005)
```

### Design decisions

- `agent_type` takes the same agent name Claude's `subagent_type` takes. This is sound
  because `.codex/config.toml` already declares `[agents.<name>]` for all 15 agents from the
  same `agents` dict (`templates/codex/config.toml.j2:15-19`), and Codex validates those as
  agent roles (`core/src/config/agent_roles.rs`). No name mapping table is needed — the
  registry is already shared. (ADR-003)
- `request_user_input`'s schema is `questions: [{id, header, question, options: [{label,
  description}]}]` (live probe), which is `AskUserQuestion`'s shape minus `multiSelect`. The
  `ask_user(is_codex, questions)` macro therefore takes the **full** question payload and
  projects it per arm: Claude gets `multiSelect`, Codex drops it and renders a one-line note
  telling the model to accept several answers in prose. A signature that took only a purpose
  string could not express any of this. (ADR-003)
- The gate asserts on rendered bodies, not template sources, because a template may
  legitimately contain `Task(` inside a `{% if not is_codex %}` arm. (ADR-004)

### Data flow

Unchanged. This work alters what instruction text reaches a Codex session; the lens result
files, `lens_coverage` inputs, and the coverage verdict contract are all untouched.

### API changes

None. `spawn_agent` / `request_user_input` are Codex runtime tools, not harness-maker APIs.

## 📝 Implementation Plan

> **Snapshot policy (applies to every render-changing phase).** Phases 2, 3 and 4 each change
> rendered bodies, so each **regenerates snapshots as its last step, inside the task worktree**
> (`regenerate.py` is worktree-invariant by triple pin; running it from base regenerates
> templates this task did not touch). Without this, three consecutive phases land with a red
> suite and the executor cannot tell an expected snapshot diff from a regression — it would
> either halt at the Phase 2 boundary or force-regenerate off-plan. Phase 5 then does a final
> regeneration and confirms the tree is clean.

### Phase 1 — Dispatch macro partial + brief baseline fixture  ✅ DONE

- `depends_on`: `[]`
- `parallel_group`: `serial-render`
- `merge_hazards`: `templates/agents/_partials/` — a new partial changes every rendered file
  that includes it; snapshots must regenerate in the same commit range as Phases 2–3.
- **Scope (in):** `src/harness_maker/templates/agents/_partials/dispatch.md.j2` (new);
  `tests/fixtures/lens_briefs_baseline.json` (new, generated by script from
  `conditional_router.LENS_DISPATCH` per ADR-006); `tests/fixtures/claude_arm_baseline.json`
  (new — the **pre-migration** rendered Claude dispatch/question lines, frozen so Phase 3 has a
  non-self-approving baseline); `tests/unit/test_render_dispatch_macro.py` (new).
- **Scope (out):** every existing call site (Phases 2–3). **And `ask_user(is_codex, questions)`,
  deferred with Phase 3** (amended during execute; raised by the A.5 coverage lens as
  `scenarios_missing: ADR003-ask_user`). ADR-003 specifies both macros, and shipping only one
  half silently is the shape T4 warns about — so it is deferred *explicitly*, not omitted. The
  reason it must not be built now: T4 measured that nearly every `AskUserQuestion` site is
  **already** `is_codex`-branched inline, and several of the rest sit mid-sentence or inside a
  `####` heading where a macro call cannot go. Authoring `ask_user` today would ship a mechanism
  with no consumer — precisely what ADR-001 rejected for `Skill(`. It is built when Phase 3
  un-HOLDs and its real call-site list exists.
- **Exit criterion:** `uv run pytest tests/unit/test_render_dispatch_macro.py -q` passes,
  asserting all four:
  1. `is_codex=True` renders the ADR-002 intent sentence **before** the literal, and the
     literal is `spawn_agent(agent_type="code-reviewer", message=`.
  2. `is_codex=False` renders `Task(subagent_type="code-reviewer", prompt=` and **no** intent
     sentence.
  3. Omitting the `is_codex` argument raises Jinja `UndefinedError` — the ADR-003 loud-failure
     property, asserted rather than assumed.
  4. The macro is exercised **through a real template that `{% import %}`s it**, not called in
     isolation, so a context-propagation defect fails here rather than in production.
  Plus: `lens_briefs_baseline.json` holds exactly four entries and each matches the
  corresponding string currently in `review.md.j2`.
- **Risk:** low
- **Rollback point:** initial commit — the partial is additive and included by nothing yet.

### Phase 2 — Migrate the `Task(` dispatch call sites  ✅ DONE

- `depends_on`: `[1]`
- `parallel_group`: `serial-render`
- `merge_hazards`: `templates/stages/review.md.j2` — the four core-lens briefs are the sole
  discriminator between four dispatches to one agent; any concurrent edit to those strings
  collides semantically even when git merges cleanly.
- **Scope (in):** `templates/stages/{plan,review,execute,research,wrapup}.md.j2`,
  `templates/commands/hm/loop.md.j2`, `templates/skills/second-opinion-gate/SKILL.md.j2`.
- **Scope (out):** `AskUserQuestion` call sites; the gate.
- **Exit criterion:** all three, checked on **rendered output**, not template sources:
  1. A rendered Codex `hm-review` body contains **fourteen** `spawn_agent(` dispatches:
     `len(lens_dispatch_plan(preset)) == 7` (mandatory ∪ routable, 7 on **both** presets) × the
     **two** dispatch blocks — `review.md.j2:187` (Step 3, round 1) and `:907` (Step C2, the
     round-N re-dispatch). Both blocks must be migrated; the round-N block is what the auto-fix
     loop re-runs, so a criterion that expects seven invites deleting it.
  2. Each of the four core-lens briefs extracted from that render is byte-identical to its
     entry in `tests/fixtures/lens_briefs_baseline.json` (ADR-006), **and** identical to the
     brief in the same run's Claude render.
  3. No rendered Codex body contains `Task(` — checked by the Phase 4 gate once it lands; until
     then by an inline assertion in this phase's test.
  4. **The intent sentence appears once above each dispatch block** in the rendered Codex
     `hm-review` body (`review.md.j2:187` and `:907`). Added during execute, raised by the A.5
     coverage lens: Phase 1 can only prove `dispatch_intro` is correct *in isolation*, and its
     Scope (out) is every call site — so nothing yet forces a call site to emit it. ADR-002 makes
     the intent normative and R1 names intent-first as the **sole** mitigation for the
     `spawn_agent` schema-drift risk, so leaving it unwired would ship exactly the
     "mechanism that provably cannot fire" class this PLAN cites as prior art.
  5. The rendered Claude dispatch lines match `tests/fixtures/claude_arm_baseline.json` under
     the `re.sub(r"\s+", " ", s).strip()` normalizer (T7 — Phase 2 is the phase that moves every
     Claude call site, so the comparison cannot wait for Phase 3).
  The source-side grep from the first draft is **not** an exit criterion: `grep -c` counts
  matching *lines*, not rendered occurrences (one Jinja loop line becomes several calls), and
  templates legitimately contain `Task(` inside explanatory prose and inside the macro's own
  Claude arm. The count reconciliation it implied (17 source sites vs 25 rendered calls) has no
  correct answer. *(Raised by the cross-model second opinion as `[Phase 2/Success Criteria]`;
  accepted.)*
- **Risk:** medium — the brief strings are load-bearing and long.
- **Rollback point:** Phase 1.

### Phase 3 — Migrate the `AskUserQuestion` call sites  ✅ DONE (re-scoped by ADR-008)

- **`status`: UN-HELD 2026-08-16** — T4 and T5 were both settled by measurement during execute
  (ADR-008). **Scope collapsed to one template block**: the autopilot-picker block in
  `agents/_partials/step_manifest.md.j2`, whose two `AskUserQuestion` lines are the only genuine
  unbranched sites in rendered Codex output, replicated into 7 stage skills. Plus a judgement
  call on one documentation line that names both tools deliberately. `commands/make.md` and the
  R5 interview-degradation cost are OUT (ADR-007 withdrawn).
- `depends_on`: `[1, 2]`
- `parallel_group`: `serial-render`
- `merge_hazards`: `templates/commands/hm/loop.md.j2` (13 call sites, also touched by Phase 2).
  The dependency on Phase 2 is what enforces that, and it is declared rather than described:
  the first draft said "must not run concurrently" in prose while declaring `depends_on: [1]`,
  which authorises exactly the concurrency it forbids. *(Raised by the cross-model second
  opinion as `[Phase 3]`; accepted.)*
- **Scope (in):** the 13 template files listed in *Affected components* holding
  `AskUserQuestion`. ~~plus the plugin's own `commands/*.md` (ADR-007)~~ — **struck, ADR-007
  withdrawn**: that surface is out of both the fix and the gate, and ADR-008 re-scoped this
  phase to one template block.
- **Scope (out):** `Skill(` (ADR-001 — no rendering work).
- **Exit criterion:** all three:
  1. Rendered Codex fixture contains zero `AskUserQuestion` and ≥1 `request_user_input(`.
  3. The rendered Claude dispatch/question lines match the **Phase 1 Claude-arm fixture**
     (`tests/fixtures/claude_arm_baseline.json`) after the normalizer
     `re.sub(r"\s+", " ", s).strip()` — runs of whitespace collapsed, leading/trailing stripped.
     "Byte-identical apart from whitespace" without a named normalizer is not a criterion two
     people can agree on, and a *regenerated snapshot* cannot serve as the baseline because it
     records whatever the macro produced — it is self-approving by construction.
- **Risk:** medium — touches every interactive stage; a malformed question block degrades the
  interview rather than erroring.
- **Rollback point:** Phase 2.

### Phase 4 — Structural gate  ✅ DONE

- `depends_on`: `[2]` — was `[2, 3]`; Phase 3 is HELD, and the gate is what produces the
  enumeration T4 asks for, so it must not wait on the phase it informs.
- `parallel_group`: `serial-render`
- `merge_hazards`: none
- **Scope (in):** `tests/structural/test_no_claude_tool_calls_in_codex_output.py` (new).
  **ONE arm**: blueprint-derived, over the ADR-004 configuration matrix. ~~(b) path-literal over
  the plugin's own `commands/*.md`~~ — **struck, ADR-007 withdrawn**; that arm was never built
  and this line previously claimed coverage the shipped test does not have.
- **Scope (out):** production code.
- **Exit criterion:** all three:
  1. The test passes on the current tree across the full ADR-004 configuration matrix.
  2. It **fails** when a single `Task(` is reintroduced into any Codex-rendered body
     (demonstrate by temporary local mutation, then revert — a gate never shown to fail is not
     known to be wired).
  3. It **fails** when the scanned Codex surface is forced empty (mutate the matrix to
     `targets: [claude-code]` and assert the non-empty precondition fires), proving the gate
     cannot pass vacuously.
- **Risk:** low
- **Rollback point:** Phase 3.

### Phase 5 — Snapshots + live e2e  ✅ DONE

- `depends_on`: `[4]`
- `parallel_group`: `serial-render`
- `merge_hazards`: snapshot files — regeneration must happen inside the task worktree
  (`regenerate.py` is worktree-invariant by triple pin; running it from base regenerates
  templates this task did not change).
- **Scope (in):** final snapshot regeneration; `tests/integration/test_codex_spawn_agent_live.py`
  (new); `tests/manual/CODEX_SPAWN_AGENT_PROBE.md` (new — the probe commands and captured output
  behind ADR-002's and ADR-005's Codex-internal claims, so a future reader re-runs them instead
  of re-deriving them; this repo has twice shipped an ADR built on a mis-spelled flag).
- **Scope (out):** `~/strange_chess` (ADR-005 rejected alternative C).
- **e2e configuration — pinned, not left to the executor:**
  - sandbox: **write-capable** (`--sandbox workspace-write`). ADR-002's schema probe used
    `read-only`; that mode cannot satisfy the result-file half of the oracle, since the whole
    point is that subagents WRITE the lens files.
  - fixture preset: **Production**, `targets: [claude-code, codex]`, rendered into a tmp dir,
    including `.codex/agents/code-reviewer.toml` (and the other dispatched roles) — `agent_type`
    resolves only against roles the fixture actually rendered.
  - expected spawn events: `len(lens_dispatch_plan(preset))` = **7**, not
    `len(mandatory_lenses(preset))`. Those differ on Side (4 vs 7); using the mandatory count
    would make the assertion preset-dependent and wrong.
  - timeout: 900 s on the `codex exec` subprocess, per the project's `subprocess.run(timeout=)`
    convention.
- **Exit criterion:** `uv run pytest -q` green (full suite; run in background per project
  policy — the suite takes ~6 minutes) **and**
  `INTEGRATION=1 uv run pytest tests/integration/test_codex_spawn_agent_live.py -q` run once
  locally and green, with the run recorded in the wrapup receipt. The live test must assert the
  ADR-005 oracle **as corrected**: an `item.completed` event whose `item.type ==
  "collab_tool_call"` and `item.tool == "spawn_agent"`, plus the spawned thread's reply in
  `item.agents_states[…].message` — not merely that the command exited 0.
  ~~one `collab_agent_spawn_begin` event per mandatory lens, the per-lens result files on
  disk, and `blocks_approval: false`~~ — **struck**: `collab_agent_spawn_begin` is not
  emitted by `codex exec --json` (measured), and the result-file half was scoped out by
  ADR-005's own correction. Leaving it here would have had the phase's success condition
  stated in the vocabulary this task exists to stop using.
- **Risk:** medium — the live test depends on a third-party CLI, a login and network.
- **Rollback point:** Phase 4.

### Phase 6 — Codex-callable `Next:` banner  ✅ DONE (added during execute, user-requested 2026-08-16)

> **Scope addition, recorded not silent.** Not in the validated PLAN. The user asked for it
> directly during `/hm:execute` after the auto-advance question, so it is authorised — but it is
> logged here rather than folded into an existing phase, because it did not go through the
> interview or either validator pass.

- `depends_on`: `[]` (independent of the dispatch macro — different seam)
- `parallel_group`: `serial-render` (touches a shared partial → same snapshot hazard)
- `merge_hazards`: `templates/agents/_partials/stage_end_summary.md.j2`
- **Motivation (same defect class as `Task(`):** the stage-end banner renders
  `➡️ Next: /hm:execute {slug}` on **every** target. Codex has no slash command for a stage and
  **no tool that runs a skill at all** — live probe against Codex CLI 0.147.0: *"SKILL-running
  tools: none … A skill in `.agents/skills/` is invoked by mentioning its skill name (e.g.
  `@hm-execute`)."* So the banner named a call that runtime cannot make.
- **Scope (in):** `template_globals.stage_invocation` (new, registered as a template global so
  every `Environment` in the package gets it — a local registration renders in one code path and
  raises `UndefinedError` in another); `stage_end_summary.md.j2:113`;
  `tests/unit/test_stage_invocation_syntax.py` (new).
- **Scope (out):** the many other `/hm:` mentions inside Codex stage-skill prose. The banner is
  what was asked for; the broader prose is the same class and is recorded as a follow-up rather
  than silently expanded into. Cursor is also unaddressed — it invokes `/hm-<name>` from
  `.cursor/commands/`, a third form, and no `is_cursor` render flag exists.
- **Exit criterion:** a rendered Codex stage skill's `Next:` line contains no `/hm:`, the Claude
  command's still does, and the rewrite covers **every** command in a multi-command string
  (`/hm:review`'s banner names two stages — rewriting only the first is a silent half-fix).
- **Risk:** low. Single seam: each stage sets `summary_next` as a literal and the partial renders
  it once, so one rewrite covers all seven.
- **Rollback point:** revert the two source edits; the test file is additive.
- **Status:** implemented; 6/6 green, and shown to go RED when the partial is reverted to the
  unrewritten `{{ summary_next }}` (a gate never observed failing is not known to be wired).

### Execute log — measured outcomes (2026-08-16)

**The defect reproduced in this repo's own render before the fix**, which is what made the gate
worth building. Per preset, Codex output carried `Task(` **18**, `AskUserQuestion` **15**,
`Skill(` **0** across 9 files, with `hm-review` carrying **14** of the `Task(` (seven lenses ×
two dispatch blocks). The table below sums the two rendered presets, which is how the first
measurement was taken:

| Marker in Codex output (both presets summed) | Before | After |
|---|---|---|
| `Task(` | 36 | **0** |
| `AskUserQuestion` | 30 | **2** |
| `Skill(` | 0 | 0 |

The surviving 2 are one line, rendered twice (`autoloop-driver/SKILL.md:36`): *"`AskUserQuestion`
in Claude Code, `request_user_input` in Codex)"* — documentation that names both **on purpose**.
It is the single allowlist entry Phase 4's gate needs.

**Claude arm intact.** Compared against the frozen `claude_arm_baseline.json` under the ADR-006
normalizer: **no dispatch lost**. Every difference is accounted for — 16 files dropped out
because they are `.agents/` Codex outputs that no longer carry a Claude call (the fix), and the
`plan` / `wrapup` / `second-opinion-gate` entries changed only because a multi-line
`Task(\n  subagent_type=…\n)` collapsed to one line (the old shape had no line containing
`Task(subagent_type=`, so the baseline never captured it). Source diff confirms the prompt
strings moved verbatim. **The fixture was deliberately NOT regenerated** — a post-migration
capture is the self-approving baseline T7 and the A.5 lenses both rejected.

**Corrections to this PLAN found by execute:**
- `second-opinion-gate/SKILL.md.j2` was recorded here as already-branched. It was not: its
  `Codex:` block was an *additional* section, not an `{% else %}`, so the Codex skill shipped
  both forms. It is now macro-driven like the rest.
- Three `Task(...)` mentions were prose, not call sites (`loop.md.j2:489`, `:808`,
  `plan.md.j2:619`). Two of them read as instructions on Codex ("retry the `Task(...)` call"), so
  they were rewritten runtime-neutrally rather than allowlisted — which is why the allowlist is
  one entry instead of four.
- `templates/commands/hm/loop.md.j2` has **zero** dispatch call sites, contradicting the
  Affected-components table above. T4 was right about that file.

**Total source change: 8 template files, +33/−31.**

### Phase D.5 — newly-reachable window (this was a repair, so it applies)

**1. What does this repair newly make reachable?**
**Codex sessions that actually spawn sub-agents.** Before, every Codex dispatch named a tool
the runtime does not have, so the model improvised locally and no sub-agent ran — the window
was empty. It is now non-empty, and it is wider than the reported symptom: the same macro feeds
`hm-review`'s **seven-lens fan-out ×2 blocks**, `hm-execute`'s **three-lens A.5 gate**,
`plan-validator`, `judgment-reviewer` and `code-verifier`. None of those has ever executed on
Codex. Concretely reachable for the first time: concurrent sub-agent execution on Codex, and
every downstream contract that assumes a sub-agent returned — above all the **lens result files
the main loop writes from each returning dispatch**, which is where the original failure showed.

**Absent case.** The repair activates on a tool that may not exist: `spawn_agent` requires the
`multi_agent` feature (stable/true at 0.147.0, but not guaranteed on an older Codex or with the
feature disabled). Before, the named tool was *always* absent; now it is *usually* present. The
handled behaviour is ADR-002's ordering — the intent sentence precedes the literal, so a session
without `spawn_agent` reads "delegate to the project's `code-reviewer` agent using your session's
sub-agent tool" and can still act or say it cannot. That is a documented degrade, not a default.

**2. Which test enters the window, and is it in this change?**
`tests/integration/test_codex_spawn_agent_live.py::test_codex_executes_the_shipped_dispatch_instruction`
— yes, in this change, run green once under `INTEGRATION=1`. It enters the window itself rather
than re-asserting the original symptom: it feeds Codex the **shipped** intent + dispatch line
and asserts the runtime's own `collab_tool_call`/`spawn_agent` record plus the sub-agent's reply.

**3. Stated gap — the window is entered, not covered.**
One dispatch is proven executable. **Not covered:** the seven-lens fan-out as a fan-out
(concurrency, all seven roles resolving, seven distinct briefs arriving intact); and the
result-file half — that the main loop, having received seven Codex replies, writes seven files
and clears `hm lens_coverage check`. That second gap is the reported symptom's own last mile, and
it is the honest limit of what this change verifies. Covering it means driving a full `/hm:review`
on Codex — seven live sub-agent runs — which ADR-005 deliberately scoped out. **Filed as a
known risk carried into review, not silently omitted:** a green suite here does not prove a
Codex `/hm:review` now approves; it proves the instruction it depends on is executable.

## 🧪 Testing Strategy

- **Unit** — `test_render_dispatch_macro.py`: both arms of the macro, brief passthrough,
  intent-sentence presence in the Codex arm only.
- **Structural** — `test_no_claude_tool_calls_in_codex_output.py`: blueprint-driven,
  output-path-derived (ADR-004). Must be demonstrated failing once (Phase 4 exit).
- **Snapshot** — regenerated; the diff is the review artifact. Reviewers read the Codex
  snapshot diffs specifically for the four core-lens briefs.
- **Integration (`INTEGRATION=1`)** — one `codex exec` run against a rendered fixture,
  asserting a subagent spawn actually occurred.
- **Manual** — none required; the reported symptom is reproduced by the structural gate and
  the live e2e together.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `spawn_agent` schema differs between `codex exec` (v1: `agent_type`/`message`) and interactive/v2 (`task_name`/`fork_turns`) | high | high — dispatch silently fails again | ADR-002 orders the **intent sentence first** so a wrong literal is recoverable rather than fatal; Phase 5's live e2e verifies the `exec` half. **Residual, explicitly unmitigated:** the interactive half is unverified and cannot be automated here. A human running one `/hm:review` in an interactive Codex session is the only closing check, and it is deliberately not a phase exit |
| R2 | The macro reformats a core-lens brief, collapsing four lenses into one | medium | high — silently degrades `/hm:review` fan-out to one voice | Phase 2 exit criterion diffs the extracted briefs byte-for-byte against the committed `lens_briefs_baseline.json` (ADR-006) and against the same run's Claude render |
| R3 | The structural gate passes without ever being wired (asserts over an empty set, or over one configuration that happens not to render the leak) | medium | high — a green gate that checks nothing is worse than none | ADR-004's non-empty precondition + configuration matrix; Phase 4 exit requires demonstrating **both** failure modes by mutation before landing |
| R4 | The macro is imported without context and silently takes the Claude arm everywhere | medium | high — reproduces the original bug inside the fix | ADR-003 makes `is_codex` an explicit required parameter, so omission is a Jinja `UndefinedError`; Phase 1 exit asserts that error fires and exercises the macro through a real `{% import %}` path |
| R5 | Rewriting `commands/*.md` to runtime-neutral prose degrades the Claude interview experience | medium | medium — vaguer questions, worse onboarding | ADR-007 accepts this explicitly; Phase 3 keeps a per-runtime example alongside the neutral instruction, and Phase 3 stays separately revertible |
| R6 | Existing rendered harnesses (`~/strange_chess`) keep the broken instruction until re-rendered | certain | medium | Out of scope by ADR-005's rejected alternative C; remedy is `/harness-maker:make --update`, and the drift banner already tells the user so (observed firing during this PLAN's probes) |
| R7 | `request_user_input` is gated behind a Codex feature flag in some configurations | low | medium | Live probe confirmed availability in `codex exec` at 0.147.0; the intent sentence covers absence by instructing a plain-prose question |

## ✅ Success Criteria

- [x] No Codex-rendered output contains `Task(`, `Task tool` or `Skill(`, and the only
      `AskUserQuestion` is the single allowlisted line that names BOTH runtimes
      (`autoloop-driver/SKILL.md:36`, one per preset). **Not an absolute** — that line's whole
      value is naming the mapping, and a reader treating the criterion literally could "fix"
      the artifact by deleting it.
- [x] A rendered Codex `hm-review` skill contains fourteen `spawn_agent` dispatches (7 lenses ×
      2 dispatch blocks, `review.md.j2:187` and `:909`) whose core lens briefs are
      byte-identical to `lens_briefs_baseline.json` and to the Claude-rendered ones.
- [x] The structural gate has been observed failing on an injected regression for **every**
      `_CLAUDE_ONLY` entry (the payload set is derived from that tuple, so a new entry with no
      payload fails the test rather than shipping unexercised) **and** on a forced-empty scan
      surface.
- [x] `INTEGRATION=1` live e2e run and green **after the final edit to it** — asserting the
      runtime's own `collab_tool_call`/`spawn_agent` record and the sub-agent's reply.
      **It does NOT assert lens result files or `blocks_approval`** — ADR-005 scoped that half
      out, and the D.5 gap above says so; an earlier version of this line claimed both and
      contradicted its own document.
- [x] Full suite green.
- [x] Every rendered dispatch on either target originates from the dispatch macro, and the
      macro fails loudly when `is_codex` is not passed.

## 🔍 Plan Validation

### Cross-model second opinion

| Model | Status | Outcome |
|---|---|---|
| `codex` | `invoked` | 9 findings (7×P1, 2×P2, 1×P3). **All 9 accepted and resolved** in this revision — see the ADR/phase edits cited inline above. |
| `antigravity` | `failed` | `agy` returned `status: SUCCESS` with an empty `response` and no `structured_output`. Recorded as agy-side flakiness on large prompts (the invoker's own diagnosis), not a parser or size-cliff failure. **The verdict below is Claude + codex only**; antigravity cast no vote. |

Codex's most consequential finding was `[ADR-003/Phase 1]`: a macro that reads `is_codex` from
Jinja context would silently take the Claude arm in production while an isolated unit test
passed — the exact `is_codex`-hardcoded-`False` failure this PLAN cites as prior art, about to
be reintroduced inside its own fix. It is now ADR-003's explicit-parameter decision and R6.

### Validator passes

Run id `clr-20260816-1`. Two passes, the cap. `hm plan_rounds outcome` reports
**`progress`** — `resolved_n: 9, unresolved_n: 0, new_n: 11`. Every pass-1 critique was
genuinely resolved and none transferred; the cap stopped a loop that was still moving, which is
a different situation from `no-progress` and calls for a different response (continue the work,
do not attack the PLAN's structure).

| Pass | Verdict | Findings |
|---|---|---|
| 1 | `MAJOR_REVISION` | 3 critical, 4 warning, 2 suggestion — all 9 accepted and resolved |
| 2 (terminal) | `MAJOR_REVISION` | 5 critical, 4 warning, 2 suggestion — **recorded, not revised** |

### Terminal findings (pass 2) — carried into execute as known risks

**These survive into `/hm:execute`. They are not blockers on the stage; they are the debt the
two-pass cap left behind. Two of them invalidate decisions made in this PLAN and must be
settled before the phase they affect runs.**

| # | Sev | Finding | Effect |
|---|---|---|---|
| T1 | critical | `lens_dispatch_plan` — the symbol Phase 2, Phase 5 and Success Criteria anchor their counts to — **does not exist**. The real function is `conditional_router.lens_dispatch(preset)` (`conditional_router.py:141`, called at `review.md.j2:2`). The arithmetic (7 on both presets) is right; the authority named for it is fabricated | Phase 2/5 exits raise `ImportError` and the executor guesses between 7 and 4 |
| T2 | critical | Phase 1's **exit criterion** still says the fixture entries must match "the corresponding string currently in `review.md.j2`" — the exact wording ADR-006's own Correction block says it removed. Scope (in) was fixed; the exit criterion was not | Phase 1 is unsatisfiable as written, or is "satisfied" by snapshotting the render path Phase 2 is about to change (self-approving) |
| T3 | critical | Phase 4's gate cannot pass on the current tree: **36 backticked prose mentions** of the three tool names across 14 template files are outside Phases 2–3's call-site scope, at least one of them unbranched and reaching Codex output (`review.md.j2:182`, `loop.md.j2:489`, `:808`). ADR-004 anticipated only *future* mentions and no phase creates the allowlist | Phase 4 lands red; cheapest recovery is weakening the gate, which is this bug's shape inside its own fix |
| T4 | critical | Phase 3's `AskUserQuestion` scope is wrong. **Nearly every site is already `is_codex`-branched** — verified: `loop.md.j2:206` and its 12 siblings, `spec.md.j2:83`, `verify.md.j2:29`, `wrapup.md.j2:643`, `execute.md.j2:507`, `plan.md.j2:109/268-272/348/399` all already emit `request_user_input` on the Codex arm. The PLAN confused "file contains the token" (13 files) with "file contains an unfixed call site" (the 7 measured, essentially the `step_manifest.md.j2:61` autopilot picker replicated per skill). Several remaining sites are mid-sentence clauses or a `####` heading, which `ask_user(is_codex, questions)` structurally cannot occupy | Phase 3 as scoped rewrites working code across 13 files, pays R5's Claude-interview degradation for no defect, and stalls when the macro cannot express the site |
| T5 | critical | **ADR-007's premise is unverified and the repo contradicts it.** `.codex-plugin/plugin.json` is bare metadata — it declares **no `commands` key** (verified). `README.md:278-294` routes Codex first-run make through Bash `harness-maker make`, because `.agents/skills/` are generated *by* the make step. So "on Codex the interview that creates a harness is driven by a tool that does not exist there" may be false, and `commands/*.md` is one file, not several | Phase 3's largest, least-revertible cost — 46 rewrites plus accepted R5 degradation — may be paid for a surface Codex never reaches |
| T6 | warning | The Phase 5 oracle is stated three times and **twice in the vocabulary the revision rejected**: ADR-005's Decision and Phase 5's Exit criterion still say "per mandatory lens" while the config bullet says dispatched-lens. Coincides at Production (7 = 7), diverges on Side (7 vs 4) | Latent wrong oracle; silent on the first Side run |
| T7 | warning | `claude_arm_baseline.json` is created in Phase 1 but consumed only in Phase 3, while **Phase 2** is the phase that moves every Claude dispatch call site | A Phase 2 Claude-arm regression surfaces one phase late, misattributed to Phase 3 — or is laundered into the baseline to make Phase 3 green |
| T8 | warning | The Snapshot policy names Phase 4 as render-changing; Phase 4's scope is test-only | A Phase 2/3 regeneration miss gets swept up under Phase 4, eroding the exact signal the policy exists to give |
| T9 | warning | R2/ADR-006 pin only the **4 core** briefs. `lens_dispatch` returns **7** on both presets and the 3 domain briefs (`conditional_router.py:126-137`) traverse the identical macro quoting seam | A quoting defect landing on the `security` brief passes Phase 2 cleanly and degrades that lens in every harness |
| T10 | suggestion | Phase 2's title says "17 call sites"; its own exit criterion says that number "has no correct answer" | Reads as a checklist target the document disowns |
| T11 | suggestion | `interview_rounds: 3` with four transcript rows ordered 1, 2, 4, 3; ADR-007 cites both "round 3" and "Interview #4"; the cross-model paragraph still says "R6" after the renumbering to R4 | Two answers to which round produced ADR-007 |

**T4 and T5 together mean Phase 3 is the wrong size.** Before Phase 3 runs it must be
re-scoped to the enumerated unbranched sites, and ADR-007's reach claim must be settled by the
one-command probe ADR-005's own standard already requires of every Codex-runtime claim — a
standard this PLAN applied everywhere except the ADR that authorises its biggest diff.

### Operator disposition (2026-08-16)

The terminal pass returned `MAJOR_REVISION`; the operator was asked and chose **proceed with
the remaining critiques as accepted risk, with Phase 3 held**. Recorded as
`validator_outcome: MAJOR_REVISION_RESOLVED` — a human was present and the verdict is explicit.
The findings above are NOT withdrawn by that choice; `/hm:execute` carries them as known risks.

Binding consequences of the disposition:

1. **Phase 3 does not run** until T4 and T5 are settled. Its `status` below is `HELD`. Running
   Phases 1, 2, 4, 5 without it is coherent: Phase 4's gate covers `AskUserQuestion` and will
   show exactly how many sites are genuinely unbranched, which is the enumeration T4 asks for.
   Phase 4's `depends_on` therefore drops to `[2]`.
2. **T1 and T2 are corrected inline during execute**, not re-planned: replace
   `lens_dispatch_plan` with `conditional_router.lens_dispatch` (`conditional_router.py:141`)
   in Phase 2 exit 1, Phase 5's e2e bullet and Success Criteria; point Phase 1's exit criterion
   at `conditional_router.py:104 LENS_DISPATCH`. Both are name corrections with a verified
   referent, not decisions.
3. **T3 makes Phase 4 land red as specified.** Phase 4 must additionally produce the allowlist
   artifact, seeded with `review.md.j2:182`, `loop.md.j2:489`, `loop.md.j2:808` — and the
   allowlist must record a *reason* per entry. It must NOT be closed by narrowing the pattern
   to `Task(subagent_type`; a pattern that exempts every backticked occurrence exempts most of
   the surface the gate exists to police.
4. **T6 and T9 are cheap and get folded into Phase 2/5 as they are worked**: one oracle
   vocabulary (dispatched-lens), and all seven `LENS_DISPATCH` briefs in the baseline fixture
   rather than four.
5. **T7 and T8 adjust phase boundaries**: the `claude_arm_baseline.json` comparison becomes a
   Phase 2 exit criterion as well as a Phase 3 one; the Snapshot policy applies to Phases 2 and
   3 only, and Phase 4 asserts the tree is already clean.
6. **T10 and T11 are cosmetic** and are accepted as-is.

The distinction this record preserves: `MAJOR_REVISION_RESOLVED` means a human accepted these,
not that a clean verdict was reached. Two passes ran and these eleven survived the second.
