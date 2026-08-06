# Architecture

This document describes the harness-maker system at a level where you can understand the design without reading the source. For implementation details, follow the file-path references into `src/harness_maker/`. For the full normative specification, see [`TECH_SPEC.md`](../TECH_SPEC.md).

## 1. What harness-maker Is

A **meta-tool**. The Claude Code ecosystem ships a `.claude/` directory inside every project — that directory contains commands, skills, agents, hooks, settings, and observability glue. harness-maker is a Claude Code plugin whose only job is to **generate, refine, and keep fresh** that `.claude/` directory, tailored to the host project's stack, scale, and lifecycle.

Three design commitments shape every decision below:

1. **Single command.** Users invoke `/harness-maker:make`. Everything else is a flag (`--audit`, `--add`, `--remove`, `--promote`). Interactive onboarding asks locale first, then keeps live setup prompts in that locale.
2. **Two presets, deep override.** `Side` (1 reviewer, lean) and `Production` (5 reviewers, verify-required) cover ~90% of cases. The remaining 10% comes from 10+ override dimensions surfaced in the interview.
3. **Brownfield-safe.** harness-maker never silently overwrites user edits. Provenance frontmatter (M13) and the Reconciler (M2) form a hash-based ours/theirs decision system.

## 2. Data Flow

```
                       ┌──────────────────────┐
   user invokes        │  /harness-maker:make │
   ──────────────────▶ │  [--audit|--add|...] │
                       └──────────┬───────────┘
                                  │
                                  ▼
            ┌─────────────────────────────────────────┐
            │  M1 Pipeline                            │
            │  ─────────                              │
            │  Profiler  ──▶  ProjectProfile          │
            │  (stack, scale, lifecycle, brownfield?) │
            │       │                                 │
            │       ▼                                 │
            │  Interviewer  ──▶  HarnessConfig        │
            │  (preset + 10+ override dims, locale-   │
            │   first via i18n.py)                    │
            │       │                                 │
            │       ▼                                 │
            │  Synthesizer  ──▶  Blueprint            │
            │  (deterministic preset → FileEntry[])   │
            │       │                                 │
            │       ▼                                 │
            │  Renderer  ──▶  files in memory         │
            │  (Jinja2 + provenance frontmatter,      │
            │   M11 context-lint at render time)      │
            └────────────────┬────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
   greenfield                          brownfield
            │                                 │
            │                                 ▼
            │                  ┌──────────────────────────┐
            │                  │  M2 Reconciler           │
            │                  │  index existing .claude/ │
            │                  │  hash-compare via M13    │
            │                  │  per-conflict keep/replace/both
            │                  │  backup → .backup-<date>/│
            │                  └──────────┬───────────────┘
            │                             │
            └─────────────┬───────────────┘
                          │
                          ▼
            ┌──────────────────────────────────────────────────────┐
            │  ADD-only apply to <project>/.claude/                │
            │  (+ .cursor/, .codex/, .agents/, AGENTS.md when targeted) │
            └────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────────────┐
        │  Generated harness (the runtime)                    │
        │  ──────────────────                                 │
        │  harness.yaml          ◀── single source of truth   │
        │  settings.json         ◀── permissions               │
        │  commands/hm/                                       │
        │    research|spec|plan|execute|review|wrapup|verify  │
        │      ◀── M3 atomic stages                           │
        │    loop.md          ◀── M7 autoloop driver          │
        │    ai-readiness.md  ◀── M5 scored readiness report   │
        │    refresh.md       ◀── M4 anti-rot, manual confirm │
        │  second_brain       ◀── typed Obsidian R/W memory    │
        │                          with project namespaces     │
        │  skills/  (12)      ◀── including verify-before,    │
        │                          conditional-router,        │
        │                          refdocs-search,            │
        │                          targeted-test-selection,   │
        │                          worktree-isolator, ...     │
        │  agents/            ◀── M12 reviewer/executor       │
        │                          privilege separation       │
        │  hooks/hooks.json   ◀── telemetry                    │
        │  .worktrees/        ◀── M9 git worktree isolation   │
        │  observability/                                     │
        │    dashboard.md                                     │
        │    metrics-YYYY-MM-DD.jsonl ◀── 100% local         │
        │       telemetry, daily-rotated (ADR-103, 0.7.1)     │
        │    refresh/raw-*.jsonl ◀── M4 crawl evidence        │
        │    security/findings-* ◀── M10 7 security gates     │
        └────────────────────────────────────────────────────┘
                                 │
                                 ▼
                  user runs /hm:* against their code
                  (autoloop: M7 + M8 verify-before-completion)
                                 │
                                 ▼
                  (anti-rot crawl removed — ADR-0007)
                  → structured question (always manual)
```

### Three additional 0.12.0+ flows

The diagram above covers the original render pipeline. Three flows added in 0.12.0 run alongside it:

