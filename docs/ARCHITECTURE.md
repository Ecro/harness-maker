# Architecture

This document describes the harness-maker system at a level where you can understand the design without reading the source. For implementation details, follow the file-path references into `src/harness_maker/`. For the full normative specification, see [`TECH_SPEC.md`](../TECH_SPEC.md).

## 1. What harness-maker Is

A **meta-tool**. The Claude Code ecosystem ships a `.claude/` directory inside every project — that directory contains commands, skills, agents, hooks, settings, and observability glue. harness-maker is a Claude Code plugin whose only job is to **generate, refine, and keep fresh** that `.claude/` directory, tailored to the host project's stack, scale, and lifecycle.

Three design commitments shape every decision below:

1. **Single command.** Users invoke `/harness-maker:make`. Everything else is a flag (`--audit`, `--add`, `--remove`, `--promote`).
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
            │  (+ .cursor/rules/ + .cursor/mcp.json when M14 active) │
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
        │    <user-named>.md  ◀── M3 fused workflows          │
        │    loop.md          ◀── M7 autoloop driver          │
        │    ai-readiness.md  ◀── M5 scored readiness report   │
        │    refresh.md       ◀── M4 anti-rot, manual confirm │
        │  skills/  (11)      ◀── including verify-before,    │
        │                          conditional-router,        │
        │                          refdocs-search,            │
        │                          worktree-isolator, ...     │
        │  agents/  (9)       ◀── M12 reviewer/executor       │
        │                          privilege separation       │
        │  hooks/hooks.json   ◀── telemetry                    │
        │  .worktrees/        ◀── M9 git worktree isolation   │
        │  observability/                                     │
        │    dashboard.md                                     │
        │    metrics.jsonl       ◀── 100% local telemetry     │
        │    refresh/raw-*.jsonl ◀── M4 crawl evidence        │
        │    security/findings-* ◀── M10 5 security gates     │
        └────────────────────────────────────────────────────┘
                                 │
                                 ▼
                  user runs /hm:* against their code
                  (autoloop: M7 + M8 verify-before-completion)
                                 │
                                 ▼
                  weekly /hm:refresh — M4 anti-rot crawl
                  → AskUserQuestion (always manual)
