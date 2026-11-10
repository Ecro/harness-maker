[🇰🇷 한국어](HOW-IT-WORKS.ko.md)

# harness-maker: How It Works

> **Audience**: developers who use harness-maker and want to know what each stage does, what it
> writes, and where it stops for a person.
> **Version**: 0.65.3
>
> This guide describes the current release only. What changed between releases is in
> [CHANGELOG.md](../CHANGELOG.md); the design record is in [ARCHITECTURE.md](ARCHITECTURE.md).

> Current release contract (validated from source):
>
> <!-- hm-doc-contract:pipeline:start -->
> **Current pipeline:** `research` → `spec` → `execute` → `wrapup`
> <!-- hm-doc-contract:pipeline:end -->
>
> <!-- hm-doc-contract:agents:start -->
> **Current agents:** `code-reviewer`, `code-verifier`, `concurrency-reviewer`, `consensus-arbiter`, `judgment-reviewer`, `performance-reviewer`, `security-reviewer`, `spec-validator`, `stage-delegate`, `test-reviewer`, `trajectory-monitor`, `ux-reviewer`
> <!-- hm-doc-contract:agents:end -->
>
> <!-- hm-doc-contract:skills:start -->
> **Current skills:** `agent-quality-rubric`, `ai-readiness-rubric`, `context-linter`, `intent-layer`, `project-knowledge`, `second-opinion-gate`, `trajectory-monitor`, `worktree-isolator`, `world-model`
> <!-- hm-doc-contract:skills:end -->
>
> <!-- hm-doc-contract:mechanisms:start -->
> **Current mechanisms:** M1, M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12, M13, M14, M15, M16, M17, M18, M19
> <!-- hm-doc-contract:mechanisms:end -->
>
> <!-- hm-doc-contract:version-files:start -->
> **Release version files:** `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`
> <!-- hm-doc-contract:version-files:end -->
>
> The lists above are every template in the source tree. Not all of them render into every
> project; [Agents](#agents) and [Skills](#skills) say which render when.

---

## Contents

1. [What harness-maker is](#1-what-harness-maker-is)
2. [Render pipeline](#render-pipeline)
3. [The four stages](#3-the-four-stages)
4. [`hm check`](#4-hm-check)
5. [Maker, the front door](#5-maker-the-front-door)
6. [Per-task worktrees](#6-per-task-worktrees)
7. [Agents](#agents)
8. [Skills](#skills)
9. [Hooks](#9-hooks)
10. [Memory, intents and the Second Brain](#10-memory-intents-and-the-second-brain)
11. [Cross-model second opinion](#11-cross-model-second-opinion)
12. [Other commands](#12-other-commands)
13. [Key `harness.yaml` settings](#13-key-harnessyaml-settings)
14. [Retired in 0.64.0](#14-retired-in-0640)

---

## 1. What harness-maker is

harness-maker is a Claude Code and Codex plugin. One command, `/harness-maker:make`, interviews
you once about your project and renders a **harness** into it: stage commands, a few agents and
skills, hooks, and one config file, `.claude/harness.yaml`, which is the single source of truth.
Re-running `make` re-renders from that file and keeps your edits.

The harness is for production code that keeps being maintained. It keeps what a capable model
still does not do on its own, and drops what it does:

- **State that outlives a context window**: SPECs, PLANs, REVIEWs, memory and intents are files,
  so the next session starts from them, not from a summary.
- **A human lock-in**: you approve the SPEC, and every irreversible decision (schema, public API,
  data migration, security boundary, new dependency) waits for you.
- **Deterministic gates**: tests are written first and must fail for a real reason (RED), and
  `hm check` runs your lint, type and test commands plus the AC tests before anything lands.
- **An understanding delta**: each commit ends with what assumption changed, so your picture of
  the system moves with the code.

Commands are `/hm:<name>` in Claude Code and `$hm-<name>` skills in Codex. All telemetry stays
on your machine.

## Render pipeline

`/harness-maker:make` (and the rendered `/hm:make`) turn `harness.yaml` into the on-disk
harness, then guide you all the way to a git decision. The flow is deliberately **not** run
inside a git worktree — `make` writes the real `.claude/`, and safety comes from a backup +
reconcile + a read-only preview, which also keeps non-git projects working.

**1. Resolve + preview (re-render only).** When `.claude/` already exists and is non-empty,
make runs `--dry-run` first and shows NEW / REPLACE / KEEP / MERGE counts (KEEP = files where
your edits are preserved verbatim; MERGE = `@hm:user:*` blocks block-merged into the new
template), then asks you to confirm before writing. A fresh install skips the preview and
applies directly. Existing generated state is copied to `.backup-<ts>/` (auto-gitignored)
before any overwrite.

**2. Apply + narrate.** Files are written; the CLI emits a stable `render-summary:` line
(`files= keep= merge= targets=`) that the slash command turns into a plain-language summary in
your locale — what changed, what was preserved, the current version. The structural-health scan
is **quiet when clean** and only goes **loud when there are real P0/P1 findings** (run
`/hm:health` for the full scan any time).

**3. Git disposition — the last mile.** Render isn't "done" until the files are in git the way
you intend. `harness-maker git-status` inspects the rendered manifest across every selected
target root (`.claude/`, plus `.codex/`, `.agents/` and `AGENTS.md` for Codex), minus
operational churn, and reports one of:

| state | what make does |
|-------|----------------|
| not a git repo | tells you; suggests `git init` if you want tracking; runs no git commands |
| undecided (neither tracked nor ignored) | asks **neutrally** — *commit them* (share with your team) or *gitignore them* (keep local). No recommended option. |
| already committed | nothing — unless a re-render added new files, in which case it offers to stage just those (never a full re-prompt) |
| already gitignored | nothing |

The decision is **inferred from git state every run, never stored**, so re-rendering never
re-nags. Committing is clean because churn (`observability/`, `.backup-*`) is already
gitignored; `git-ignore-roots` ignores the whole target roots and **fails loudly** if the write
doesn't take effect, so the slash command can't falsely report success.

**What the interview asks.** Only what you own: locale, target IDEs (Claude Code, Codex, or
both; never auto-detected), the preset (`Side` for a side project, `Production` for a shipped
product) and a few project facts. Everything else takes the preset's default, and the summary
lists what was decided for you.

**What renders.** `.claude/harness.yaml`, `.claude/commands/hm/*.md`, `.claude/agents/*.md`,
`.claude/skills/*/SKILL.md`, the `hooks` and `permissions` keys of `.claude/settings.json`
(deep-merged, so your own hooks stay), and pointer sections in `CLAUDE.md`. With Codex selected:
`.codex/config.toml`, `.codex/hooks.json`, `.codex/agents/*.toml`, `AGENTS.md` and
`.agents/skills/`. Every generated file carries `generated_by`, `content_hash`,
`source_template` and `harness_maker_version` in its frontmatter, which is how a re-render tells
your edits from its own output.

## 3. The four stages

One task moves through up to four stages in order: `/hm:research` (optional) → `/hm:spec` →
`/hm:execute` → `/hm:wrapup`. Each stage is self-contained, reads the previous stage's files,
and stops where a person is needed. You type the next stage yourself, or Maker chains them in
one session (see [§5](#5-maker-the-front-door)). Nothing is pushed unless you ask.

| stage | writes | stops for you when |
|---|---|---|
| `/hm:research <topic>` | `work-docs/RESEARCH-<slug>.md` | `--deep` asks 3–5 scoping questions first |
| `/hm:spec <slug>` | `specs/SPEC-<slug>.md`, `specs/SPEC-<slug>.machine.yaml` | the interview, and SPEC approval |
| `/hm:execute <slug>` | `work-docs/PLAN-<slug>.md`, tests, code, `work-docs/REVIEW-<slug>-<date>.md` | an unapproved SPEC, a new irreversible decision, a finding left unresolved |
| `/hm:wrapup <slug>` | memory entries, one commit | a held irreversible decision, intent writes under an exempt SPEC |

### 3.1 `/hm:research` — optional

Gathers what a SPEC needs: the codebase, the project's own record (memory, earlier SPECs, PLANs
and REVIEWs), current library docs and the web. Every claim carries its `file:line` or URL and
the snippet behind it. It analyses each approach (assumption, evidence, trade-off, fit, risk) and
recommends a direction, which the SPEC is free to overrule. No stage requires it.

### 3.2 `/hm:spec` — what, why, and how to verify

The only interview. With `worktree.enabled`, it runs in a per-task worktree (see
[§6](#6-per-task-worktrees)).

1. **Skip check.** A one-file, obviously-scoped, reversible change with no API or format change
   gets a minimal SPEC with one testable AC and is stamped exempt, without an interview.
2. **Intent.** If the project has active intents, it asks which one this task serves.
3. **Interview.** It asks only what you own: why now, what "done" looks like, the scenarios, the
   non-goals, and every irreversible decision; at most 3 questions per round. It settles
   constraints, verification and each AC's oracle itself and shows them as **Refinement
   Decisions** for you to veto.
4. **SPEC + machine.yaml.** Each AC has an oracle independent of the code it checks (golden,
   differential, property, rubric or consensus). "The test will check it" is rejected as
   circular.
5. **Checks.** `hm spec_machine check` validates the pair and scores its quality; at
   `spec.strictness: block` a blocked score stops the stage, at `warn` it only warns. `spec-validator` performs one conditional, advisory critique of the
   SPEC: skipped by default for a SPEC with 8 or fewer live ACs, run when you choose "Approve
   after spec-validator".
6. **Approval.** Only your explicit "Approve this SPEC" stamps it (`hm spec_machine approve`);
   silence never counts. `--exempt` is reserved for a SPEC with no irreversible decision under
   `autonomy.level: auto_full`, or the skip path.

### 3.3 `/hm:execute` — tests first, then code, then one review

It never commits.

1. **SPEC gate.** `hm spec_machine approval-status` must say `approved` or `exempt`.
2. **PLAN.** Writes `work-docs/PLAN-<slug>.md`: phases (each with `scope`, `exit` command,
   `risk`, `rollback`) and a `### Do not change` list of paths this task must not touch.
3. **Tests first (RED).** A test for every testable AC, named `test_ac_NNN_<short>`, before any
   code. `hm check --red` must show each failing for a real reason. An AC whose behaviour
   already exists may be waived with `--green-ok AC-NNN`; the reviewer sees the waiver.
4. **Implement.** Phase by phase, the smallest change that turns its tests green. A new choice in
   an irreversible category is appended to the SPEC (voiding its approval) and the stage stops
   for you.
5. **Bind and gate.** `hm spec_machine mark-tested` binds the tests to their ACs, then
   `hm check` runs every gate. A path from `Do not change` in the diff stops the stage.
6. **Review.** One `code-reviewer` reads the SPEC, PLAN, diff and tests together, so it also
   catches a weakened test. Each finding gets a disposition: `accepted`, `rejected` (with an
   authority), `duplicate` or `unresolved`. Accepted findings are fixed and reviewed again, up to
   `reviewers.max_review_rounds` (3). The REVIEW doc is written after the loop, so its presence
   marks execute as done.

### 3.4 `/hm:wrapup` — gate, memory, one commit

1. **Gate.** `hm check --reuse --require-review`: a code change with no REVIEW record fails
   (unless the SPEC is exempt). `--reuse` skips the rerun when nothing changed since execute.
2. **Judgment ACs.** Each `type: judgment` AC goes to `judgment-reviewer` against its rubric.
3. **PLAN** is marked complete.
4. **Memory.** Durable lessons go to the wiki and the failure log (`hm memory_md`); a failure
   that recurs three times becomes a proposal in `.claude/memory/pending-proposals.md`.
   Intent observations and metric records are written without asking under an approved SPEC.
5. **Commit.** One commit whose message has the why, the RED summary, and an `Understanding:`
   block (`<assumption>: <before> -> <after>`, `unknown: …`, `agent-decided: ADR-…`).
   `hm wrapup_land` stages exactly the task's files; a held irreversible decision is shown to
   you before it lands.
6. **Squash-land.** With worktrees on, `hm worktree task-land` squashes `hm/<slug>` onto your
   branch as one commit and removes the worktree.

It never pushes.

## 4. `hm check`

`hm check --slug <slug>` runs a task's deterministic gates and prints one JSON line with one
section per gate:

| section | checks |
|---|---|
| `approval` | the SPEC is approved, exempt, or allowed unstamped by `auto_full` |
| `gates` | your CI config's lint, type and test commands; without a CI file, ruff, mypy and pytest derived from `pyproject.toml`; plus `reviewers.mechanical_checks` |
| `ac` | every testable AC has a bound test, and it passes |
| `review` | with `--require-review`, a code change has a REVIEW record |
| `contract` | no changed path is in the PLAN's `Do not change` list |
| `security` | no secret or hook injection in a changed file |
| `cve` | dependency vulnerabilities via OSV (`--offline` skips it and says so) |

Exit codes: `0` ok, `1` a gate failed, `2` usage, `3` degraded (a gate could not run; never a
pass), `4` the tree changed mid-run, `5` approval missing or invalid. `--red` inverts the AC gate
for the RED step; `--mutation` adds an opt-in mutation gate. The AC runner is pytest only; on a
project without pytest, `hm check` says so instead of passing silently.

## 5. Maker, the front door

Maker is a skill (named at interview time; default `Maker`, typed `/maker`) that is the one entry
to the project's state: it briefs you on where things stand, starts or resumes a task, records a
project fact, and manages goals and metrics. It reads a digest from `hm world_model digest` (at
most 1,500 bytes, always exit 0) instead of re-reading the repo.

**Scope follows the ask.** "research X" ends at research, "spec X" at spec, "build X" or "fix X"
runs the full pipeline.

**Advance rule.** On a full-pipeline start or resume, Maker runs spec → execute → wrapup in the
same session and stops where a person is needed (the interview, SPEC approval, an irreversible
decision, an unresolved finding), when the last `hm check` did not exit 0, or when the task has
`## Queued asks`. It never pushes. Typing a stage yourself always works too.

`intent-layer` and `project-knowledge` are reached only through Maker; they never trigger on
their own.

## 6. Per-task worktrees

With `worktree.enabled: true`, each task lives in `.worktrees/<slug>/` on branch `hm/<slug>`,
shared by all its stages:

- `hm worktree task-preflight` creates or re-enters it and warns about other active sessions.
- `hm worktree task-refresh` rebases it onto your branch (it refuses a dirty tree and aborts on
  a conflict, leaving the branch untouched).
- `/hm:wrapup` lands it as exactly one squash commit with `hm worktree task-land`.

Two sessions on the same repo each get their own worktree. The `worktree_gate` hook blocks an
edit to the base checkout while a task worktree is active. The full rules are in
[multi-session-worktree.md](reference/multi-session-worktree.md).

## Agents

Agents are sub-agents the stages dispatch. The only enforced boundary is `tools:`; reviewers
have no Bash and no write tools.

| agent | renders when | used by |
|---|---|---|
| `code-reviewer` | always | `/hm:execute` review |
| `spec-validator` | always | `/hm:spec` advisory pass |
| `judgment-reviewer` | always | `/hm:wrapup` judgment ACs |
| `security-reviewer`, `concurrency-reviewer`, `test-reviewer`, `performance-reviewer`, `ux-reviewer` | `reviewers.fanout: true`, for names in `reviewers.installed` | dispatched beside `code-reviewer`; findings are merged as a union, not a vote |
| `code-verifier`, `consensus-arbiter` | `second_opinion.models` is non-empty | the cross-model acceptance gate |
| `stage-delegate` | `delegation.stages` includes `wrapup` | runs wrapup Steps 1–5 and returns a receipt |
| `trajectory-monitor` | never (template kept) | — |

## Skills

| skill | renders when | what it does |
|---|---|---|
| `world-model` | always, at the handle you named | Maker (§5) |
| `intent-layer` | always | intents: create, observe, measure, close; reached through Maker |
| `project-knowledge` | always | records a project fact the code does not show; reached through Maker |
| `context-linter` | always | flags bloated CLAUDE.md, agent and skill files against the preset's limits |
| `agent-quality-rubric` | always | grades an agent file Platinum to Bronze |
| `ai-readiness-rubric` | always | scores how ready a repo is for AI work |
| `worktree-isolator` | always | the worktree procedure the stages follow |
| `second-opinion-gate` | `second_opinion.models` is non-empty | the round-state and acceptance procedure of the review loop |
| `trajectory-monitor` | never (template kept) | — |

## 9. Hooks

Claude Code reads project hooks only from the `hooks` key of `.claude/settings.json`; Codex reads
`.codex/hooks.json`. Both are merged on re-render, so your own hooks stay.

| event | command | host | what it does |
|---|---|---|---|
| `SessionStart` | `hooks.sessionid_envfile` | both | exposes the session id to stage shell commands |
| `SessionStart` | `hooks.sessionstart_drift` | Codex (Claude: the plugin's own `hooks/hooks.json`) | warns when the rendered harness drifted from its templates |
| `PreToolUse` (Bash) | `gates.permission_gate` | both | blocks dangerous commands such as `curl … \| sh` |
| `PreToolUse` (Write/Edit) | `gates.worktree_gate` | Claude | blocks base-checkout edits while a task worktree is active |
| `PreToolUse` (Write/Edit; Codex: `apply_patch`) | `gates.spec_gate` | both | at `spec.strictness: block`, blocks writing a test file that no SPEC references |
| `PreCompact` | `hooks.flush_session`, `worktree span-end` | Claude | snapshots progress before compaction |
| `Stop` | `worktree span-end` (Codex: `hooks.flush_session`) | both | closes the session's span (Codex: snapshots progress) |

## 10. Memory, intents and the Second Brain

- **Memory** (`.claude/memory/`): a wiki of durable project facts and a failure log with
  occurrence counts. Stages read it with `hm memory_retrieve --topic …`; wrapup writes it with
  `hm memory_md`. A compaction checkpoint in `.claude/memory/session/<date>.md` lets an
  interrupted stage resume.
- **Intents** (`hm intent`): goals with open questions and metrics. Wrapup records observations
  (`confirms` / `contradicts`) and metric measurements from the task's evidence.
- **Second Brain** (optional, `second_brain.enabled`): an Obsidian vault shared across projects.
  Research and execute search it; wrapup promotes only what is durable across projects.

## 11. Cross-model second opinion

With `second_opinion.models` set (`codex`, `antigravity`), execute's review also asks the other
models through `hm second_opinion_invoke`. A finding two voters raise is accepted (k-of-N, K=2);
a single-voter finding goes to `code-verifier`, which may still accept it. The vote is frozen
after one call per review. Every failure (missing CLI,
timeout, bad output) warns and proceeds. Rates come from
`hm verifier_discrimination report --ledger .claude/observability/second-opinion.jsonl`, never a
hand count. Details: [second-opinion.md](reference/second-opinion.md).

## 12. Other commands

| command | what it does |
|---|---|
| `/hm:make` | re-render from `harness.yaml` (same as `/harness-maker:make`) |
| `/hm:health` | structural integrity plus personalization drift audit |
| `/hm:metrics` | change failure rate, post-merge churn and token spend, from local git and transcripts |
| `/hm:help` | the command list in your locale |
| `/hm:uninstall` | removes the generated files after showing what goes and asking you to confirm |

## 13. Key `harness.yaml` settings

| key | effect |
|---|---|
| `preset` | `Side` or `Production`: defaults for strictness, limits and review depth |
| `locale` | the language stages talk to you in; documents stay English |
| `targets` | `claude-code`, `codex` |
| `spec.strictness` | `block` or `warn`: whether a blocked SPEC quality score stops `/hm:spec`, and whether `spec_gate` blocks a test file no SPEC references |
| `worktree.enabled` | per-task worktrees (§6) |
| `reviewers.max_review_rounds`, `reviewers.fanout`, `reviewers.installed` | the review loop and lens reviewers |
| `autonomy.level` | `ask`, `gated`, `auto_safe`, `auto_full`; only `auto_full` lets the spec stage stamp a SPEC, and execute and `hm check` proceed on an unstamped one, without asking |
| `second_opinion.models` | §11 |
| `delegation.stages` | `[wrapup]` hands wrapup Steps 1–5 to `stage-delegate` |
| `second_brain` | §10 |
| `wrapup_docs` | docs wrapup updates for each change |

Keys of retired features (`loop.*`, `autonomy.autopilot_persistent`, `autonomy.pipeline`, step
and time caps) stay in the schema and keep their values on re-render, but nothing reads them;
`loop.enabled` and `autonomy.autopilot_persistent` warn once per `make`.

## 14. Retired in 0.64.0

The workflow went from seven stages to four. Retired:

- **Commands**: `hm:review` (now execute's review step), `hm:verify` (now `hm check`), `hm:loop`
  and `hm:loop-p5-batch` (use the host's `/loop`), `hm:configure`.
- **Autopilot** auto-advance (Maker's Advance rule replaced it). The `harness-maker autopilot`
  and `verify` CLI commands still run for old scripts but are hidden from help.
- **Agents**: `stuck`, `security-auditor`, `executor`, `autoloop-coder`.
- **Skills**: `security-scanner`, `verify-before-completion`, `targeted-test-selection`,
  `conditional-router`, `autoloop-driver`, `refdocs-search`.
- **Cursor** as a target (0.63.0); leftover `.cursor/` files are removed only when untouched.

A re-render removes the retired files it shipped, and keeps any you edited.