1. **Detection cache flow (M15)**: `profile.profile()` calls `detection_cache.load_or_run()`, which checks cache freshness against manifest-mtime with a 24h ceiling (per `detection_cache.CACHED_MANIFESTS`). On cache miss, the full detection runs and `detection_cache.write()` persists the result to `~/.cache/harness-maker/profile-<repo-hash>.json`. The cached `ProjectProfile` is what feeds the Interviewer + M16 recommendation registry.
2. **Foreign config import flow (M17)**: `foreign_config.detect()` scans the project root for 6 known foreign-AI-tool configs (cursor rules, claude.md, agents.md, continue, aider, copilot). `foreign_config.llm_map()` calls Anthropic with a sha256-keyed 24h cache and proposes a mapping to harness.yaml axes. The slash command UI in `interview.py` confirms with the user before `foreign_config.apply()` returns a `ChangeSet`. The caller writes via `atomic_write`. Re-renders use `@hm:harness:*` inverted block markers so user content outside the harness-managed region is preserved byte-for-byte (see `docs/reference/block-merge-spec.md`).
3. **Adaptive telemetry flow (M18 + M19)**: `harness_yaml_override` events are captured at two sites — (a) `/hm:configure` exit (primary; computes pre/post yaml diff via `telemetry.compute_yaml_diff()` so uncommitted edits are caught), and (b) the SessionStart drift hook (secondary; git diff since the last recorded `ts`). Both call `telemetry.emit_override()`, which deduplicates on `(ts, axis_path, after)` and appends to `.claude/observability/adaptive/overrides.jsonl`. `/hm:health`'s personalization layer reads that file plus the current harness.yaml plus the ProjectProfile cache and runs `personalization_audit.run_audit()`, which returns a composite-score `PersonalizationPlan` with ranked `PersonalizationActionItem` list (per ADR-011 rubric).

### Worktree artifact janitor

Worktree isolation has an opportunistic cleanup pass at `worktree create`.
`prune_stale(base)` runs before the queue and dirty-base guards so leaked
harness bookkeeping does not become false live-session pressure. It removes
orphan loop markers, removes owned dangling worktree directories only when
they have a `.git` entry and are neither git-registered nor live-marker
referenced, and drains a finalize-stash ref when ANY of: its recorded base
dir is gone (unreachable stash → cruft), its stash object is gc-pruned/dropped
(nothing to restore), or every tracked and untracked stash blob already exists
in `HEAD`. A still-resolvable stash whose content is NOT yet in `HEAD` is
preserved and warned (never auto-dropped — ADR-008), and does not count as live
queue pressure unless its session marker still exists.

### Keep-base-clean churn isolation

The 5-layer cross-session worktree defense only fires correctly if the base
repo is actually clean between sessions. The harness used to dirty its own base
(telemetry writes `.claude/observability/` on every tool call; loop-context,
iter-receipts, render manifest accumulate), so finalize stashed every run and
the queue-guard blocked the next parallel `create`. A single churn source of
truth — `worktree._HARNESS_CHURN_DIRS` (prefix-matched) + `_HARNESS_CHURN_FILES`
(exact-matched), unioned into `_HARNESS_GITIGNORE_PATTERNS` — now drives both
dirt-filters (`_is_harness_artifact` for finalize; the create-guard inherits via
delegation) AND `_ensure_harness_gitignore`, which seeds the patterns into the
user's `.gitignore` at make time and every `worktree create` (idempotent +
subsumption-safe). The filter stays a strict subset (never forgives genuine user
`.claude/agents|skills|commands|harness.yaml` edits), and `.gitignore` itself is
treated as co-managed/non-dirtying so the seeding append cannot re-trip the
guards. wrapup also commits RESEARCH + SPEC so deliverables stop lingering as
untracked dirt (PLAN-worktree-base-artifact-pollution).

## 3. The 19 Mechanisms (M1-M19)

Every mechanism below maps to a module under `src/harness_maker/` and at least one verification check in `.claude-verify.sh`.

### M1 — Profile → Interview → Synthesize → Render Pipeline

The four-stage core. Each stage has a single responsibility and a typed handoff.

- **Profiler** (`profile.py`) inspects the project root for signals: `pyproject.toml`, `package.json`, `Cargo.toml`, `*.overlay`, `.github/workflows/`, presence of `.claude/`, presence of standalone `TECH_SPEC.md`, vault membership. Emits `ProjectProfile`.
- **Interviewer** (`interview.py`) recommends a preset based on the profile, then runs an interactive interview across 10+ override dimensions: workflow naming, reviewers, models, autoloop, anti-rot, worktree, security, context-lint, memory, caching. Also captures `targets` (Claude Code / Cursor) and `recommended_model`. Locale-first; English is the default (`DEFAULT_LOCALE = "en"`) with Korean built-in and unknown locales silently falling back to English, via `i18n.py`. Emits `HarnessConfig`.
- **Synthesizer** (`synthesize.py`) is **purely deterministic** — given a `HarnessConfig`, it produces the same `Blueprint` (a list of `FileEntry`) every time. No LLM call here; this guarantees reproducibility and snapshot testability.
- **Renderer** (`render.py`) walks the `Blueprint`, loads each Jinja2 template, injects context, prepends provenance frontmatter (M13), and writes the result.
- **Second Brain** (`second_brain.py`) treats an Obsidian vault as a typed Markdown graph for stage-aware memory. First-install onboarding is read-first; deeper write-capable setup is configured later. Read/write access is constrained by configured folder allowlists, and writable folders require `second_brain.project_id` in the folder path so several projects can share one vault without writing into the same namespace.