```

## 3. The 14 Mechanisms (M1-M14)

Every mechanism below maps to a module under `src/harness_maker/` and at least one verification check in `.claude-verify.sh`.

### M1 — Profile → Interview → Synthesize → Render Pipeline

The four-stage core. Each stage has a single responsibility and a typed handoff.

- **Profiler** (`profile.py`) inspects the project root for signals: `pyproject.toml`, `package.json`, `Cargo.toml`, `*.overlay`, `.github/workflows/`, presence of `.claude/`, presence of standalone `TECH_SPEC.md`, vault membership. Emits `ProjectProfile`.
- **Interviewer** (`interview.py`) recommends a preset based on the profile, then runs an interactive interview across 10+ override dimensions: workflow naming, reviewers, models, autoloop, anti-rot, worktree, security, context-lint, memory, caching. Also captures `targets` (Claude Code / Cursor) and `recommended_model`. Locale-first; English is the default (`DEFAULT_LOCALE = "en"`) with Korean built-in and unknown locales silently falling back to English, via `i18n.py`. Emits `HarnessConfig`.
- **Synthesizer** (`synthesize.py`) is **purely deterministic** — given a `HarnessConfig`, it produces the same `Blueprint` (a list of `FileEntry`) every time. No LLM call here; this guarantees reproducibility and snapshot testability.
- **Renderer** (`render.py`) walks the `Blueprint`, loads each Jinja2 template, injects context, prepends provenance frontmatter (M13), and writes the result.

The split lets you swap the interview UX (CLI prompt vs `AskUserQuestion`) without touching synthesis, and snapshot-test the synthesizer in isolation.

### M2 — Reconciler (Brownfield Conflict Resolution)

When `.claude/` already exists, the Renderer doesn't write blindly. The `Reconciler` (`reconcile.py`):

1. Indexes every existing file under `.claude/`.
2. Computes the new Blueprint's intended file set.
3. For each collision, reads the existing file's `content_hash` from its provenance frontmatter (M13). If hashes match, the existing file is "ours" — safe to overwrite. If they differ or the frontmatter is missing, it's "theirs" — treat as user-edited.
4. Emits a `ConflictItem` per collision with `decision: keep | replace | both`. In autoloop mode, the decision is automatic from hash comparison; in interactive mode, the user picks.
5. Backs up the entire `.claude/` to `.backup-<date>/` before applying anything.
6. Apply is **ADD-only** — no in-place mutation, no deletes from disk (deletes happen via the backup-and-rewrite pattern).

### M3 — Workflow Engine (Atomic + Fused)

There are exactly **7 atomic stages**: `research`, `spec`, `plan`, `execute`, `review`, `wrapup`, `verify`. Each is a Jinja2 fragment under `templates/stages/<stage>.md.j2` and is **always** exposed as `/hm:<stage>`.

**Workflows** are user-named sequences of stages. The synthesizer emits a workflow seed per preset (e.g. `dev = [plan, execute, review, wrapup]`). The `workflow_fuse.py` module concatenates the relevant stage fragments into a single command file rendered to `.claude/commands/hm/<workflow>.md`. Re-running `/harness-maker:make` extends `harness.yaml.workflows` and re-fuses.

This decouples "what the workflow does" from "how the user calls it" — the same atomic stages back every workflow.

### M4 — Anti-rot Pipeline

The Claude Code ecosystem moves weekly. Skills, agents, and best practices that were optimal on day 1 rot into liabilities by day 90. M4 fights that.

Three stages:

1. **Crawl** (weekly): four sources — Anthropic blog/changelog, GitHub releases (`anthropics/claude-code` by default), arxiv (cs.SE / cs.CL / cs.CR), OSV.dev. Implemented under `src/harness_maker/crawler/`. Raw output to `observability/refresh/raw-<date>.jsonl`.
2. **Filter** (`relevance.py`): LLM scores each item for project-relevance. Threshold starts at 0.7 and adapts ±0.05 based on the recent accept/reject ratio.
3. **Propose** (`templates/commands/hm/refresh.md.j2`): `/hm:refresh` opens an `AskUserQuestion` per surviving item — accept, reject, or defer. **Manual confirm is non-negotiable**: there is no `--auto-apply` path.

This means harness-maker stays current without ever silently changing the user's runtime.

### M5 — Monitoring (3 Metrics)

Three metrics are computed and surfaced in the `/hm:ai-readiness` report:

- **효율** — cache hit % per turn. Computed from telemetry hook output (PostToolUse) with a hybrid schema that works across Claude Code and Cursor IDE (0.5.4+).
- **Health** — 0-100 score across 6 dimensions: docs, tests, CI, observability, security, governance. Implemented in `readiness.py`. Drills down into `agent_quality.py`, which assigns each agent a Platinum/Gold/Silver/Bronze rating against a fixed rubric. A "ceremony penalty" deducts points when an agent has high-process / low-output behavior.
- **fresh** — days since the last `/hm:refresh` accepted at least one proposal.

A **SessionStart drift reminder** hook (`hooks/sessionstart_drift.py`) fires on every session open and warns if the running harness-maker version differs from the version that rendered the harness — alerting users to re-render after a plugin update (0.5.6+).

All telemetry stays local — `metrics.jsonl` is never transmitted.

### M6 — Conditional Router

When `/hm:review` runs, it doesn't blindly call every reviewer. The `conditional_router.py` module inspects the changed-file paths and routes:

- `auth/` or `.env` → security reviewer
- `worker/`, `thread/`, `isr/` → concurrency reviewer
- `*.tsx`, `ui/` → UX reviewer
- perf-critical paths (configurable per project) → performance reviewer
- everything → code reviewer (always)

Override: set `harness.yaml.reviewers.routing: always-all` to call every reviewer on every diff.

### M7 — Autoloop Driver

`/hm:loop "<goal>" [--mode feature|improve] [--time 8h] [--max-iter 30] [--per-iter-workflow X] [--dry-run]` runs an unbounded-token, time-and-iteration-bounded loop. Implemented in `autoloop_driver.py`.

Two modes:

- **feature** (default) — driven by a goal or `--spec` file; coverage-driven adaptive interview extracts features; iterates until all features pass or caps fire.
- **improve** — driven by a quality target or `--target` path; iterates the `exec-rev` workflow until a convergence predicate is met.

Each iteration:

1. Allocates a per-loop worktree at loop start (M9); reuses it for all iterations (0.5.5+).
2. Runs the chosen per-iteration workflow (default: `exec-rev`). Wrapup runs once at loop close, not per iteration.
3. Calls `/hm:verify` (M8) before completion.
4. Cleans up on success; preserves on failure.

Safety: every 5 iterations the driver pings the user; 3 consecutive failures stop the loop.

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

`worktree.py` integrates `git worktree`. By default `/hm:execute` (and optionally `/hm:plan` in `Production`) runs inside a fresh worktree under `.worktrees/<workflow>-<timestamp>/` at the project root. The LLM may only write inside that worktree — enforced by M12's executor agent permissions.

`/hm:loop` allocates **one shared worktree per loop run** (not per iteration), reducing branch churn (0.5.5+). Cleanup uses prefix-match (`phase-*`, `autoloop-*`, `execute-*`) so harness-maker never removes worktrees created by Cursor or other tools in the same `.worktrees/` directory.

Successful runs cleanup the worktree after merging back. Failed runs preserve the worktree as evidence.

### M10 — 5 Security Gates

Implemented in `security_scanner.py`. Findings are written to `observability/security/findings-<date>.jsonl`.

| Gate | Technique | Trigger |
|---|---|---|
| **secrets** | regex + entropy (gitleaks-style) | `pre_commit`, `pre_wrapup`, `refresh` |
| **permissions** | `settings.json` `allow` over-grant detection | `refresh`, `/harness-maker:make` |
| **hook injection** | `hooks.json` AST scan for dangerous commands (`rm -rf`, `curl \| sh`, `eval`) | `pre_wrapup`, `refresh` |
| **dependency CVEs** | OSV.dev lookup against `package-lock.json`, `Cargo.lock`, `requirements.txt` | weekly |
| **prompt injection** | hidden-instruction pattern detection + reviewer/executor privilege split (M12) | LLM call boundary |

### M11 — Context Lint

`context_lint.py` runs at render time. Before the Renderer writes a file, the lint checks length and importance density. On overrun: warn and propose an automatic summary. Configurable via `harness.yaml.context_lint.strict`.

### M12 — Privilege Separation

Reviewer agents and executor agents have **structurally different permissions** in their `settings.json` slot:

- **Reviewer** (`templates/agents/code-reviewer.md.j2`, etc.): `permissions.deny: [Write, Edit, Bash exec]`. Can read and analyze; cannot mutate.
- **Executor** (`templates/agents/executor.md.j2`, `autoloop-coder.md.j2`): `permissions.allow: [Write(.worktrees/**)]`. Can write only inside the active worktree.

Combined with M9, this gives a defense-in-depth model: even if a reviewer is prompt-injected into trying to write, the permission system blocks it. Even if an executor is injected into writing outside the worktree, the path scope blocks it.

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
- **`/hm:refresh`** (M4) compares hashes to detect user edits and refuses to silently overwrite.
- **`phase_<N>_invariants`** check in `.claude-verify.sh` walks every generated file and asserts the first line is `---` — the invariant that makes the other two loops sound.

### M14 — Dual-IDE Rendering (Cursor target) (0.5.0+)

harness-maker renders the same harness for both Claude Code and Cursor IDE. The `targets` field in `HarnessConfig` (values: `claude-code`, `cursor`, or both) drives which files the Renderer emits.

**Single-source assets** (`targets: [claude-code, cursor]` both get these):
- `.claude/agents/`, `.claude/skills/`, `.claude/commands/hm/`, `.claude/hooks/hooks.json`

Cursor 2.4+ reads `.claude/agents/` and `.claude/skills/` natively, so no duplication is needed for those.

**Cursor-only assets** (emitted only when `cursor` ∈ targets):
- `.cursor/rules/harness.mdc` — always-on workflow rules rendered via `_render_cursor_mdc()`, which limits frontmatter to keys Cursor accepts (`description`, `globs`, `alwaysApply`). Our `content_hash` metadata is omitted from the frontmatter to avoid strict-reject.
- `.cursor/mcp.json` — pure JSON (no frontmatter); rendered via `_render_pure_text()`.

**Dual plugin manifest**: `.claude-plugin/plugin.json` for the Claude Code marketplace and `.cursor-plugin/plugin.json` for the Cursor Marketplace. Both manifests must be bumped in sync with `pyproject.toml` and `src/harness_maker/__init__.py` on every version release (4-file invariant).

**Recommended model**: `HarnessConfig.recommended_model` defaults to `claude-opus-4-7` and propagates to agent frontmatter. The harness does **not** rewrite prompts to be model-agnostic — `<thinking>` blocks and Claude-specific patterns are preserved deliberately.

## 4. Preset Comparison

The two presets bracket the design space. Most projects pick one and tune 1-3 dimensions.

| Dimension | Side | Production |
|---|---|---|
| Reviewers | `[code]` (1) | `[code, security, perf, ux, concurrency]` (5) |
| Consensus | cross-check | cross-check |
| Routing | conditional (M6) | conditional (M6) |
| Caching | aggressive | aggressive |
| Workflow seeds | `dev=[plan,execute,review,wrapup]` + `quick=[execute]` | `dev` + `quick` + `careful=[research,spec,plan,execute,review,wrapup,verify]` + `audit=[review]` |
| Default workflow | `dev` | `dev` |
| Model preset_default | sonnet | sonnet |
| Autoloop allowed | true | true |
| Memory files | `failures.md`, `wiki.md` | `failures.md`, `wiki.md` |
| Anti-rot threshold | adaptive (start 0.7) | adaptive (start 0.7) |
| Anti-rot auto-apply | false (always manual) | false (always manual) |
| Hooks | statusline + telemetry | statusline + telemetry |
| Verify-before-completion (M8) | optional | **required** |
| Worktree scope (M9) | `[execute]` | `[execute, plan]` |

The two presets share most defaults intentionally — the gap is concentrated in the multi-reviewer set, the additional `careful`/`audit` workflows, and the mandatory verify gate. This keeps the surface area small for users graduating from `Side` to `Production`.

## 5. Where to Read Next

- **Design rationale & decisions:** [`TECH_SPEC.md`](../TECH_SPEC.md) Section 6 (ADRs + risk register K1-K17)
- **How to extend:** [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **What's verified:** [`.claude-verify.sh`](../.claude-verify.sh) — every mechanism above has at least one phase check
- **Reference patterns:** [`docs/reference/autoloop-pattern.md`](reference/autoloop-pattern.md)
- **Cursor target details:** [`../README.md#cursor-target`](../README.md) — KEEP rule trade-off, recommended model, manual checklist