The split lets you swap the interview UX (CLI prompt vs structured question tool) without touching synthesis, and snapshot-test the synthesizer in isolation.

### M2 — Reconciler (Brownfield Conflict Resolution)

When `.claude/` already exists, the Renderer doesn't write blindly. The `Reconciler` (`reconcile.py`):

1. Indexes every existing file under `.claude/`.
2. Computes the new Blueprint's intended file set.
3. For each collision, reads the existing file's `content_hash` from its provenance frontmatter (M13). If hashes match, the existing file is "ours" — safe to overwrite. If they differ or the frontmatter is missing, it's "theirs" — treat as user-edited.
4. Emits a `ConflictItem` per collision with `decision: keep | replace | both`. In autoloop mode, the decision is automatic from hash comparison; in interactive mode, the user picks.
5. Backs up the entire `.claude/` to `.backup-<date>/` before applying anything.
6. Apply is **ADD-only** — no in-place mutation, no deletes from disk (deletes happen via the backup-and-rewrite pattern).

### M3 — Stage Engine (seven atomic stages)

There are exactly **7 atomic stages**: `research`, `spec`, `plan`, `execute`, `review`, `wrapup`, `verify`. Each is a Jinja2 fragment under `templates/stages/<stage>.md.j2` and is **always** exposed as `/hm:<stage>`.

The `research` fragment includes a discovery-lens calibration step so broad trend or roadmap prompts inspect user workflows and adjacent artifacts before narrowing into academic, benchmark, or implementation-only sources.

**Fused workflows were retired in 0.47.0** (`PLAN-harness-diet` ADR-001/002). Until then, user-named stage sequences under `harness.yaml.workflows` were concatenated by `workflow_fuse.py` into a single `/hm:<workflow>` command; that module, the `workflows` / `default_workflow` keys and the five rendered fused commands are all gone. They were 58.6% of the shipped Claude command surface with zero recorded invocations.

Stages are chained instead by `/hm:loop --per-iter-stages execute,review` or by autopilot's `autonomy.pipeline`. `io_utils.load_harness_yaml` strips the two retired keys at LOAD time (one advisory per project), so an old config keeps working without a re-render.

### M4 — Anti-rot Pipeline

The Claude Code ecosystem moves weekly. Skills, agents, and best practices that were optimal on day 1 rot into liabilities by day 90. M4 fights that.

Three stages:

1. **Crawl** (weekly): four sources — Anthropic blog/changelog, GitHub releases (`anthropics/claude-code` by default), arxiv (cs.SE / cs.CL / cs.CR), OSV.dev. Implemented under `src/harness_maker/crawler/`. Raw output to `observability/refresh/raw-<date>.jsonl`.
2. **Filter** (`relevance.py`): LLM scores each item for project-relevance. Threshold starts at 0.7 and adapts ±0.05 based on the recent accept/reject ratio.
3. **Propose**: this step no longer exists. ADR-0007 deleted the crawl, the relevance filter, and `refresh.md.j2` after a production run rejected 11 of 12 surfaced items. The manual-confirm rule it enforced is preserved wherever proposals still reach a user (`/hm:health`'s action items).

This means harness-maker stays current without ever silently changing the user's runtime.

### M5 — Monitoring (3 Metrics)

Three metrics are computed and surfaced in the `/hm:health` report:

- **Efficiency** — cache hit % per turn. Computed from telemetry hook output (PostToolUse) with a hybrid schema that works across Claude Code and Cursor IDE (0.5.4+). 0.7.1 (ADR-103) rotates the on-disk file daily as `metrics-YYYY-MM-DD.jsonl`; readers walk dated shards newest-first via `_metrics_io.iter_recent_entries` and fall back to the legacy `metrics.jsonl` for pre-0.7.1 entries.
- **Health** — 0-100 score across 6 dimensions: docs, tests, CI, observability, security, governance. Implemented in `readiness.py`. Drills down into `agent_quality.py`, which assigns each agent a Platinum/Gold/Silver/Bronze rating against a fixed rubric. A "ceremony penalty" deducts points when an agent has high-process / low-output behavior.
- **fresh** — retired with the crawl (ADR-0007); no longer computed.

A **SessionStart drift reminder** hook (`hooks/sessionstart_drift.py`) fires on every session open and warns if the running harness-maker version differs from the version that rendered the harness — alerting users to re-render after a plugin update (0.5.6+).

The detector (`relevance.detect_version_drift`) compares `harness.yaml.harness_maker_version` (the **stamped** version, formerly named `installed` — renamed in 0.6.2 REVIEW M2 to remove a semantic inversion) against `relevance.latest_installed_version()`, which scans `~/.claude/plugins/cache/harness-maker-local/harness-maker/<v>/` for the highest semver-parseable directory name. **Why scan the cache instead of using the imported `__version__`** (0.6.2 P6): a rendered slash command runs with `uv run --with /path/to/<render-time-version>`, pinning its in-process `__version__` to the version that *rendered* it. The SessionStart hook runs against the live plugin so its `__version__` is current. The two import paths therefore see different `__version__` values; calling the same `detect_version_drift` would return different verdicts. Routing both through `latest_installed_version()` (an external truth source) makes them agree. The function is `@functools.cache`-decorated for sub-100ms session-start latency, with a top-K cap (10) on the cache scan to bound worst-case syscalls on long-lived installs.

All telemetry stays local — `metrics-YYYY-MM-DD.jsonl` is never transmitted. 0.7.1 (ADR-107) added a `tool_input` whitelist for the persisted entries: only `path`, `file_path`, `command`, `target`, `database`, `url`, `query` survive; values are scanned for known-secret prefixes (`sk-`, `ghp_`, `AKIA`, `Bearer …`) and redacted *before* a 256-char cap to ensure a partial-token tail cannot survive truncation. The cwd resolution chain is env-var-first (`CLAUDE_PROJECT_DIR` → `CURSOR_PROJECT_DIR` → typed `workspace.current_dir` → `os.getcwd()`); the bare stdin `cwd` field is intentionally NOT consulted, since prior to 0.7.1 a poisoned PostToolUse payload could redirect metrics writes via that field (ADR-102).

### M6 — Conditional Router

When `/hm:review` runs, it doesn't blindly call every reviewer. The `conditional_router.py` module inspects the changed-file paths and routes:

- `auth/` or `.env` → security reviewer
- `worker/`, `thread/`, `isr/` → concurrency reviewer
- `*.tsx`, `ui/` → UX reviewer
- perf-critical paths (configurable per project) → performance reviewer
- everything → code reviewer (always)

Override: set `harness.yaml.reviewers.routing: always-all` to call every reviewer on every diff.

### M7 — Autoloop Driver

`/hm:loop "<goal>" [--mode feature|improve] [--time 8h] [--max-iter 30] [--per-iter-workflow X] [--dry-run]` runs an unbounded-token, time-and-iteration-bounded loop. The command prompt drives runtime orchestration; `autoloop_driver.py` supplies typed schema and dev-time tests.

Two modes:

- **feature** (default) — driven by a goal or `--spec` file; coverage-driven adaptive interview extracts features; iterates until all features pass or caps fire.
- **improve** — driven by a quality target or `--target` path; reviews first, fixes only when the current state does not already meet the exit checklist.

Each iteration:

1. Allocates a per-loop worktree at loop start (M9); reuses it for all iterations (0.5.5+).
2. Runs the chosen per-iteration stage list (default: `execute,review`). Wrapup runs once at loop close, not per iteration.
3. Runs the 4-gate convergence check: mechanical commands, per-criterion LLM judgment, regression comparison, and a persisted two-iteration streak.
4. Calls `/hm:verify` (M8) before completion.
5. Cleans up on success; preserves on failure.

Safety: every 5 iterations the driver pings the user; time, iteration, repeated-failure, repeated-feature, and ambiguity safety rails stop the loop before it spins indefinitely.

### M8 — Verify-Before-Completion Gate

`verify.py` is invoked automatically before `/hm:wrapup` finishes (and before each autoloop iteration completes). The checklist:

- PLAN/SPEC requirements satisfied
- Regression gate passes
- Health hasn't dropped more than 5 points
- Anti-rot has zero pending high-severity proposals
- Security has zero high-severity findings
- Worktree merges cleanly back to base

Required in the `Production` preset; optional in `Side`.

### M9 — Worktree Isolation

`worktree.py` integrates `git worktree`. Isolation is a single boolean, `harness.yaml`'s `worktree.enabled` (0.48.0 — `scope`, `branch_prefix` and `feature_branch_workflow` were retired by `PLAN-worktree-side-defaults`): ON means **every** `/hm:` stage runs inside the persistent per-task worktree `.worktrees/<slug>/` on branch `hm/<slug>`, which `/hm:wrapup` squash-lands; OFF means no stage creates a worktree and all work happens on the current branch. There is no per-stage scope — the axis proved to be one decision, and the three keys that appeared to subdivide it had no runtime effect. Isolation is a **convention, not a sandbox**: the executor agent is instructed to write only inside that worktree (prompt-level guidance), but its `tools:` list grants unrestricted `Write`/`Edit`/`Bash`, so nothing actually stops it from writing elsewhere. See M12.

`/hm:loop` allocates **one shared worktree per loop run** (not per iteration), reducing branch churn (0.5.5+). `sibling_repos` in `harness.yaml` lets the same isolation session create matching worktrees for related repositories, so cross-repo changes can be reviewed and merged as one logical unit. Cleanup uses prefix-match (`phase-*`, `autoloop-*`, `execute-*`) so harness-maker never removes worktrees created by Cursor or other tools in the same `.worktrees/` directory.

Successful runs cleanup the worktree after merging back. Failed runs preserve the worktree as evidence.

### M10 — 7 Security Gates

Implemented in `security_scanner.py`. Findings are written to `observability/security/findings-<date>.jsonl`.

| Gate | Technique | Trigger |
|---|---|---|
| **secrets** | regex + entropy (gitleaks-style) | `pre_commit`, `pre_wrapup`, `refresh` |
| **permissions** | `settings.json` `allow` over-grant detection | `refresh`, `/harness-maker:make` |
| **hook injection** | `hooks.json` AST scan for dangerous commands (`rm -rf`, `curl \| sh`, `eval`) | `pre_wrapup`, `refresh` |
| **dependency CVEs** | OSV.dev lookup against `package-lock.json`, `Cargo.lock`, `requirements.txt` | weekly |
| **hallucination** (0.7.0+) | AST scan for non-existent imports. 0.7.1 (ADR-105) switched to a pure-filesystem check — `_is_available` walks `sys.path` for `<pkg>/__init__.py` / `<pkg>.py` / `<pkg>/` and never imports the package, so adversarial sys.path entries cannot trigger `__init__.py` side-effects on LLM-generated code. `@functools.lru_cache(maxsize=512)` memoises the lookup; guarded `try/except ImportError` and `except` handler imports are downgraded to P2. | `pre_wrapup` |
| **prod-name guard** (0.7.0+) | Cross-tool sequence detection: walks recent PostToolUse entries via `_metrics_io.iter_recent_entries` and flags windows of N tool calls whose `tool_input.target` contains production-only patterns (`prod`, `production`, the actual deployed bucket name, etc.). 0.7.1 rewrote the matcher with a `collections.deque(maxlen=window)` sliding window for O(N) scan. | `pre_wrapup` |
| **prompt injection** | hidden-instruction pattern detection + reviewer/executor privilege split (M12). Regex first pass + LLM second pass via `scan_prompt_injection_llm`. On any LLM transport error the gate degrades to regex-only with a warning. | LLM call boundary |

### M11 — Context Lint

`context_lint.py` runs at render time. Before the Renderer writes a file, the lint checks length and importance density. On overrun: warn and propose an automatic summary. Configurable via `harness.yaml.context_lint.strict`.

### M12 — Privilege Separation

> **Corrected 2026-07-17 (0.40.0).** This section used to describe a YAML
> `permissions:` block in agent frontmatter (allow/deny lists, including a
> "Write+Edit pairing invariant") as the enforcement mechanism. It never
> enforced anything: **subagent frontmatter has no `permissions:` field**,
> so Claude Code silently ignored every one of those blocks. The blocks
> were deleted from all agent templates rather than left as misleading
> documentation.

Reviewer agents and executor agents are separated by **`tools:`**, the only
thing Claude Code actually binds per-agent:

- **Reviewer** (`templates/agents/code-reviewer.md.j2` and 4 siblings): `tools:` omits `Bash` entirely. This is the real boundary — there is no shell to invoke `rm`, `curl`, or an interpreter through, regardless of anything written in a `deny:` block. Adding `Bash` back would grant an unrestricted shell no frontmatter could narrow.
- **Executor** (`templates/agents/executor.md.j2`): `tools:` includes `Read, Grep, Glob, Write, Edit, Bash` — unrestricted paths and an unrestricted shell. Staying inside `.worktrees/**` and avoiding system paths (`/etc/**`, `~/.ssh/**`, `~/.aws/**`) is **prompt-level guidance**, not a runtime restriction; nothing stops the agent from writing outside the worktree except the instruction saying not to. The old frontmatter `deny:` list (`Write(/etc/**)`, `Edit(/etc/**)`, `Bash(curl * | sh)`, …) never fired for a second reason even before the frontmatter-is-inert fact: `Write(<path>)` rule shapes aren't consulted by the file-permission check at all (only `Edit`/`Read` are), and `Bash(... | ...)` rules are matched per-subcommand after splitting on `&& || ; | &`, so a rule spanning a separator can never match.

The only **real, enforced** permission boundary in harness-maker is the
main session's `settings.json` `permissions.deny`, which is session-wide
(applies identically to the main session and every agent — it cannot
express "this agent may not run `rm`"). It is opt-in via
`harness.yaml.permissions.deny_dangerous: true` and currently renders as:

```json
["Bash(rm:*)", "Edit(/etc/**)", "Edit(~/.ssh/**)", "Edit(~/.aws/**)"]
```

(`Write(/etc/**)` and `Bash(curl * | sh)` were dropped from this list —
both were unmatchable shapes per `permission_syntax.is_matchable_rule`,
guarded by `test_permission_syntax.py`. `curl | sh` detection is delegated
to the `permission_gate` PreToolUse hook instead of a settings rule.)

Per-agent command scoping is not expressible in frontmatter. When it's
needed, the real options are a PreToolUse hook keyed on agent identity, or
a sandbox — both defeated by `--dangerously-skip-permissions` /
`bypassPermissions`.

CLAUDE.md §Security/Permissions v1.6 carries this correction authoritatively.

### M13 — Provenance Frontmatter

Every generated `.md` and `.json` carries frontmatter:

```yaml
---
generated_by: harness-maker
harness_maker_version: "0.1.0"
content_hash: "<sha256 of body>"
source_template: templates/skills/.../SKILL.md.j2
generated_at: "2026-05-03T12:34:56Z"
provenance: synthesized
---
```

Three loops depend on this:

- **Reconciler** (M2) reads `content_hash` to decide ours vs theirs.
- **`reconcile`** (invoked by `/harness-maker:make`) compares hashes to detect user edits and refuses to silently overwrite.
- **`phase_<N>_invariants`** check in `.claude-verify.sh` walks every generated file and asserts the first line is `---` — the invariant that makes the other two loops sound.

### M14 — Multi-Target Rendering (Claude Code, Cursor, Codex)

harness-maker renders the same workflow model for Claude Code, Cursor IDE, and OpenAI Codex CLI. The `targets` field in `HarnessConfig` (values: `claude-code`, `cursor`, `codex`, or any combination) drives which files the Renderer emits.

**Single-source Claude/Cursor assets** (`targets: [claude-code, cursor]` both get these — Cursor reads them natively):
- `.claude/agents/<name>.md`
- `.claude/skills/<name>/SKILL.md`
- `.claude/commands/hm/<name>.md` (verified empirically against kairos 0.5.7 in 0.6.2 — see `tests/cursor-compat/results-2026-05-08.md`; the previously-reserved `_is_cursor_command` dispatch in `render.py` is now annotated as dead code)

**Per-IDE assets** (different content per IDE — both files emitted when `cursor` ∈ targets):
- `.claude/hooks/hooks.json` — Claude Code schema: PascalCase event keys (`PreToolUse`, `PostToolUse`, `Stop`, `PreCompact`) + nested `{matcher, hooks:[{type, command}]}` shape.
- `.cursor/hooks.json` — Cursor-native schema: lowercase camelCase event keys (`preToolUse`, `stop`, `preCompact`) + flat `{matcher, command}` shape + `version: 1`.

**The hooks divergence is by design**, not a bug. The 0.6.2 forensic on the kairos repo (private, harness-maker 0.5.7) traced 4 entries in `metrics.jsonl` — all with `event: "stop"` (lowercase) and Cursor-only `status` / `loop_count` payload fields per `telemetry.py:11` — to the lowercase template, proving Cursor reads its dedicated file with its own schema. Both `templates/cursor/hooks.json.j2` and `templates/hooks/hooks.json.j2` carry Jinja header comments and unit tests (`test_cursor_hooks_uses_lowercase_native_schema`) that fail loudly if a future change attempts to converge them. CLAUDE.md §Plugin structure also documents the divergence authoritatively.

**Cursor-only assets** (emitted only when `cursor` ∈ targets):
- `.cursor/rules/harness.mdc` — always-on workflow rules rendered via `_render_cursor_mdc()`, which limits frontmatter to keys Cursor accepts (`description`, `globs`, `alwaysApply`). Our `content_hash` metadata is omitted from the frontmatter to avoid strict-reject. The `.mdc` line budget is a Cursor authoring guideline (≤500 lines; split recommended past ~200 per CLAUDE.md), **not** enforced by `context_lint.py` — its per-preset `THRESHOLDS` table covers only `CLAUDE.md`/`AGENTS.md`/`agent`/`skill`/`workflow`. Current rendered output is ~133 lines.
- `.cursor/mcp.json` — pure JSON (no frontmatter), rendered via `_render_pure_text()`. Populated from `harness.yaml.mcp_servers` propagated through `HarnessConfig.mcp_servers` and the Jinja context (0.6.2 P5). Empty default `{"mcpServers": {}}` is valid; users add servers manually to their yaml. The `interview.answers_from_harness_yaml` reverse mapper preserves user-edited `mcp_servers` across re-renders, with type validation (`command: str` non-empty, `args: list[str]` optional, `env: dict[str, str]` optional) and a warning log when entries are dropped.

**Codex-only assets** (emitted only when `codex` ∈ targets):
- `AGENTS.md` — Codex's top-level instruction file. It uses HTML metadata and `@hm:user:*` block markers instead of YAML frontmatter so Codex displays clean instructions and user additions survive re-renders.
- `.codex/config.toml` — Codex config with agent registrations.
- `.codex/agents/<name>.toml` — Codex-native agent definitions generated from the same reviewer/executor inventory.
- `.codex/hooks.json` — Codex hook schema, including `PermissionRequest` handling and Codex file-edit tool matchers.
- `.agents/skills/<name>/SKILL.md` — existing harness skills, seven atomic stage skills, and the loop skill in Codex's discovery layout.

Codex TOML files intentionally carry no provenance frontmatter because TOML parsers reject markdown preambles. The Reconciler treats `.codex/*.toml` as replaceable generated config, while `AGENTS.md` is block-merge aware.

**Plugin manifests**: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and `.codex-plugin/plugin.json` describe the same package for each runtime. All three manifests must be bumped in sync with `pyproject.toml` and `src/harness_maker/__init__.py` on every version release.

**Recommended model**: `HarnessConfig.recommended_model` defaults to `opus` and propagates to agent frontmatter. The harness does **not** rewrite prompts to be model-agnostic — `<thinking>` blocks and Claude-specific patterns are preserved deliberately.

**Minimum supported Cursor**: 2.4 (2026-01-22 — first to bundle subagents, skills, Claude Code hooks compatibility). **Recommended**: 3.2+ (2026-04-24 — agent-first redesign, native `/worktree` and `/best-of-n`). The native worktree commands coexist safely with `/hm:execute` because cleanup is prefix-matched (`phase-*`, `autoloop-*`, `execute-*` reserved for harness-maker).

### M15 — Detection Depth (Track A)

`harness_maker.profile.profile()` detects 12+ language stacks via `STACK_MANIFESTS` + `STACK_GLOB_MANIFESTS`. It parses python / node / rust dependency files for known frameworks. The detector also picks up `package_manager` (`uv` / `poetry` / `pip` / `pipenv` / `npm` / `pnpm` / `yarn` / `bun` / `cargo`) and `ci_provider` (`github-actions` / `gitlab-ci` / `circleci` / `jenkins` / `travis`). The result populates `ProjectProfile` and feeds the M16 recommendation registry.

Caching: results are stored at `~/.cache/harness-maker/profile-<repo-hash>.json` with manifest-mtime invalidation + a 24h ceiling, both governed by `detection_cache.CACHED_MANIFESTS`. The cache makes back-to-back `/hm:configure` runs cheap and keeps `/hm:health`'s personalization layer from re-walking the source tree.

Installed-CLI detection is deliberately **outside** this cache. `harness-maker detect-tools --json` (0.49.0) resolves `codex` / `agy` / `cursor` on `PATH` on every call and is not a `ProjectProfile` field: installing a CLI touches no project manifest, so manifest-mtime invalidation would never fire and a cached answer could report a tool installed minutes ago as absent. `installed` means the binary resolves; authentication is never probed.

**Key files**: `src/harness_maker/profile.py`, `src/harness_maker/detection_cache.py`.

### M16 — Recommendation Framework

`harness_maker.recommendation` provides a registry of `recommend_<axis>(profile, project_dir) -> Recommendation | None` functions. Each function declares per-detection `Confidence` (`HIGH` / `MEDIUM` / `LOW`, per ADR-007). The `interview.py` dispatcher (`_dispatch_recommendation`) routes by confidence bucket:

- **HIGH** → silent default, recorded as a yaml comment so the user can see *why* later.
- **MEDIUM** → explicit `AskUserQuestion` so the user explicitly accepts or overrides.
- **LOW** → no surface (we don't show low-confidence guesses).

Tri-IDE payload equivalence is asserted (validator N1: the same `Recommendation` flows through Claude Code, Cursor, and Codex). Backward-compat regression test guards 0.11.x users from silent default changes (validator W3).

**Key files**: `src/harness_maker/recommendation.py`, `src/harness_maker/interview.py`, `src/harness_maker/models.py` (`Confidence`, `Recommendation`, `RecommendationEvidence`, `AdaptiveConfig`).

### M17 — Foreign AI Config Migration (Track D)

`harness_maker.foreign_config` detects 6 known foreign-AI-tool configs in the project, LLM-maps their content to harness.yaml axes (Anthropic call, sha256-keyed 24h cache), and applies single-source re-renders with `@hm:harness:*` inverted block markers (ADR-003 + ADR-009).

`MarkerStyle` dispatch routes by file extension:
- `HTML_COMMENT` for `.md` / `.mdc`
- `HASH_COMMENT` for `.yml` / `.yaml`
- `JSON_KEY` (`_hm_harness` top-level key) for `.json`

0.11.x files (frontmatter `generated_by: harness-maker` + zero `@hm:harness:*` markers in body) are upgraded on first encounter post-0.12.0 — the whole file is rewritten with the new marker family; the second render is a no-op (idempotent). See `docs/reference/block-merge-spec.md` for the marker syntax + reconcile decision tree.

**Key files**: `src/harness_maker/foreign_config.py`, `src/harness_maker/block_merge.py`, `src/harness_maker/templates/foreign-configs/*.j2`.

### M18 — Adaptive Telemetry (Track B start)

`harness_yaml_override` events are captured at two sites:

- **Primary** — `/hm:configure` exit: pre/post yaml diff. Catches uncommitted edits the user just made.
- **Secondary** — SessionStart hook: git diff since the last recorded `ts`. Catches changes made outside `/hm:configure` (e.g., direct yaml edits between sessions).

Dedup key `(ts, axis_path, after)` prevents the two sites from double-recording the same change. The schema is versioned (`schema_version: 1` mandatory per validator C3); the Phase 10 reader skips unknown versions so new schema additions remain forward-compatible.

Storage: `.claude/observability/adaptive/overrides.jsonl` via `atomic_write`. Opt-out via `harness.yaml.adaptive.disable_telemetry: true` (default `false` per ADR-005 default-on). 100% local — `tests/unit/test_no_network.py` asserts no socket call (ADR-005 positive obligation).

**Key files**: `src/harness_maker/telemetry.py`, `src/harness_maker/hooks/sessionstart_drift.py`, `src/harness_maker/cli.py` (configure-exit hook).

### M19 — Personalization Audit

`/hm:health`'s personalization layer computes a composite score from telemetry + harness.yaml + ProjectProfile cache, per ADR-011 locked formulas in `rubrics/personalization.yaml v0`:

```
composite = L1 conversion × 0.4 + L2 stability × 0.3 + L3 cadence × 0.3
```

Tier boundaries: **Bronze** < 40 ≤ **Silver** ≤ 64 < **Gold** ≤ 84 < **Platinum** ≤ 100.

Output: `PersonalizationPlan` with a ranked `PersonalizationActionItem` list, each carrying `evidence = {n_observations, top_3_signals, confidence}`. Items lacking observations *or* signals are dropped (ADR-010 mode C noise mitigation — avoid producing recommendations whose justification is thinner than the recommendation itself).

The runner reuses the `rubric_loader` pattern from `ai_readiness.py` so the v0 calibration is just one YAML file. The rubric itself is provisional; revisit after 30+ projects accumulate audit runs.

**Key files**: `src/harness_maker/personalization_audit.py`, `src/harness_maker/rubrics/personalization.yaml`, `src/harness_maker/templates/commands/hm/personalization-audit.md.j2`.

## 4. Preset Comparison

The two presets bracket the design space. Most projects pick one and tune 1-3 dimensions.

| Dimension | Side | Production |
|---|---|---|
| Reviewers | `[code]` (1) | `[code, security, perf, ux, concurrency]` (5) |
| Consensus | cross-check | cross-check |
| Routing | conditional (M6) | conditional (M6) |
| Caching | aggressive | aggressive |
| Workflow seeds | *(retired in 0.47.0)* | *(retired in 0.47.0)* |
| Default workflow | *(retired in 0.47.0)* | *(retired in 0.47.0)* |
| Model preset_default | sonnet | sonnet |
| Autoloop allowed | true | true |
| Memory files | `failures.md`, `wiki.md`, `pending-proposals.md`, `pending-drift.md`, `session/`, `archive/` | same |
| Anti-rot threshold | adaptive (start 0.7) | adaptive (start 0.7) |
| Anti-rot auto-apply | false (always manual) | false (always manual) |
| Hooks | statusline + telemetry | statusline + telemetry |
| Verify-before-completion (M8) | optional | **required** |
| Worktree isolation (M9) | `enabled: false` | `enabled: true` |
| `adaptive.disable_telemetry` (M18) | `false` (opt-out) | `false` (opt-out) |

The two presets share most defaults intentionally — the gap is concentrated in the multi-reviewer set and the mandatory verify gate (the `careful`/`audit` workflow seeds that used to widen it went away with the fused axis in 0.47.0). This keeps the surface area small for users graduating from `Side` to `Production`.

Telemetry (M18) is default-on for both presets per ADR-005: the audit is only useful with data, so opt-out is set rather than opt-in. No preset variation. The flag flips it off project-wide; there is no per-event consent.

## 5. Where to Read Next

- **Design rationale & decisions:** [`TECH_SPEC.md`](../TECH_SPEC.md) Section 6 (ADRs + risk register K1-K17), and Section 7 "Personalization Architecture" for the deeper M15-M19 detail.
- **How to extend:** [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **What's verified:** [`.claude-verify.sh`](../.claude-verify.sh) — every mechanism above has at least one phase check
- **Reference patterns:** [`docs/reference/autoloop-pattern.md`](reference/autoloop-pattern.md), [`docs/reference/block-merge-spec.md`](reference/block-merge-spec.md) (covers the `@hm:harness:*` inverted marker family used by M17)
- **Target details:** [`../README.md#targets`](../README.md) — Cursor and Codex asset layout, KEEP rule trade-off, recommended model, manual checklist
- **0.12.0 ADRs (in `work-docs/PLAN-personalization-depth-2026-05.md`):**
  - ADR-005 — default-on telemetry + no-network positive obligation
  - ADR-009 — `@hm:harness:*` inverted markers (foreign config re-render)
  - ADR-010 — evidence schema (n_observations / top_3_signals / confidence) for personalization items
  - ADR-011 — locked v0 rubric formulas (L1/L2/L3 + composite + tier boundaries)
