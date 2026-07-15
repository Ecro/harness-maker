# TECH_SPEC: harness-maker

> **Status:** v2.4 (0.9.3 target + autoloop refresh) · **Written:** 2026-05-03 · **Language:** English
> Claude Code / Cursor / Codex harness generator — generates and updates project-specific runtime assets with a single `/harness-maker:make` command. Structured for autonomous builds via autoloop.

## 0. Loop Configuration

```json
{
  "phases": 12,
  "max_iterations_per_phase": 5,
  "max_global_iterations": 100,
  "verify_command": "bash .claude-verify.sh",
  "progress_file": ".claude-progress.json",
  "repo_path": "/home/noel/harness-maker"
}
```

**Loop behavior:**
- All Tasks in each Phase complete → Phase Exit Criteria verified
- Phase Exit Criteria failure: retry up to 5 times → if still failing, record blocker and HALT
- AskUserQuestion calls are forbidden — all decisions defer to this spec + CLAUDE.md (DD#8 autonomous decision protocol)
- Progress state is written atomically to `.claude-progress.json`
- Final Acceptance (Section 5) failure does NOT HALT — report only; user reviews afterward

---

## 1. Product Vision

### Problem Statement
The user (`/home/noel`) operates 22+ Claude-active projects single-handedly. Harness configuration fragmentation across projects is severe:
- 8 projects have no harness at all
- Only 1 (spoton) has a heavy harness
- vault is effectively the main hub
- Command surface consistency ≈ 30%
- Memory standard consistency ≈ 40%

Manual curation across 22 projects × per-item is unsustainable. The boundary between what requires human decision vs. what can be automated needs to be redrawn.

### Solution
**harness-maker** — a multi-target harness generator. A **single meta-command** `/harness-maker:make` generates a *custom harness (commands, skills, agents, hooks, monitoring, anti-rot, worktree, and security assets)* via an interview-driven flow. Claude Code uses `.claude/`; Cursor reuses the same `.claude/` assets and receives `.cursor/` glue; Codex receives `AGENTS.md`, `.codex/`, and `.agents/skills/`. Day-to-day commands use the `/hm:` prefix where slash commands are available, and matching skills where Codex discovers skills. Supports both Brownfield and Greenfield-with-spec projects. Interactive onboarding asks locale first, then keeps live setup prompts and Deep Interview questions in that locale. Obsidian Second Brain support connects a generated harness to a user-owned Markdown vault as typed stage-aware memory; first install is read-first, and writable folders require a `project_id` namespace so multiple projects sharing one vault do not collide.

### Target User
1. **The user themselves (primary)**: Incremental rollout across 22 projects. Dogfood.
2. (Phase 10+) External users — solo developers; marketplace distribution under consideration.

### Success Metrics
- [ ] `/harness-maker:make` generates a complete harness from an empty directory within 10 minutes
- [ ] `/harness-maker:make` reconciles conflicts and applies ADD-only changes against a directory with an existing rich `.claude/`
- [ ] Generated `/hm:dev`, `/hm:loop`, `/hm:monitor`, `/hm:refresh` all function correctly
- [ ] `/hm:refresh` crawls 4 sources → proposes patches → user confirms
- [ ] `/hm:execute` operates inside worktree isolation
- [ ] `/hm:verify` detects 7 categories of security gate violations (sandbox seed vulnerability)
- [ ] All generated files carry provenance frontmatter (hash + version)
- [ ] Reviewer agent is blocked by `settings.json` when attempting `Write` (privilege separation)
- [ ] CLAUDE.md / agent prompt length-limit lint is operational

### NON-GOALS (intentionally excluded — do not change)
- Brainstorming / systematic-debugging pre-gates — user's decision
- Aider-native rendering — not under consideration until a dedicated target model is designed
- Team collaboration features — hiloop's domain
- Cloud backend — 100% local (telemetry included)
- Replacing vault itself — vault remains the hub
- Firmware/embedded team governance automation
- Mode classification (M1-M4) — deprecated, replaced by 2 presets (Side/Production)

---

## 2. Technical Constitution

### Tech Stack
| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Language | Python | 3.12+ | Single language (Bash prohibited) |
| Package Manager | uv | latest | pyproject.toml + uv.lock |
| Type Check | mypy | latest | strict mode, 0 errors |
| Linting | ruff | latest | check + format |
| Testing | pytest | 8+ | mock-first; integration tests run only when INTEGRATION=1 |
| Templates | Jinja2 | 3+ | All rendering |
| YAML | PyYAML | 6+ | harness.yaml parsing |
| LLM SDK | anthropic | latest | Uses Claude Code subscription |
| HTTP | httpx | latest | arxiv / GitHub / OSV.dev API |
| Hash | hashlib (stdlib) | - | sha256 frontmatter |
| RSS | feedparser | latest | Anthropic blog crawl |
| CLI (optional) | typer | latest | Dev tooling only (plugin entry is .md) |
| CI | GitHub Actions | - | lint + test on PR |
| License | MIT | - | LICENSE file |

### Project Structure (Plugin = ~/harness-maker)
```
harness-maker/
├── README.md
├── LICENSE                              # MIT
├── CLAUDE.md                            # autoloop CODER guide
├── TECH_SPEC.md                         # this document (vault symlink target)
├── pyproject.toml                       # uv project
├── uv.lock
├── .gitignore
├── .claude-verify.sh                    # autoloop verify entry point
├── .claude-progress.json                # autoloop runtime state (gitignored)
├── .claude-plugin/
│   └── plugin.json                      # Claude Code official manifest
├── .cursor-plugin/
│   └── plugin.json                      # Cursor marketplace manifest
├── .codex-plugin/
│   └── plugin.json                      # Codex plugin manifest
├── .claude/                             # harness-maker dogfoods itself (Phase 9)
│   └── obsidian.json                    # points to vault path
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── harness_maker/                   # Python package
│       ├── __init__.py                  # __version__ = "0.9.3"
│       ├── cli.py                       # dev tooling (typer)
│       ├── i18n.py                      # locale resolver
│       ├── profile.py                   # signal extraction
│       ├── interview.py                 # preset + dimension interview
│       ├── synthesize.py                # preset + answers → blueprint
│       ├── reconcile.py                 # brownfield conflict resolution
│       ├── render.py                    # Jinja2 render + frontmatter attachment
│       ├── verify.py                    # smoke (yaml lint, hooks parse, frontmatter)
│       ├── modular_edit.py              # --add / --remove
│       ├── workflow_fuse.py             # atomic stages → fused workflow command
│       ├── telemetry.py                 # post-tool-use hook
│       ├── context_lint.py              # length + importance lint
│       ├── provenance.py                # frontmatter attachment and validation
│       ├── _metrics_io.py               # ADR-103: daily-rotated metrics reader
│       ├── _locking.py                  # ADR-106: re-entrant exclusive_lock
│       ├── crawler/
│       │   ├── __init__.py
│       │   ├── anthropic_blog.py
│       │   ├── github_releases.py
│       │   ├── arxiv.py
│       │   ├── osv_dev.py
│       │   └── reference_repos.py
│       ├── relevance.py                 # adaptive threshold filter
│       ├── readiness.py                 # Health 6-dimension calculation
│       ├── agent_quality.py             # Platinum/Gold/Silver/Bronze
│       ├── conditional_router.py        # changed area → reviewer selection
│       ├── worktree.py                  # git worktree lifecycle
│       ├── security_scanner.py          # 7-gate orchestrator (ADR-101)
│       ├── secscan/
│       │   ├── secrets.py
│       │   ├── permissions.py
│       │   ├── hook_injection.py
│       │   ├── dependency_cves.py
│       │   ├── prompt_injection.py
│       │   ├── hallucination.py         # ADR-105: pure-filesystem gate
│       │   └── prod_name_guard.py       # ADR-101: production-name guard
│       └── autoloop_driver.py           # /hm:loop driver
├── commands/                            # meta-tool has exactly 1 command
│   └── make.md                          # /harness-maker:make
├── skills/                              # meta-tool's own skills
│   ├── profile-project/SKILL.md
│   ├── interview-config/SKILL.md
│   ├── synthesize-blueprint/SKILL.md
│   ├── reconcile-brownfield/SKILL.md
│   ├── render-blueprint/SKILL.md
│   ├── verify-harness/SKILL.md
│   └── modular-edit/SKILL.md
├── templates/                           # ★ assets rendered into the user's .claude/
│   ├── harness-yaml/
│   │   ├── Side.yaml.j2
│   │   └── Production.yaml.j2
│   ├── claude-md/
│   │   ├── Side.ko.md.j2
│   │   ├── Side.en.md.j2
│   │   ├── Production.ko.md.j2
│   │   └── Production.en.md.j2
│   ├── settings/
│   │   ├── Side.json.j2
│   │   └── Production.json.j2
│   ├── memory/
│   │   ├── failures.ko.md.j2
│   │   ├── failures.en.md.j2
│   │   ├── wiki.ko.md.j2
│   │   └── wiki.en.md.j2
│   ├── stages/                          # atomic stage prompt fragments
│   │   ├── research.md.j2
│   │   ├── spec.md.j2
│   │   ├── plan.md.j2
│   │   ├── execute.md.j2
│   │   ├── review.md.j2
│   │   ├── wrapup.md.j2
│   │   └── verify.md.j2
│   ├── commands/                        # → user .claude/commands/hm/
│   │   └── hm/
│   │       ├── atomic_command.md.j2     # renders each of the 7 atomics
│   │       ├── workflow_command.md.j2   # renders each fused workflow
│   │       ├── loop.md.j2               # /hm:loop
│   │       ├── monitor.md.j2            # /hm:monitor
│   │       └── refresh.md.j2            # /hm:refresh
│   ├── skills/                          # → user .claude/skills/
│   │   ├── verify-before-completion/SKILL.md.j2
│   │   ├── conditional-router/SKILL.md.j2
│   │   ├── ai-readiness-rubric/SKILL.md.j2
│   │   ├── agent-quality-rubric/SKILL.md.j2
│   │   ├── research-crawler/SKILL.md.j2
│   │   ├── relevance-filter/SKILL.md.j2
│   │   ├── autoloop-driver/SKILL.md.j2
│   │   ├── worktree-isolator/SKILL.md.j2
│   │   ├── security-scanner/SKILL.md.j2
│   │   └── context-linter/SKILL.md.j2
│   ├── agents/                          # → user .claude/agents/
│   │   ├── code-reviewer.md.j2
│   │   ├── security-reviewer.md.j2
│   │   ├── security-auditor.md.j2
│   │   ├── performance-reviewer.md.j2
│   │   ├── ux-reviewer.md.j2
│   │   ├── concurrency-reviewer.md.j2
│   │   ├── consensus-arbiter.md.j2
│   │   ├── autoloop-coder.md.j2
│   │   └── executor.md.j2
│   ├── hooks/
│   │   └── hooks.json.j2
│   └── observability/
│       ├── dashboard.ko.md.j2
│       └── dashboard.en.md.j2
└── tests/
    ├── conftest.py
    ├── unit/                            # unit tests (mock-first)
    │   ├── test_profile.py
    │   ├── test_interview.py
    │   ├── test_synthesize.py
    │   ├── test_reconcile.py
    │   ├── test_render.py
    │   ├── test_verify.py
    │   ├── test_modular_edit.py
    │   ├── test_workflow_fuse.py
    │   ├── test_context_lint.py
    │   ├── test_provenance.py
    │   ├── test_relevance.py
    │   ├── test_readiness.py
    │   ├── test_agent_quality.py
    │   ├── test_conditional_router.py
    │   ├── test_worktree.py
    │   ├── test_security_scanner.py
    │   ├── test_autoloop_driver.py
    │   └── crawler/
    │       ├── test_anthropic_blog.py
    │       ├── test_github_releases.py
    │       ├── test_arxiv.py
    │       └── test_osv_dev.py
    ├── fixtures/                        # synthetic projects for render validation
    │   ├── side-python-cli/             # Side x Python
    │   ├── side-tauri-app/              # Side x Tauri
    │   ├── prod-tauri-app/              # Production x Tauri
    │   └── prod-firmware/               # Production x C/Zephyr
    ├── snapshot/                        # expected blueprint snapshots
    │   ├── side-python-cli.expected.yaml
    │   ├── side-tauri-app.expected.yaml
    │   ├── prod-tauri-app.expected.yaml
    │   └── prod-firmware.expected.yaml
    ├── integration/                     # run only when INTEGRATION=1
    │   ├── test_make_greenfield.py
    │   ├── test_make_brownfield.py
    │   ├── test_refresh_real_crawl.py
    │   └── test_loop_minimal.py
    └── e2e/
        └── test_dogfood_sandbox.py
```

### Code Style
- 1-line module docstring at the top of every file (states module purpose)
- Function docstrings: WHY only (WHAT is expressed by the code)
- Comments minimal — non-obvious cases only
- Variable and function names in English; user-facing output follows locale
- Error messages: Korean when locale=ko, system errors left in English verbatim
- mypy strict must pass (Any prohibited, explicit type hints required)
- ruff all selected rules must pass (rulesets: E, F, W, I, N, UP, B, A, C4, RET, SIM, PT)

### Git Policy
- Commit format: `<type>: <subject>` or autoloop auto-format `autoloop(harness-maker): phase N - <name>`
- type: `feat | fix | chore | ci | test | docs | refactor`
- **No remote** — local commits only. Push prohibited.
- Auto-commit runs at the wrapup stage of every phase

### External API Policy
- LLM calls go through Claude Code subscription (no API key required)
- arxiv / GitHub / OSV.dev: unauthenticated, shared cache at `~/.cache/harness-maker/`
- External calls use fixture mocks by default. Real calls only when INTEGRATION=1 env is set.

### Security / Permissions (v1.6, revised REVIEW-2026-05-08)
- **Reviewer agent** (code, security, perf, ux, concurrency, security-auditor, consensus-arbiter):
  - allow: `[Read(*), Grep(*), Glob(*), Bash(git diff:*), Bash(git log:*), Bash(git status:*)]`
  - deny: `[Write(*), Edit(*), Bash(rm:*), Bash(curl:*), Bash(npm:*), Bash(eval *), Bash(python:*), Bash(node:*), Bash(sh:*), Bash(bash:*)]`
  - **Why interpreter denies** (0.6.2 REVIEW M7): blocking only `Bash(rm:*)` can be bypassed via `Bash(python -c "import os; os.system('rm …')")`. All interpreter invocations are denied.
- **Executor agent** (autoloop-coder, executor):
  - allow: `[Read(*), Grep(*), Glob(*), Write(.worktrees/**), Edit(.worktrees/**), Bash(uv run:*), Bash(pytest:*), Bash(npm test:*), Bash(cargo test:*), Bash(git diff:*), Bash(git log:*), Bash(git status:*)]`
  - deny: `[Write(/etc/**), Write(~/.ssh/**), Write(~/.aws/**), Edit(/etc/**), Edit(~/.ssh/**), Edit(~/.aws/**), Bash(curl * | sh), Bash(eval *), Bash(rm -rf /:*)]`
  - **Why Edit/Write pairing** (0.6.2 REVIEW M1): denying only `Write(/etc/**)` still allows `Edit(/etc/sudoers)` to modify the same file. All system paths require both Write and Edit to be denied as a pair.
- Security gates expanded from 5 to 7 in 0.7.1 (ADR-101): added hallucination gate (pure-filesystem, never imports — ADR-105) and production-name guard.
- All generated files include frontmatter:
  ```yaml
  generated_by: harness-maker
  harness_maker_version: "0.9.3"
  generated_at: "<ISO-8601>"
  source_template: "templates/<path>"
  content_hash: "sha256:<hex>"
  provenance: "official"  # official | community | user-modified
  ```

### Telemetry (ADR-102, ADR-103)
- cwd resolution order: `CLAUDE_PROJECT_DIR → CURSOR_PROJECT_DIR → workspace.current_dir → os.getcwd()`. Stdin `cwd` is not consulted.
- Metrics rotate daily as `metrics-YYYY-MM-DD.jsonl`. Reader: `harness_maker._metrics_io.iter_recent_entries` (ADR-103).
- Read-staleness policy: doc-only; no LOCK_SH (ADR-104).
- tool_input whitelist + secret-prefix redaction (`sk-` / `ghp_` / `AKIA` / `Bearer`) applied before the 256-char cap (ADR-107).
- drift_monitor XML fence uses open+close defang (ADR-108).
- `_locking.exclusive_lock` is re-entrant via `threading.local` (ADR-106).
- 100% local telemetry — no external transmission.

### Context Lint (v1.6)
| Asset | Side limit | Production limit |
|---|---|---|
| CLAUDE.md | 200 lines | 500 lines |
| agent prompt | 100 lines | 200 lines |
| skill SKILL.md | 50 lines | 150 lines |
| workflow command (fused) | 300 lines | 600 lines |

When exceeded, the renderer emits a warning (override: `harness.yaml.context_lint.strict: false`).

---

## 3. Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                              User                                     │
│                  /harness-maker:make  (single entry point)            │
│           [--audit | --add X | --remove X | --promote]                │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
            ┌────────────────┴─────────────────────────┐
            │   harness-maker plugin (meta-tool)        │
            │   Role: generate and update user .claude/ │
            ├──────────────────────────────────────────┤
            │  ① Profiler          (signal extraction)  │
            │  ② Interviewer       (Preset + 10+ dims)  │
            │  ③ Synthesizer       (preset → blueprint) │
            │  ④ Reconciler        (Brownfield conflicts)│
            │  ⑤ Renderer          (Jinja2 + frontmatter)│
            │  ⑥ Verifier          (smoke verification) │
            │  ⑦ ModularEditor     (--add / --remove)   │
            │  ⑧ I18n              (locale awareness)   │
            │   Self-update: Claude Code plugin auto-update │
            └──────────────────────────────────────────┘
                             │  generate · render
                             ▼
        ┌─────────────────────────────────────────────────────┐
        │  <project>/.claude/  (generated harness = all runtime)  │
        │  ├── harness.yaml       (single source of truth)     │
        │  ├── settings.json      (permissions)                │
        │  ├── commands/                                        │
        │  │   └── hm/                                          │
        │  │       ├── research.md ┐                            │
        │  │       ├── spec.md     │                            │
        │  │       ├── plan.md     ├ atomic stages (always 7)  │
        │  │       ├── execute.md  │   /hm:<stage>              │
        │  │       ├── review.md   │                            │
        │  │       ├── wrapup.md   │                            │
        │  │       ├── verify.md   ┘                            │
        │  │       ├── dev.md      ┐                            │
        │  │       ├── careful.md  ├ workflows (user-named)     │
        │  │       ├── ...         ┘                            │
        │  │       ├── loop.md       → /hm:loop                 │
        │  │       ├── monitor.md    → /hm:monitor              │
        │  │       └── refresh.md    → /hm:refresh (anti-rot)   │
        │  ├── skills/  (9 skills)                              │
        │  ├── agents/  (14 agents)                             │
        │  ├── hooks/hooks.json (telemetry)                     │
        │  ├── .worktrees/  (gitignored)                        │
        │  └── observability/                                    │
        │      ├── dashboard.md                                 │
        │      ├── metrics.jsonl                                │
        │      ├── refresh/                                      │
        │      │   ├── raw-<date>.jsonl                        │
        │      │   └── proposed-<date>.md                       │
        │      └── security/                                     │
        │          └── findings-<date>.jsonl                   │
        └─────────────────────────────────────────────────────┘
```

### Data Model (Core Pydantic Models)

```python
# src/harness_maker/models.py

from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field

class Locale(str, Enum):
    KO = "ko"
    EN = "en"

class Preset(str, Enum):
    SIDE = "Side"
    PRODUCTION = "Production"

class ModelTier(str, Enum):
    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"

class AtomicStage(str, Enum):
    RESEARCH = "research"
    SPEC = "spec"
    PLAN = "plan"
    EXECUTE = "execute"
    REVIEW = "review"
    WRAPUP = "wrapup"
    VERIFY = "verify"

class ProjectProfile(BaseModel):
    """Profiler output."""
    stack: list[str]
    scale: str  # small | medium | large
    lifecycle: str  # experiment | active | maintenance
    existing_dotclaude: bool
    spec_only: bool  # True when only TECH_SPEC.md is present
    vault_member: bool

class WorkflowDef(BaseModel):
    """User-named workflow (fused stages)."""
    name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    stages: list[AtomicStage]

class HarnessConfig(BaseModel):
    """harness.yaml schema."""
    locale: Locale = Locale.KO
    preset: Preset = Preset.SIDE
    workflows: dict[str, list[AtomicStage]]
    default_workflow: str
    execution: dict  # { default: "step" | "autoloop" }
    reviewers: dict  # { list, consensus, routing }
    caching: str  # aggressive | conservative | adaptive | off
    hooks: dict  # { telemetry-collector }
    memory: dict  # { files: [failures.md, wiki.md] }
    autoloop: dict  # { allowed, default_time_h, default_max_iter }
    anti_rot: dict  # { threshold, auto_apply, schedule }
    dashboard: dict  # { path }
    models: dict  # { preset_default, stages, agents }
    worktree: dict  # { enabled, base_dir, cleanup, scope, merge_strategy }
    security: dict  # { enabled, scan_on, checks, on_finding }
    context_lint: dict  # { strict }

class Blueprint(BaseModel):
    """Synthesizer output."""
    config: HarnessConfig
    files: list["FileEntry"]
    
class FileEntry(BaseModel):
    """One file to render."""
    path: Path  # relative path such as .claude/commands/hm/dev.md
    template: str  # templates/commands/hm/workflow_command.md.j2
    context: dict  # Jinja2 context vars
    frontmatter: dict  # provenance fields

class ReconcileDecision(str, Enum):
    KEEP = "keep"
    REPLACE = "replace"
    BOTH = "both"

class ConflictItem(BaseModel):
    existing_path: Path
    new_path: Path
    decision: ReconcileDecision | None = None
```

### Core Mechanisms (all implemented in Phases 4–8)

**(M1) Profiler → Interviewer → Synthesizer → Renderer pipeline (Phase 2)**
1. Profiler detects stack / scale / lifecycle / existing_dotclaude / spec_only
2. Interviewer presents preset recommendation + 10+ dimension override questions (workflow naming, reviewers, models, autoloop, anti-rot, worktree, security, context_lint, memory, caching). Additional axes: `targets` (claude-code / cursor / both), `recommended_model` (default: claude-opus-4-7). Locale default is English (DEFAULT_LOCALE="en"); Korean messages are built-in; unsupported locales fall back to en silently.
3. Synthesizer performs deterministic mapping → Blueprint
4. Renderer attaches Jinja2 + provenance frontmatter and writes to .claude/ (when M14 is active, also writes to .cursor/)

**(M2) Reconciler — Brownfield Conflict Resolution (Phase 5)**
- Indexes existing .claude/ → identifies N conflict candidates against the new blueprint
- Per-item user choice (keep/replace/both) — in autoloop environments, decisions are made automatically based on frontmatter hash
- Hash match = ours (safe to overwrite); hash absent/mismatch = user or third-party origin (preserve)
- Backup → `.claude/.backup-<date>/` → ADD-only apply

**(M3) Workflow Engine — atomic + fused (Phase 5)**
- 7 atomic stages → each automatically exposed as `/hm:<stage>`
- Workflow = user-named stage sequence → Renderer synthesizes fragments → single `/hm:<name>` command
- Defined under `harness.yaml.workflows` key; additional workflows can be added by re-running `/harness-maker:make`
- `/hm:research` calibrates search lenses before gathering; broad trend and roadmap prompts must run the user-workflow/product opportunity lens before academic, benchmark, or architecture-only searches.

**(M4) Anti-rot (Phase 4)**
3-stage pipeline:
1. Crawl (weekly): Anthropic blog/changelog + GitHub releases (`anthropics/claude-code` by default) + arxiv (cs.SE/cs.CL/cs.CR) + OSV.dev
2. Filter (LLM): adaptive threshold (starts at 0.7, adjusts ±0.05 based on accept/reject ratio)
3. Propose: `/hm:refresh` issues AskUserQuestion (accept/reject/defer). **Manual confirm always required.**

**(M5) Monitoring — 3 metrics (Phase 3)**
- Efficiency (cache hit %) — collected every turn, reported in `/hm:ai-readiness` report. Collected via PostToolUse telemetry hook (0.5.4+ hybrid schema: shared by Claude Code and Cursor IDE). ADR-103: `metrics.jsonl` is rotated daily; use `_metrics_io.iter_recent_entries` to read across rotation boundaries.
- Health (0–100) — 6-dim (docs/tests/CI/obs/security/governance) + Agent quality drill-down (Platinum/Gold/Silver/Bronze) + ceremony penalty
- Freshness (days since refresh)
- **SessionStart drift reminder** (0.5.6+): warns at session start when the running harness-maker version differs from the version that rendered the current harness (sessionstart_drift.py hook)
- Telemetry is 100% local (`metrics.jsonl` — zero external transmission)

**(M6) Conditional Router (Phase 5)**
- Changed-file region → automatic reviewer selection
- auth/.env → security; perf-critical → performance; ui/.tsx → ux; worker/thread/isr → concurrency
- Override: `harness.yaml.reviewers.routing: always-all`

**(M7) Autoloop driver (Phase 6)**
- `/hm:loop "<goal>" [--mode feature|improve] [--time 8h] [--max-iter 30] [--per-iter-workflow X] [--dry-run]`
- **feature mode** (default): goal/spec-driven, coverage-driven adaptive interview → iterates until convergence
- **improve mode** (0.4.7+): quality-target / `--target`-path driven; repeats exec-rev cycles until the convergence predicate is satisfied
- Token budget is unlimited; only time and iteration count are limited
- **Single worktree per loop** (0.5.5+): one worktree is created at loop start and shared across all iterations; per-iter-workflow defaults to exec-rev (wrapup runs once at loop close). ADR-106: worktree acquisition uses a re-entrant flock to prevent concurrent loop invocations from racing on the same worktree path.
- User ping every 5 iterations; 3 consecutive failures → stop

**(M8) Verify-before-completion gate (Phase 6)**
- Invoked automatically just before `/hm:wrapup` or autoloop iteration completion
- Checklist: PLAN/SPEC fulfilled / regression gate / Health within -5 / Anti-rot pending / 0 security high findings / worktree mergeable

**(M9) Worktree isolation (Phase 7)**
- `/hm:execute` automatically creates a git worktree (`.worktrees/<workflow>-<ts>/` — relative to project root, not inside `.claude/`)
- LLM modifies files only within the worktree
- Cleanup on success; preserved on failure
- Prefix-match cleanup (`phase-*`, `autoloop-*`, `execute-*`): does not touch worktrees owned by other tools even when Cursor shares the same `.worktrees/` directory. `worktree create` now runs an opportunistic janitor before its guards: orphan markers and dangling owned worktrees are removed, stale finalize-stash refs are preserved unless their tracked and untracked content is already in `HEAD`, and queue pressure counts only live refs with active session markers. ADR-106: the re-entrant flock guards the cleanup path as well, ensuring concurrent wrapup and loop-close do not double-free the same worktree.

**(M10) 7 Security Gates (Phase 7)**
| Check | Technique | Trigger |
|---|---|---|
| secrets | regex + entropy (gitleaks-style) | pre_commit · pre_wrapup · refresh |
| permissions | settings.json `allow` over-expansion check | refresh · /harness-maker:make |
| hook injection | hooks.json dangerous-command AST (rm -rf, curl pipe sh, eval) | pre_wrapup · refresh |
| dependency CVEs | OSV.dev lookup (package-lock / Cargo.lock / requirements.txt) | weekly |
| prompt injection | hidden-instruction patterns + privilege-separation architecture | before each LLM call |
| hallucination guard | LLM output cross-checked against known identifiers before apply | pre_wrapup · autoloop iter |
| prod-name guard | blocks use of production resource names (DBs, buckets) in generated commands | pre_commit · pre_wrapup |

(Gate count raised from 5 to 7 in 0.7.1: hallucination guard and prod-name guard added.)

**(M11) Context Lint (Phase 8)**
- Length and importance check run immediately before Renderer apply. Violations emit a warning and automatically suggest a summary.

**(M12) Privilege Separation (Phase 8, hardened 0.7.1)**
- Agent YAML frontmatter `permissions: {allow, deny}` (addresses Cursor 2.5+ subagent permission-inheritance gap — parent-to-child cascade does not occur; permissions must be declared per-agent explicitly)
- Reviewer: deny `[Write(*), Edit(*), Bash(rm|curl|npm|eval|python|node|sh|bash:*)]` — blocks interpreter-based bypass
- Executor: allow `[Write(.worktrees/**), Edit(.worktrees/**), Bash(uv run|pytest|...)]`; deny system paths as Write **+ Edit pairs** `[Write(/etc/**), Edit(/etc/**), Write(~/.ssh/**), Edit(~/.ssh/**), Write(~/.aws/**), Edit(~/.aws/**)]`
- Combined with Worktree isolation → dual-layer defense of isolation and separation

**(M13) Provenance Frontmatter (Phase 8)**
- All generated assets carry a frontmatter header (generated_by, harness_maker_version, content_hash, source_template, generated_at, provenance)
- `/hm:refresh` compares hashes → detects user modifications → blocks silent overwrite
- Brownfield reconcile uses frontmatter to distinguish ours from theirs
- Version numbers must be updated in **5 files simultaneously**: `.claude-plugin/plugin.json` · `.cursor-plugin/plugin.json` · `.codex-plugin/plugin.json` · `pyproject.toml` · `src/harness_maker/__init__.py`. Missing any one causes a runtime or marketplace manifest to report the previous version. ADR-108: when rendering drift diffs, XML fence delimiters are defanged (both open and close tags) to prevent the diff content from being interpreted as live tool calls.

**(M14) Multi-target rendering — Claude Code, Cursor, Codex**
- `HarnessConfig.targets: list[Target]` — user makes an explicit selection during the interview (auto-detection is prohibited)
- Single-source `.claude/` assets (agents, skills, commands): Cursor 2.4+ reads these natively, so Claude Code and Cursor share one copy
- Cursor-only assets (rendered only when `cursor` is present in `targets`):
  - `.cursor/rules/harness.mdc` — `_render_cursor_mdc()`: includes only Cursor-accepted frontmatter fields (description/globs/alwaysApply); excludes content_hash
  - `.cursor/mcp.json` — `_render_pure_text()`: pure JSON, zero frontmatter
- Codex-only assets (rendered only when `codex` is present in `targets`):
  - `AGENTS.md` — top-level instructions with HTML metadata and `@hm:user:*` block markers
  - `.codex/config.toml` and `.codex/agents/*.toml` — pure TOML config and agent registrations
  - `.codex/hooks.json` — Codex hook schema, including `PermissionRequest` handling
  - `.agents/skills/*/SKILL.md` — existing skills plus generated stage, workflow, and loop trigger skills
- Plugin manifests: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json` — version synchronization is mandatory
- `recommended_model: claude-opus-4-7` — propagated to agent frontmatter. User override permitted. Prompts themselves are not neutralized for model (`<thinking>` and other Claude-specific expressions are preserved). ADR-107: tool_input fields passed through telemetry hooks are filtered against a whitelist; any field matching a secret pattern (API keys, tokens, passwords) is redacted before writing to `metrics.jsonl`.

### Preset Default Comparison

| Dimension | Side | Production |
|---|---|---|
| Reviewers | `[code]` (1) | `[code, security, perf, ux, concurrency]` (5) |
| Consensus | cross-check | cross-check |
| Routing | conditional | conditional |
| Caching | aggressive | aggressive |
| Recommended workflow seeds | dev=[plan,execute,review,wrapup] + quick=[execute] | above + careful=[research,spec,plan,execute,review,wrapup,verify] + audit=[review] |
| default_workflow | dev | dev |
| Model preset_default | sonnet | sonnet |
| Autoloop allowed | true | true |
| Memory | failures.md + wiki.md | failures.md + wiki.md |
| Anti-rot threshold | adaptive (0.7) | adaptive (0.7) |
| Anti-rot auto_apply | false | false |
| Hooks | telemetry | telemetry |
| Verify-before-completion | optional | required |
| Worktree scope | [execute] | [execute, plan] |
| Security on_finding.high | warn | block |
| Context lint | enabled | enabled (stricter) |
| Approximate file count | 25–30 | 35–45 |

---

## 4. Implementation Phases

### Phase 1: Project Scaffold + Plugin Manifest + i18n MVP

**Objective:** Python package + uv + official plugin manifest + i18n module + Q1 locale working.

**Research targets (autoloop Stage 1 auto-fetch):**
- Claude Code plugin manifest spec: https://code.claude.com/docs/en/plugins
- Claude Code plugins reference (full schema): https://code.claude.com/docs/en/plugins-reference
- uv usage: https://docs.astral.sh/uv/
- pyproject.toml schema: https://packaging.python.org/en/latest/specifications/pyproject-toml/

#### Tasks

- **Task 1.0: Environment precheck (fail fast)**
  - Do: Validate build environment — (a) `command -v uv` (confirm uv is installed; if missing, print install instructions and STOP), (b) `python3 --version` is 3.12+ (if not, STOP), (c) `command -v git` and `git rev-parse --git-dir` (confirm current repo is git-initialized — it should already be), (d) `mkdir -p ~/.cache/harness-maker && touch ~/.cache/harness-maker/.write-test && rm ~/.cache/harness-maker/.write-test` (confirm cache directory is writable). Proceed only if all checks pass; on any failure, print a clear error message and STOP.
  - Files: invoke only `phase_1_env` in `.claude-verify.sh` (no new separate file — the verify script handles environment validation)
  - Done when: `bash .claude-verify.sh phase_1_env` exits 0
  - Verify: `bash .claude-verify.sh phase_1_env`
  - Commit: (no commit — verify-only task; if env is OK, proceed to next task)

- **Task 1.1: uv project initialization**
  - Do: Run `uv init --package` then configure pyproject.toml — name="harness-maker", version="0.1.0", python ">=3.12", license="MIT", deps=[jinja2>=3, pyyaml>=6, pydantic>=2, anthropic, httpx, feedparser, typer, rich], dev=[pytest>=8, pytest-asyncio, ruff, mypy]. ruff config (E,F,W,I,N,UP,B,A,C4,RET,SIM,PT ruleset). mypy strict.
  - Files: `pyproject.toml`, `uv.lock`, `src/harness_maker/__init__.py` (with `__version__ = "0.1.0"`)
  - Done when: `uv sync` succeeds, `uv run python -c "import harness_maker; print(harness_maker.__version__)"` prints "0.1.0"
  - Verify: `bash .claude-verify.sh phase_1_uv`
  - Commit: `feat(phase1): initialize uv project with core dependencies`

- **Task 1.2: Official Plugin manifest**
  - Do: Create `.claude-plugin/plugin.json` — name="harness-maker", description="Auto-generate project-tailored harness + anti-rot + monitoring", version="0.1.0", author={name: "noel"}, license="MIT". Comply with official spec — do not place any other directories inside `.claude-plugin/`.
  - Files: `.claude-plugin/plugin.json`
  - Done when: `jq -r .name .claude-plugin/plugin.json` returns "harness-maker"
  - Verify: `bash .claude-verify.sh phase_1_manifest`
  - Commit: `feat(phase1): add Claude Code plugin manifest`

- **Task 1.3: Meta-tool entry command**
  - Do: Create `commands/make.md` — defines the `/harness-maker:make` command. Single slash command. argparse: `--audit, --add, --remove, --promote`. Body is a placeholder ("Phase 2 implementation pending") + on invocation calls `python -m harness_maker.cli make $ARGUMENTS`.
  - Files: `commands/make.md`, `src/harness_maker/cli.py` (typer skeleton)
  - Done when: `cat commands/make.md` shows `/harness-maker:make` routing, `uv run python -m harness_maker.cli --help` works normally
  - Verify: `bash .claude-verify.sh phase_1_command`
  - Commit: `feat(phase1): add /harness-maker:make entry command`

- **Task 1.4: i18n module + Q1 locale**
  - Do: Implement `src/harness_maker/i18n.py`. `resolve_locale(project_dir: Path) -> Locale` — prefer the `locale` key in `.claude/harness.yaml`; return None if absent (caller handles Q1 flow). `t(key: str, locale: Locale, **vars) -> str` — message catalog lookup. Catalog lives in `src/harness_maker/i18n_messages.py` (dict). Minimum keys: `q1_choose_language`, `apply_done`, `error_no_yaml`. Test: `tests/unit/test_i18n.py` — None when locale is missing, ko/en message lookup tests.
  - Files: `src/harness_maker/i18n.py`, `src/harness_maker/i18n_messages.py`, `tests/unit/test_i18n.py`
  - Done when: `uv run pytest tests/unit/test_i18n.py -v` passes
  - Verify: `bash .claude-verify.sh phase_1_i18n`
  - Commit: `feat(phase1): implement i18n module with ko/en messages`

- **Task 1.5: README + LICENSE + CI skeleton**
  - Do: `README.md` (1 page — project purpose, Quick Start placeholder, License). `LICENSE` (MIT, copyright "noel"). `.github/workflows/ci.yml` — uv setup → ruff check → ruff format --check → mypy --strict → pytest. matrix: python 3.12.
  - Files: `README.md`, `LICENSE`, `.github/workflows/ci.yml`
  - Done when: all 3 files exist, ci.yml calls ruff+mypy+pytest
  - Verify: `bash .claude-verify.sh phase_1_meta`
  - Commit: `chore(phase1): add README, MIT LICENSE, CI workflow`

**Phase 1 Exit Criteria:**
```bash
bash .claude-verify.sh phase_1_env \
  && uv sync \
  && uv run python -c "from harness_maker import __version__; assert __version__ == '0.1.0'" \
  && jq -r .name .claude-plugin/plugin.json | grep -q '^harness-maker$' \
  && test -f commands/make.md \
  && uv run pytest tests/unit/test_i18n.py -v \
  && uv run ruff check src/ \
  && uv run mypy --strict src/ \
  && test -f README.md && test -f LICENSE && test -f .github/workflows/ci.yml \
  && bash .claude-verify.sh phase_1_invariants
```

---

### Phase 2: Foundations — Pydantic Models + Profiler + Interviewer

**Objective:** Secure the building blocks for the Pipeline (Phase 3). Models, signal extraction, and interview all pass unit tests.

**Research targets (autoloop Stage 1 auto-fetch):**
- Pydantic v2 patterns: https://docs.pydantic.dev/latest/
- AskUserQuestion tool spec (Claude Code SDK): https://code.claude.com/docs/en/sub-agents

#### Tasks

- **Task 2.1: Pydantic model definitions**
  - Do: Implement all models from Section 3 Data Model in `src/harness_maker/models.py` (Locale, Preset, ModelTier, AtomicStage, ProjectProfile, WorkflowDef, HarnessConfig, Blueprint, FileEntry, ReconcileDecision, ConflictItem). pydantic v2 strict.
  - Files: `src/harness_maker/models.py`, `tests/unit/test_models.py`
  - Done when: `uv run python -c "from harness_maker.models import HarnessConfig, Blueprint, ProjectProfile"` succeeds, model validation tests pass
  - Verify: `bash .claude-verify.sh phase_2_models`
  - Commit: `feat(phase2): define Pydantic models for harness config and blueprint`

- **Task 2.2: Profiler implementation**
  - Do: `src/harness_maker/profile.py` — `profile(project_dir: Path) -> ProjectProfile`. Signals: (a) stack — check for package.json/pyproject.toml/Cargo.toml/CMakeLists.txt/go.mod, (b) scale — file count < 50 small / 50-500 medium / >500 large, (c) lifecycle — git commit frequency (commits in last 30 days), (d) existing_dotclaude — whether `.claude/` exists, (e) spec_only — `TECH_SPEC.md` present + 0 code files → true, (f) vault_member — `.claude/obsidian.json` exists. Unit test with mock signals.
  - Files: `src/harness_maker/profile.py`, `tests/unit/test_profile.py`
  - Done when: calling profile on 4 fixture stub directories (fleshed out in Phase 3) returns the expected ProjectProfile
  - Verify: `bash .claude-verify.sh phase_2_profile`
  - Commit: `feat(phase2): implement Profiler with multi-stack detection`

- **Task 2.3: Interviewer implementation**
  - Do: `src/harness_maker/interview.py` — `interview(profile: ProjectProfile, autoloop_mode: bool = False) -> dict[str, Any]`. When autoloop_mode=True, auto-adopt all defaults (no AskUserQuestion calls). In interactive mode, recommend a preset and ask 10+ dimension questions: workflow names, default_workflow, reviewers, consensus, caching, models, autoloop, memory, anti_rot, worktree, security, context_lint. Use ko/en message catalog.
  - Files: `src/harness_maker/interview.py`, `tests/unit/test_interview.py`
  - Done when: autoloop_mode test confirms default answer adopted for every dimension. Interactive mode tested with mocked input.
  - Verify: `bash .claude-verify.sh phase_2_interview`
  - Commit: `feat(phase2): implement Interviewer with autoloop + interactive modes`

**Phase 2 Exit Criteria:**
```bash
uv run pytest tests/unit/test_models.py tests/unit/test_profile.py tests/unit/test_interview.py -v \
  && uv run ruff check src/harness_maker/{models,profile,interview}.py \
  && uv run mypy --strict src/harness_maker/{models,profile,interview}.py \
  && uv run python -c "from harness_maker.models import HarnessConfig, Blueprint, ProjectProfile, FileEntry, ConflictItem; from harness_maker.profile import profile; from harness_maker.interview import interview" \
  && bash .claude-verify.sh phase_2_invariants
```

---

### Phase 3: Synthesis Pipeline — Synthesizer + Renderer + Reconciler + Verifier + 4 Fixtures + CLI

**Objective:** End-to-end operation of the `/harness-maker:make` core pipeline. Apply to 4 fixtures and assert expected blueprint match + file count.

**Research targets (autoloop Stage 1 auto-fetch):**
- Jinja2 templating: https://jinja.palletsprojects.com/en/3.1.x/
- (Phase 2 artifacts already available — Pydantic models, profile, interview)

#### Tasks

- **Task 3.1: Synthesizer implementation**
  - Do: `src/harness_maker/synthesize.py` — `synthesize(profile: ProjectProfile, answers: dict) -> Blueprint`. Deterministically map preset+answers to a Blueprint(HarnessConfig + list[FileEntry]). Side preset → 25-30 files, Production → 35-45 files. Exact file list for Side and Production derived from the `templates/` tree in Section 2 of this spec (mapping each `.j2` file to its destination path under the user's `.claude/`).
  - Files: `src/harness_maker/synthesize.py`, `tests/unit/test_synthesize.py`
  - Done when: Side preset blueprint contains 25-30 files, Production 35-45 files, all FileEntry objects have valid template paths
  - Verify: `bash .claude-verify.sh phase_3_synthesize`
  - Commit: `feat(phase3): implement Synthesizer (preset + answers → Blueprint)`

- **Task 3.2: Renderer implementation (with provenance frontmatter, deterministic mode)**
  - Do: `src/harness_maker/render.py` — `render(blueprint: Blueprint, target_dir: Path, *, dry_run: bool = False, freeze_time: datetime | None = None)`. Set up Jinja2 environment (`templates/` as search path). For each FileEntry: (a) render template, (b) attach provenance frontmatter (generated_by, harness_maker_version, generated_at = freeze_time or now(), source_template, content_hash sha256 of body **excluding frontmatter**, provenance="official"), (c) **atomic write** to target_dir (use the `atomic_write` helper from CLAUDE.md — tempfile + os.replace). dry_run=True makes zero disk changes and returns only the change list. **freeze_time argument guarantees test determinism (required for snapshot comparison)**.
  - Files: `src/harness_maker/render.py`, `tests/unit/test_render.py`
  - Done when: rendering a Side blueprint into an empty fixture directory produces 25-30 files all containing frontmatter, content_hash matches actual hash, byte-identical output for the same freeze_time
  - Verify: `bash .claude-verify.sh phase_3_render`
  - Commit: `feat(phase3): implement Renderer with Jinja2 + provenance + deterministic freeze_time`

- **Task 3.3: Reconciler implementation (Brownfield)**
  - Do: `src/harness_maker/reconcile.py` — `reconcile(existing_dir: Path, blueprint: Blueprint) -> list[ConflictItem]`. Index the existing `.claude/`. Compare each new FileEntry against it. Classify conflicts: (a) frontmatter present and hash matches → ours, safe to overwrite (decision=REPLACE automatically), (b) no frontmatter or hash mismatch → user/other source (decision=KEEP by default; auto in autoloop environment), (c) new only → ADD. Backup function — `.claude/.backup-<ISO>/`.
  - Files: `src/harness_maker/reconcile.py`, `tests/unit/test_reconcile.py`
  - Done when: reconcile on a brownfield fixture (seeded existing `.claude/`) correctly classifies N conflicts. Backup directory creation confirmed.
  - Verify: `bash .claude-verify.sh phase_3_reconcile`
  - Commit: `feat(phase3): implement Reconciler with frontmatter-based conflict resolution`

- **Task 3.4: Verifier implementation (smoke)**
  - Do: `src/harness_maker/verify.py` — `verify(target_dir: Path) -> list[str]` (errors). Checks: harness.yaml YAML lint, hooks/hooks.json JSON parse, provenance frontmatter present in all `.md` files, settings.json permissions schema valid.
  - Files: `src/harness_maker/verify.py`, `tests/unit/test_verify.py`
  - Done when: errors == [] for a valid blueprint render result; errors detected on intentional corruption
  - Verify: `bash .claude-verify.sh phase_3_verifier`
  - Commit: `feat(phase3): implement Verifier with yaml/json/frontmatter checks`

- **Task 3.5: 4 Fixtures + Snapshot Test (deterministic)**
  - Do: Create `tests/fixtures/{side-python-cli, side-tauri-app, prod-tauri-app, prod-firmware}/` directories. Seed each fixture with the files required for Profiler to detect the stack (pyproject.toml or package.json, etc.). `tests/snapshot/<fixture>.expected.yaml` — expected Blueprint per fixture (preset, file list + content_hash per file, harness.yaml contents). `tests/unit/test_synthesize_snapshot.py` — 4 fixture profiles → synthesize → render(target=tmp, freeze_time=datetime(2026,1,1,0,0,0,tzinfo=UTC)) → snapshot comparison. **Timestamp fixed via freeze_time → frontmatter content is deterministic → stable snapshots**. Also assert rendered file count (Side: 25-30, Production: 35-45; use per-fixture expected values).
  - Files: `tests/fixtures/*/`, `tests/snapshot/*.expected.yaml`, `tests/unit/test_synthesize_snapshot.py`
  - Done when: all 4 fixtures match snapshot, each fixture file count is within the expected range
  - Verify: `bash .claude-verify.sh phase_3_fixtures`
  - Commit: `test(phase3): add 4 fixtures with deterministic snapshot tests`

- **Task 3.6: CLI integration — `make` command working**
  - Do: Complete the `make` function in `src/harness_maker/cli.py`. Flow: profile → (if autoloop_mode True, use defaults) interview → synthesize → (if existing_dotclaude) reconcile → render → verify. `uv run python -m harness_maker.cli make <fixture-dir> --autoloop` applies successfully to all 4 fixtures.
  - Files: `src/harness_maker/cli.py` (extended)
  - Done when: CLI invocation on all 4 fixtures → `.claude/` created → verify passes + file count within expected range
  - Verify: `bash .claude-verify.sh phase_3_cli_make`
  - Commit: `feat(phase3): wire CLI make command end-to-end`

**Phase 3 Exit Criteria:**
```bash
uv run pytest tests/unit/ -v \
  && uv run ruff check src/ \
  && uv run mypy --strict src/ \
  && for fix in side-python-cli side-tauri-app prod-tauri-app prod-firmware; do
       rm -rf tests/fixtures/$fix/.claude
       uv run python -m harness_maker.cli make tests/fixtures/$fix --autoloop || exit 1
       test -f tests/fixtures/$fix/.claude/harness.yaml || exit 1
       count=$(find tests/fixtures/$fix/.claude -type f | wc -l)
       case "$fix" in
         side-*)  [[ $count -ge 25 && $count -le 32 ]] || { echo "$fix: expected 25-30, got $count"; exit 1; } ;;
         prod-*)  [[ $count -ge 35 && $count -le 47 ]] || { echo "$fix: expected 35-45, got $count"; exit 1; } ;;
       esac
     done \
  && bash .claude-verify.sh phase_3_invariants
```

---

### Phase 4: Monitoring 3 Metrics (Efficiency + Health + Fresh)

**Objective:** Dashboard and telemetry assets rendered into the user harness; all 3 metrics displayed in `/hm:ai-readiness` report. Health 6-dim + Agent quality drill-down calculation working.

**Research targets (autoloop Stage 1 auto-fetch):**
- Claude Code hooks (PostToolUse, format): https://code.claude.com/docs/en/hooks
- Claude Code session data fields available to hook scripts (stdin JSON schema)

#### Tasks

- **Task 3.1: Telemetry hook implementation**
  - Do: `src/harness_maker/telemetry.py` — `python -m harness_maker.telemetry` is invoked as a PostToolUse hook. Reads hook input from stdin, records per-turn metrics to metrics.jsonl (input_tokens, output_tokens, cache_read, cost).
  - Files: `src/harness_maker/telemetry.py`, `tests/unit/test_telemetry.py`
  - Done when: invocation with mock hook input → verified that a line is appended to metrics.jsonl
  - Verify: `bash .claude-verify.sh phase_3_telemetry`
  - Commit: `feat(phase3): implement telemetry collector hook`

- **Task 3.3: Health 6-dim scoring**
  - Do: `src/harness_maker/readiness.py` — `compute_health(project_dir: Path, preset: Preset) -> dict`. Score each of the 6 dimensions 0-100: docs (CLAUDE.md/README/ADR presence + length), tests (test/ directory + coverage grep), CI (.github/workflows present), observability (metrics.jsonl + dashboard present), security (high-severity count in `.claude/observability/security/findings`), governance (Production-only weighted; ADR/CONTRIBUTING present). composite = weighted average + ceremony penalty.
  - Files: `src/harness_maker/readiness.py`, `tests/unit/test_readiness.py`
  - Done when: Health score computed for all 4 fixtures; empty fixture scores low, rich fixture scores high
  - Verify: `bash .claude-verify.sh phase_3_health`
  - Commit: `feat(phase3): implement Health 6-dim composite scoring`

- **Task 3.4: Agent quality drill-down**
  - Do: `src/harness_maker/agent_quality.py` — `score_agent(agent_md: Path) -> dict`. 3-layer evaluation: (a) Static — length, structure, presence of permissions definition, (b) LLM judge — ask Claude to evaluate the agent prompt (quality 0-100, mockable), (c) Monte Carlo — consistency across 10 runs of the same prompt (placeholder for now). Aggregate → Platinum (>=90) / Gold (80-89) / Silver (70-79) / Bronze (<70).
  - Files: `src/harness_maker/agent_quality.py`, `tests/unit/test_agent_quality.py`
  - Done when: grade determination passes with a mock agent `.md`
  - Verify: `bash .claude-verify.sh phase_3_agent_quality`
  - Commit: `feat(phase3): implement Agent quality rubric (Platinum/Gold/Silver/Bronze)`

- **Task 3.5: Dashboard render + monitor command**
  - Do: Write `templates/observability/dashboard.{ko,en}.md.j2` — 3 metrics + Health 6-dim + Agent quality drill-down + Anti-rot pending section. Write `templates/commands/hm/monitor.md.j2` — `/hm:monitor` command: compute metrics via Python then refresh dashboard.
  - Files: `templates/observability/dashboard.{ko,en}.md.j2`, `templates/commands/hm/monitor.md.j2`
  - Done when: make on Side fixture → invoking /hm:monitor updates dashboard.md (using mock metrics)
  - Verify: `bash .claude-verify.sh phase_3_dashboard`
  - Commit: `feat(phase3): add dashboard template + /hm:monitor command`

- **Task 3.5: hooks.json + settings.json templates**
  - Do: `templates/hooks/hooks.json.j2` — PostToolUse telemetry hook. `templates/settings/{Side,Production}.json.j2` — permissions allow list (read-only by default; privilege separation hardened in Phase 8).
  - Files: `templates/hooks/hooks.json.j2`, `templates/settings/{Side,Production}.json.j2`
  - Done when: rendered hooks.json passes jq, settings.json contains permissions
  - Verify: `bash .claude-verify.sh phase_3_hooks_settings`
  - Commit: `feat(phase3): add hooks.json + settings.json templates`

**Phase 3 Exit Criteria:**
```bash
uv run pytest tests/unit/ -v \
  && uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop \
  && jq . tests/fixtures/side-python-cli/.claude/hooks/hooks.json > /dev/null \
  && test -f tests/fixtures/side-python-cli/.claude/observability/dashboard.md
```

---

### Phase 5: Anti-rot Pipeline (4-source crawl + adaptive threshold + manual confirm)

**Objective:** `/hm:refresh` command rendered into the user harness, runs automatically weekly + on manual invocation. 4-source crawl → adaptive filter → propose UI. **Always requires manual confirm.**

**Research targets (autoloop Stage 1 auto-fetch):**
- arxiv API spec: https://info.arxiv.org/help/api/user-manual.html
- GitHub REST API releases endpoint: https://docs.github.com/en/rest/releases/releases
- GitHub API rate limits (unauthenticated 60/h): https://docs.github.com/en/rest/overview/rate-limits-for-the-rest-api
- OSV.dev API: https://google.github.io/osv.dev/api/
- Anthropic news index page (HTML scrape — no RSS): https://www.anthropic.com/news
- Claude Code release notes: https://github.com/anthropics/claude-code/releases
- feedparser library: https://feedparser.readthedocs.io/en/latest/
- httpx async client: https://www.python-httpx.org/

#### Tasks

- **Task 4.1: Crawler — Anthropic blog/changelog (HTML scrape)**
  - Do: `src/harness_maker/crawler/anthropic_blog.py` — `fetch_recent(since: datetime) -> list[CrawlItem]`. **Anthropic has no official RSS.** Fetch `https://www.anthropic.com/news` HTML via httpx, parse article cards with BeautifulSoup4 (add dependency) or regex → CrawlItem(title, url, published, summary). Cache: `~/.cache/harness-maker/anthropic-blog.json` (12h TTL). On failure: graceful skip + warning log.
  - Files: `src/harness_maker/crawler/anthropic_blog.py`, `tests/unit/crawler/test_anthropic_blog.py`, `pyproject.toml` (add beautifulsoup4)
  - Files: `src/harness_maker/crawler/anthropic_blog.py`, `tests/unit/crawler/test_anthropic_blog.py`
  - Done when: invocation with mock RSS feed returns CrawlItem list; cache hit makes no network call
  - Verify: `bash .claude-verify.sh phase_4_anthropic`
  - Commit: `feat(phase4): implement Anthropic blog crawler`

- **Task 4.2: Crawler — GitHub releases**
  - Do: `src/harness_maker/crawler/github_releases.py` — `fetch_releases(repo: str, since: datetime) -> list[CrawlItem]`. Call `api.github.com/repos/{repo}/releases` via httpx (unauthenticated). repos: anthropics/claude-code, obra/superpowers, Yeachan-Heo/oh-my-claudecode, scalarian/oh-my-codex, wshobson/agents, davila7/claude-code-templates, coleam00/Archon, affaan-m/everything-claude-code, HKUDS/OpenHarness. Cache: `~/.cache/harness-maker/gh-{repo}.json` (24h TTL). Graceful skip on rate limit detection.
  - Files: `src/harness_maker/crawler/github_releases.py`, `tests/unit/crawler/test_github_releases.py`
  - Done when: mock response → CrawlItem list; rate-limit response → empty list + warning log
  - Verify: `bash .claude-verify.sh phase_4_github`
  - Commit: `feat(phase4): implement GitHub releases crawler with caching`

- **Task 4.3: Crawler — arxiv**
  - Do: `src/harness_maker/crawler/arxiv.py` — `fetch_recent(categories: list[str], terms: list[str], since: datetime) -> list[CrawlItem]`. Call arxiv API (export.arxiv.org/api/query). categories: cs.SE, cs.CL, cs.CR. terms: ["coding agent", "prompt engineering", "agent harness", "agent eval", "prompt injection"]. Cache: `~/.cache/harness-maker/arxiv.json` (7d TTL).
  - Files: `src/harness_maker/crawler/arxiv.py`, `tests/unit/crawler/test_arxiv.py`
  - Done when: mock response → CrawlItem list, cache hit verified
  - Verify: `bash .claude-verify.sh phase_4_arxiv`
  - Commit: `feat(phase4): implement arxiv crawler with category+term filter`

- **Task 4.4: Crawler — OSV.dev**
  - Do: `src/harness_maker/crawler/osv_dev.py` — `query_cve(packages: list[Package]) -> list[Vulnerability]`. OSV.dev API. Parse package-lock.json/Cargo.lock/requirements.txt.
  - Files: `src/harness_maker/crawler/osv_dev.py`, `tests/unit/crawler/test_osv_dev.py`
  - Done when: mock package list → Vulnerability list returned
  - Verify: `bash .claude-verify.sh phase_4_osv`
  - Commit: `feat(phase4): implement OSV.dev CVE query`

- **Task 4.5: Relevance filter (adaptive threshold)**
  - Do: `src/harness_maker/relevance.py` — `score(item: CrawlItem, harness_yaml: dict, history: list) -> float`. LLM call (Claude Code subscription). Input: CrawlItem + harness.yaml summary + past accept/reject history. Output: applicability_score (0-1), risk (low/med/high), proposed_change. threshold = adaptive: start 0.7, if accept rate >80% → -0.05, if reject rate >50% → +0.05. Unit test with mock LLM.
  - Files: `src/harness_maker/relevance.py`, `tests/unit/test_relevance.py`
  - Done when: mock LLM response → score computed and threshold adaptation verified
  - Verify: `bash .claude-verify.sh phase_4_relevance`
  - Commit: `feat(phase4): implement adaptive relevance filter`

- **Task 4.6: research-crawler skill template**
  - Do: `templates/skills/research-crawler/SKILL.md.j2` — skill invoked by the user harness. description: "Crawl 4 sources for harness updates". Body: Python module invocation procedure.
  - Files: `templates/skills/research-crawler/SKILL.md.j2`
  - Done when: rendered SKILL.md contains valid frontmatter + description
  - Verify: `bash .claude-verify.sh phase_4_skill_template`
  - Commit: `feat(phase4): add research-crawler skill template`

- **Task 4.7: relevance-filter skill template**
  - Do: `templates/skills/relevance-filter/SKILL.md.j2`
  - Files: `templates/skills/relevance-filter/SKILL.md.j2`
  - Done when: rendered SKILL.md is valid
  - Verify: `bash .claude-verify.sh phase_4_filter_template`
  - Commit: `feat(phase4): add relevance-filter skill template`

- **Task 4.8: /hm:refresh command template (manual confirm UI)**
  - Do: `templates/commands/hm/refresh.md.j2` — `/hm:refresh` command. Flow: (1) invoke 4 crawlers, (2) relevance filter, (3) items passing threshold → create `.claude/observability/refresh/proposed-<date>.md`, (4) AskUserQuestion for each proposal (accept/reject/defer), (5) on accept → patch the relevant `.claude/` asset + commit. **Absolutely no auto-apply.**
  - Files: `templates/commands/hm/refresh.md.j2`
  - Done when: rendered refresh.md includes manual confirm flow; in autoloop environment, runs only up to propose step (simulates accept)
  - Verify: `bash .claude-verify.sh phase_4_refresh_template`
  - Commit: `feat(phase4): add /hm:refresh command template with manual confirm`

**Phase 4 Exit Criteria:**
```bash
uv run pytest tests/unit/crawler/ tests/unit/test_relevance.py -v \
  && uv run python -c "from harness_maker.crawler import anthropic_blog, github_releases, arxiv, osv_dev; print('all ok')" \
  && for tpl in research-crawler relevance-filter; do
       test -f templates/skills/$tpl/SKILL.md.j2 || exit 1
     done \
  && test -f templates/commands/hm/refresh.md.j2 \
  && grep -q "AskUserQuestion" templates/commands/hm/refresh.md.j2  # confirm manual confirm is present
```

---

### Phase 6: Workflow Engine + Conditional Router + Modular Installer

**Objective:** 7 atomic stages + user-named fused workflows rendered into the user harness. Conditional Router selects reviewers based on the change area. `--add` / `--remove` modular installation working.

**Research targets (autoloop Stage 1 auto-fetch):**
- Claude Code skill spec (SKILL.md frontmatter): https://code.claude.com/docs/en/skills
- Claude Code subagent spec (agent .md frontmatter): https://code.claude.com/docs/en/sub-agents
- Slash command subdirectory namespace (`commands/hm/<name>.md` → `/hm:<name>`): https://code.claude.com/docs/en/plugins-reference

#### Tasks

- **Task 5.1: Atomic stage prompt fragments**
  - Do: Write 7 files `templates/stages/{research,spec,plan,execute,review,wrapup,verify}.md.j2`. Each fragment ~50-150 lines (within Side limits). Instructions for each stage clearly stated. Variables: {{ project_name }}, {{ feature }}, {{ workflow_context }}.
  - Files: `templates/stages/*.md.j2`
  - Done when: all 7 fragments are valid Jinja2, render produces normal output
  - Verify: `bash .claude-verify.sh phase_5_stages`
  - Commit: `feat(phase5): add 7 atomic stage prompt fragments`

- **Task 5.2: Workflow fusion logic**
  - Do: `src/harness_maker/workflow_fuse.py` — `fuse(stages: list[AtomicStage], workflow_name: str) -> str`. Combine atomic stage fragments into a single prompt. Insert a clear separator between each fragment (`## Stage: <name>`). Output is the body of a single `/hm:<workflow>` command `.md` file.
  - Files: `src/harness_maker/workflow_fuse.py`, `tests/unit/test_workflow_fuse.py`
  - Done when: example workflow `dev=[plan,execute,review,wrapup]` fused → output is the 4 fragments combined in order
  - Verify: `bash .claude-verify.sh phase_5_fuse`
  - Commit: `feat(phase5): implement workflow fusion logic`

- **Task 5.3: Atomic + workflow command templates**
  - Do: `templates/commands/hm/atomic_command.md.j2` — Renderer renders each of the 7 atomics to produce `commands/hm/{stage}.md`. `templates/commands/hm/workflow_command.md.j2` — Renderer iterates `harness.yaml.workflows` and generates a fused command for each workflow.
  - Files: `templates/commands/hm/atomic_command.md.j2`, `templates/commands/hm/workflow_command.md.j2`, `src/harness_maker/render.py` extended (add workflow loop)
  - Done when: applying to Side fixture produces all 7 atomic + N workflow commands under `commands/hm/`
  - Verify: `bash .claude-verify.sh phase_5_commands_render`
  - Commit: `feat(phase5): wire atomic + workflow command rendering`

- **Task 5.4: Conditional Router**
  - Do: `src/harness_maker/conditional_router.py` — `route_reviewers(changed_files: list[Path], preset_reviewers: list[str], routing: str) -> list[str]`. When routing="conditional": map changed-file areas (auth/.env → security, perf-critical → performance, ui/.tsx → ux, worker/thread/isr → concurrency). When routing="always-all": return all preset_reviewers.
  - Files: `src/harness_maker/conditional_router.py`, `tests/unit/test_conditional_router.py`
  - Done when: various combinations of changed_files return the expected reviewer set
  - Verify: `bash .claude-verify.sh phase_5_router`
  - Commit: `feat(phase5): implement Conditional Router`

- **Task 5.5: conditional-router skill template + agents**
  - Do: `templates/skills/conditional-router/SKILL.md.j2`. 9 agent templates: `templates/agents/{code,security,performance,ux,concurrency}-reviewer.md.j2`, `consensus-arbiter.md.j2`, `autoloop-coder.md.j2`, `executor.md.j2`. Each agent `.md` has frontmatter (name, description, permissions) — **the exact frontmatter schema for Claude Code SubAgent permissions must be confirmed from the research target URL docs (verify allow/deny field names and structure)**. Privilege separation is a placeholder (hardened in Phase 8). security-auditor added in Phase 7.
  - Files: `templates/skills/conditional-router/SKILL.md.j2`, `templates/agents/*.md.j2` (8 files)
  - Done when: applying Production fixture → `.claude/agents/` contains 8 agents
  - Verify: `bash .claude-verify.sh phase_5_agents`
  - Commit: `feat(phase5): add Conditional Router skill + 8 agent templates`

- **Task 5.6: Modular Installer (--add / --remove)**
  - Do: `src/harness_maker/modular_edit.py` — `add(component: str, target_dir: Path)`, `remove(component: str, target_dir: Path)`. Component format: `reviewer:security`, `hook:pre-push-smoke`, `skill:tdd-conditional`. On add/remove: (a) render the relevant template, (b) sync `.claude/harness.yaml` (e.g., add to reviewers.list), (c) re-run verifier. CLI integration: `cli.py make --add ...`.
  - Files: `src/harness_maker/modular_edit.py`, `tests/unit/test_modular_edit.py`
  - Done when: `make --add reviewer:security` on Side fixture → security-reviewer.md added, harness.yaml updated
  - Verify: `bash .claude-verify.sh phase_5_modular`
  - Commit: `feat(phase5): implement modular --add / --remove installer`

- **Task 5.7: Workflow naming + interview integration**
  - Do: Extend `src/harness_maker/interview.py` — Q-workflows step: present recommended workflow seeds per preset (Side: dev+quick / Production: the above + careful + audit), user confirms/edits/removes/adds names. Validate workflow names (`[a-z][a-z0-9-]*`; reserved words = atomic stage names + "make" are blocked). Determine default_workflow.
  - Files: `src/harness_maker/interview.py` (extended), `tests/unit/test_interview.py` (extended)
  - Done when: in autoloop_mode, recommended seeds adopted as-is; in interactive mode, workflow rename verified with mock input
  - Verify: `bash .claude-verify.sh phase_5_workflow_interview`
  - Commit: `feat(phase5): wire workflow naming into interview`

**Phase 5 Exit Criteria:**
```bash
uv run pytest tests/unit/test_workflow_fuse.py tests/unit/test_conditional_router.py tests/unit/test_modular_edit.py tests/unit/test_interview.py -v \
  && uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop \
  && for stage in research spec plan execute review wrapup verify; do
       test -f tests/fixtures/side-python-cli/.claude/commands/hm/$stage.md || exit 1
     done \
  && test -f tests/fixtures/side-python-cli/.claude/commands/hm/dev.md \
  && uv run python -m harness_maker.cli make tests/fixtures/prod-tauri-app --autoloop --add reviewer:security \
  && test -f tests/fixtures/prod-tauri-app/.claude/agents/security-reviewer.md
```

---

### Phase 7: Autoloop driver + Verify-before-completion gate

**Objective:** The `/hm:loop` command is rendered into the user harness and operates as an autonomous iteration loop. `/hm:verify` acts as a gate skill that is automatically invoked immediately before wrapup.

Note (ADR-108): The drift_monitor fence introduced in 0.7.1 guards the autoloop driver against unbounded token consumption; the `iter % 5` ping and 3-consecutive-failure stop logic below are the primary safety rails, and ADR-108 adds a drift fence that halts the loop if the goal-state delta has not decreased over N iterations.

**Research targets (autoloop Stage 1 auto-fetch):**
- Autoloop pattern reference for this repo (self-contained, no vault dependency): docs/reference/autoloop-pattern.md
- AHE — Agentic Harness Engineering: https://arxiv.org/abs/2604.25850
- Inside the Scaffold (5 loop primitives): https://arxiv.org/abs/2604.03515
- superpowers verify-before-completion pattern: https://github.com/obra/superpowers

#### Tasks

- **Task 6.1: Autoloop driver logic**
  - Do: `src/harness_maker/autoloop_driver.py` — `run(goal: str, args: dict)`. parse_goal → feature_list. while not converged: next_feature → execute workflow (fused command invocation simulation) → state update. safety: ping at iter % 5 == 0, stop on 3 consecutive failures, time/iter cap. No token limit.
  - Files: `src/harness_maker/autoloop_driver.py`, `tests/unit/test_autoloop_driver.py`
  - Done when: convergence simulation via mock workflow execution, zero disk changes in dry-run mode
  - Verify: `bash .claude-verify.sh phase_6_driver`
  - Commit: `feat(phase6): implement autoloop driver`

- **Task 6.2: /hm:loop command template**
  - Do: `templates/commands/hm/loop.md.j2` — invokes autoloop_driver. argparse: `<goal>` (required), `--time 8h`, `--max-iter 30`, `--workflow <name>`, `--convergence "<criterion>"`, `--dry-run`.
  - Files: `templates/commands/hm/loop.md.j2`
  - Done when: rendered loop.md is well-formed, autoloop argument parsing spec is clear
  - Verify: `bash .claude-verify.sh phase_6_loop_template`
  - Commit: `feat(phase6): add /hm:loop command template`

- **Task 6.3: autoloop-coder + autoloop-driver skill templates**
  - Do: `templates/agents/autoloop-coder.md.j2` — main worker agent for autoloop. `templates/skills/autoloop-driver/SKILL.md.j2` — driver invocation guide.
  - Files: `templates/agents/autoloop-coder.md.j2`, `templates/skills/autoloop-driver/SKILL.md.j2`
  - Done when: frontmatter validation passes after render
  - Verify: `bash .claude-verify.sh phase_6_autoloop_assets`
  - Commit: `feat(phase6): add autoloop-coder agent + autoloop-driver skill templates`

- **Task 6.4: Verify-before-completion gate implementation**
  - Do: `templates/skills/verify-before-completion/SKILL.md.j2` — skill automatically invoked immediately before `/hm:wrapup` or autoloop iter completion. Checklist: PLAN/SPEC satisfied / regression gate / Health score within -5 / Anti-rot pending deferred or resolved / zero high security findings / Worktree merge-safe. Each check calls bash or Python. Blocks wrapup on failure.
  - Files: `templates/skills/verify-before-completion/SKILL.md.j2`
  - Done when: SKILL.md specifies all 6 checks, each with a clear verification command
  - Verify: `bash .claude-verify.sh phase_6_verify_gate`
  - Commit: `feat(phase6): add verify-before-completion gate skill`

- **Task 6.5: ai-readiness-rubric + agent-quality-rubric skill templates**
  - Do: `templates/skills/ai-readiness-rubric/SKILL.md.j2` — guide for computing Health 6-dim score (calls readiness.py). `templates/skills/agent-quality-rubric/SKILL.md.j2` — guide for Platinum/Gold/Silver/Bronze evaluation (calls agent_quality.py). Procedure for automatically registering Bronze-grade agents as anti-rot patch candidates is explicitly stated.
  - Files: `templates/skills/ai-readiness-rubric/SKILL.md.j2`, `templates/skills/agent-quality-rubric/SKILL.md.j2`
  - Done when: valid frontmatter + description after render
  - Verify: `bash .claude-verify.sh phase_6_health_skills`
  - Commit: `feat(phase6): add Health + Agent quality rubric skills`

**Phase 6 Exit Criteria:**
```bash
uv run pytest tests/unit/test_autoloop_driver.py -v \
  && uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop \
  && test -f tests/fixtures/side-python-cli/.claude/commands/hm/loop.md \
  && test -f tests/fixtures/side-python-cli/.claude/skills/verify-before-completion/SKILL.md \
  && test -f tests/fixtures/side-python-cli/.claude/skills/ai-readiness-rubric/SKILL.md \
  && test -f tests/fixtures/side-python-cli/.claude/skills/agent-quality-rubric/SKILL.md \
  && test -f tests/fixtures/side-python-cli/.claude/agents/autoloop-coder.md
```

---

### Phase 8: Worktree Isolation + harness.yaml schema extension

**Objective:** `/hm:execute` operates automatically inside a git worktree. `worktree:` and `security:` sections are added to harness.yaml (the actual security gate logic is in Phase 9).

**Research targets (autoloop Stage 1 auto-fetch):**
- git worktree CLI: https://git-scm.com/docs/git-worktree
- Archon worktree pattern reference: https://github.com/coleam00/Archon

#### Tasks

- **Task 8.1: Worktree lifecycle**
  - Do: `src/harness_maker/worktree.py` — `create(workflow: str, base_dir: Path) -> Path` (creates `.worktrees/<workflow>-<ts>/`), `cleanup(wt_path: Path, on_success: bool)`, `merge(wt_path: Path, strategy: str)`, `cleanup_all(force: bool)` (called on autoloop blocker). Invokes git worktree CLI. Validates automatic `.gitignore` addition.
  - Files: `src/harness_maker/worktree.py`, `tests/unit/test_worktree.py`
  - Done when: worktree create/cleanup/merge/cleanup_all confirmed working in a temp git repo
  - Verify: `bash .claude-verify.sh phase_8_worktree`
  - Commit: `feat(phase8): implement git worktree lifecycle`

- **Task 8.2: worktree-isolator skill template**
  - Do: `templates/skills/worktree-isolator/SKILL.md.j2` — automatic worktree creation on `/hm:execute` invocation, change isolation, cleanup procedure on success. References `harness.yaml.worktree` configuration.
  - Files: `templates/skills/worktree-isolator/SKILL.md.j2`
  - Done when: rendered SKILL.md specifies the 4-step flow
  - Verify: `bash .claude-verify.sh phase_8_worktree_skill`
  - Commit: `feat(phase8): add worktree-isolator skill template`

- **Task 8.3: harness.yaml schema extension (worktree + security sections)**
  - Do: Add `worktree:` and `security:` sections to `templates/harness-yaml/{Side,Production}.yaml.j2` (actual security check logic is Phase 9). Side: worktree.scope=[execute], security.on_finding.high=warn. Production: scope=[execute, plan], on_finding.high=block. Extend Pydantic HarnessConfig model to validate `worktree` and `security` keys.
  - Files: `templates/harness-yaml/{Side,Production}.yaml.j2`, `src/harness_maker/models.py` (extended)
  - Done when: rendered harness.yaml passes Pydantic HarnessConfig validation
  - Verify: `bash .claude-verify.sh phase_8_yaml_schema`
  - Commit: `feat(phase8): extend harness.yaml schema with worktree + security`

**Phase 8 Exit Criteria:**
```bash
uv run pytest tests/unit/test_worktree.py -v \
  && bash .claude-verify.sh phase_8_worktree_skill \
  && bash .claude-verify.sh phase_8_yaml_schema \
  && bash .claude-verify.sh phase_8_invariants
```

---

### Phase 9: 7 Security Gates (secrets · permissions · hook injection · CVE · hallucination · prod-name guard · prompt injection)

**Objective:** All 7 security gates are detectable. The orchestrator calls all 7 gates in aggregate. A security-auditor agent is added.

Two additional gates — hallucination detection and prod-name guard — landed in 0.7.0 and were hardened in 0.7.1: ADR-105 implements a pure-filesystem hallucination check (no external API calls required), and the prod-name guard uses a deque-based sliding window to detect repeated production-name leakage across iterations.

**Research targets (autoloop Stage 1 auto-fetch):**
- gitleaks pattern catalog (regex reference): https://github.com/gitleaks/gitleaks
- OSV.dev API query format: https://google.github.io/osv.dev/api/
- CVE-2025-59536 (skill poisoning): https://arxiv.org/abs/2604.03081
- OWASP LLM prompt injection: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- ECC AgentShield security scaffolding pattern: https://github.com/affaan-m/everything-claude-code

#### Tasks

- **Task 9.1: Security gate — secrets**
  - Do: `src/harness_maker/secscan/secrets.py` — `scan(target_dir: Path) -> list[Finding]`. Regex patterns: AWS_ACCESS_KEY, GitHub PAT, Anthropic API key, .env leakage, generic high-entropy strings. severity: high.
  - Files: `src/harness_maker/secscan/secrets.py`, `tests/unit/test_secrets_scan.py`
  - Done when: seeded fake secrets are detected, empty directory yields 0 findings
  - Verify: `bash .claude-verify.sh phase_9_secrets`
  - Commit: `feat(phase9): implement secrets scanner`

- **Task 9.2: Security gate — permissions**
  - Do: `src/harness_maker/secscan/permissions.py` — `scan(settings_json: Path) -> list[Finding]`. Detects overly broad patterns inside `permissions.allow` in settings.json (`Bash(*)`, `Write(/**)`, etc.). severity: high (catch-all) / medium (broad path).
  - Files: `src/harness_maker/secscan/permissions.py`, `tests/unit/test_permissions_scan.py`
  - Done when: catch-all detected, normal narrow patterns yield 0 findings
  - Verify: `bash .claude-verify.sh phase_9_permissions`
  - Commit: `feat(phase9): implement permissions scanner`

- **Task 9.3: Security gate — hook injection**
  - Do: `src/harness_maker/secscan/hook_injection.py` — `scan(hooks_json: Path) -> list[Finding]`. Dangerous pattern list: `rm -rf`, `curl <url> | sh`, `eval`, `wget ... | bash`. AST or regex.
  - Files: `src/harness_maker/secscan/hook_injection.py`, `tests/unit/test_hook_injection.py`
  - Done when: seeded dangerous hooks detected, normal hooks yield 0 findings
  - Verify: `bash .claude-verify.sh phase_9_hook_injection`
  - Commit: `feat(phase9): implement hook injection scanner`

- **Task 9.4: Security gate — dependency CVEs**
  - Do: `src/harness_maker/secscan/dependency_cves.py` — `scan(target_dir: Path) -> list[Finding]`. Parses package-lock.json/Cargo.lock/requirements.txt/uv.lock → package list → osv_dev.query_cve(). severity: high (CVSS >= 7) / medium (4-6.9) / low (<4).
  - Files: `src/harness_maker/secscan/dependency_cves.py`, `tests/unit/test_cve_scan.py`
  - Done when: Vulnerability list from mock OSV response, severity classification accurate
  - Verify: `bash .claude-verify.sh phase_9_cve`
  - Commit: `feat(phase9): implement dependency CVE scanner`

- **Task 9.5: Security gate — prompt injection**
  - Do: `src/harness_maker/secscan/prompt_injection.py` — `scan(text: str) -> list[Finding]`. Hidden instruction patterns (zero-width chars, base64 instructions, "ignore previous", "system:" injection). severity: high.
  - Files: `src/harness_maker/secscan/prompt_injection.py`, `tests/unit/test_prompt_injection.py`
  - Done when: seeded fake injections detected, normal text yields 0 findings
  - Verify: `bash .claude-verify.sh phase_9_prompt_injection`
  - Commit: `feat(phase9): implement prompt injection scanner`

- **Task 9.6: Security scanner orchestrator + skill + agent**
  - Do: `src/harness_maker/security_scanner.py` — `scan_all(target_dir: Path, harness_config: dict) -> list[Finding]`. Calls all 7 gates → findings → saves to `.claude/observability/security/findings-<date>.jsonl`. Applies on_finding policy (high=block/warn/allow). `templates/skills/security-scanner/SKILL.md.j2`, `templates/agents/security-auditor.md.j2`.
  - Files: `src/harness_maker/security_scanner.py`, `templates/skills/security-scanner/SKILL.md.j2`, `templates/agents/security-auditor.md.j2`, `tests/unit/test_security_scanner.py`
  - Done when: all 7 seeded vulnerabilities detected, findings.jsonl generated, security-auditor agent renders correctly
  - Verify: `bash .claude-verify.sh phase_9_orchestrator`
  - Commit: `feat(phase9): wire security scanner orchestrator + skill + auditor agent`

**Phase 9 Exit Criteria:**
```bash
uv run pytest tests/unit/test_secrets_scan.py tests/unit/test_permissions_scan.py tests/unit/test_hook_injection.py tests/unit/test_cve_scan.py tests/unit/test_prompt_injection.py tests/unit/test_security_scanner.py -v \
  && bash .claude-verify.sh phase_9_seeded_vulns \
  && bash .claude-verify.sh phase_9_invariants
```

---

### Phase 10: Context Lint + Privilege Separation + Provenance Frontmatter

**Objective:** Integrate context lint into the renderer (blocks verbose output). Separate permissions for reviewer agent settings.json. Validate provenance frontmatter on all generated files (partially implemented in Phase 2 — full verification and hash comparison here).

Note (ADR-107): The 0.7.1 tool_input whitelist and secret redaction in the telemetry hook are directly relevant to privilege separation; generated executor/reviewer agent frontmatter must reflect the updated allow/deny lists from ADR-107.

**Research targets (autoloop Stage 1 auto-fetch):**
- Claude Code settings.json permissions schema (allow/deny format): https://code.claude.com/docs/en/settings
- Evaluating AGENTS.md (verbose context empirical study): https://arxiv.org/abs/2602.11988
- OpenClaw — Privilege Separation (privilege separation ASR 0.31% vs 14%): https://arxiv.org/abs/2603.13424
- Supply-Chain Poisoning (rationale for provenance): https://arxiv.org/abs/2604.03081
- AgentBound capability framework: https://arxiv.org/abs/2510.21236

#### Tasks

- **Task 8.1: Context Lint implementation**
  - Do: `src/harness_maker/context_lint.py` — `lint(file_path: Path, asset_type: str, preset: Preset) -> list[str]` (warnings). Thresholds: CLAUDE.md (Side 200 / Prod 500), agent (100 / 200), skill SKILL.md (50 / 150), workflow command (300 / 600). Suggests automatic summarization on threshold exceeded.
  - Files: `src/harness_maker/context_lint.py`, `tests/unit/test_context_lint.py`
  - Done when: warning emitted for over-threshold files, 0 warnings for normal files
  - Verify: `bash .claude-verify.sh phase_8_context_lint`
  - Commit: `feat(phase8): implement context lint with length thresholds`

- **Task 8.2: Integrate context lint into renderer**
  - Do: Extend `src/harness_maker/render.py` — call context_lint on every rendered file immediately before Apply. Output warnings. When `harness.yaml.context_lint.strict: true`, exceeding threshold is an error (blocks Apply). default false.
  - Files: `src/harness_maker/render.py` (extended), `tests/unit/test_render.py` (extended)
  - Done when: warning emitted with intentionally verbose template, blocked when strict=true
  - Verify: `bash .claude-verify.sh phase_8_render_lint`
  - Commit: `feat(phase8): wire context lint into renderer`

- **Task 8.3: context-linter skill template**
  - Do: `templates/skills/context-linter/SKILL.md.j2` — self-lint skill inside the user harness (can be invoked immediately before `/hm:execute` or `/hm:wrapup`).
  - Files: `templates/skills/context-linter/SKILL.md.j2`
  - Done when: passes render
  - Verify: `bash .claude-verify.sh phase_8_lint_skill`
  - Commit: `feat(phase8): add context-linter skill template`

- **Task 8.4: Privilege separation — Reviewer agents permissions**
  - Do: Add read-only permissions to the frontmatter of `templates/agents/{code,security,security-auditor,performance,ux,concurrency}-reviewer.md.j2`. **Must verify the exact schema from the official Claude Code SubAgent spec (https://code.claude.com/docs/en/sub-agents + https://code.claude.com/docs/en/settings) before applying** — if SubAgent frontmatter only supports a `tools: [Read, Grep]` allowlist and does not support a deny list, enforce read-only via allowlist alone (excluding Write/Edit/Bash exec tools entirely). Apply consistently across all 6 reviewers.
  - Files: `templates/agents/{code,security,security-auditor,performance,ux,concurrency}-reviewer.md.j2`
  - Done when: deny list present in rendered agent .md frontmatter
  - Verify: `bash .claude-verify.sh phase_8_reviewer_perms`
  - Commit: `feat(phase8): enforce read-only permissions on all reviewer agents`

- **Task 8.5: Privilege separation — Executor agent**
  - Do: `templates/agents/executor.md.j2` — write-capable but restricted to `.worktrees/**` only. `permissions.allow: [Read(*), Grep(*), Write(.worktrees/**), Edit(.worktrees/**), Bash(npm test:*), Bash(pytest:*), Bash(uv run:*), Bash(cargo test:*)]`, `deny: [Write(/etc/**), Write(~/.ssh/**), Write(~/.aws/**), Bash(curl * | sh), Bash(eval *), Bash(rm -rf /:*)]`. Same policy applies to autoloop-coder.md.j2.
  - Files: `templates/agents/executor.md.j2`, `templates/agents/autoloop-coder.md.j2` (extended)
  - Done when: permission policy verified after render
  - Verify: `bash .claude-verify.sh phase_8_executor_perms`
  - Commit: `feat(phase8): add executor agent with worktree-bounded write permissions`

- **Task 8.6: Provenance verification + refresh hash comparison**
  - Do: `src/harness_maker/provenance.py` — `verify_file(file_path: Path) -> tuple[bool, str]` (hash match result, source_template). `compute_hash(file_path: Path) -> str`. `parse_frontmatter(file_path: Path) -> dict`. On `/hm:refresh`: detect user modifications by comparing each file's frontmatter content_hash against actual hash → mismatch requires user confirm (in autoloop environment, auto-KEEP).
  - Files: `src/harness_maker/provenance.py`, `tests/unit/test_provenance.py`
  - Done when: normal generated file passes verify, intentional modification detected as mismatch
  - Verify: `bash .claude-verify.sh phase_8_provenance_verify`
  - Commit: `feat(phase8): implement provenance hash verification`

- **Task 8.7: Wire provenance into Reconciler + refresh**
  - Do: Extend `src/harness_maker/reconcile.py` — compare existing file frontmatter hash vs new blueprint hash → auto-REPLACE on match, KEEP on mismatch. On `/hm:refresh`: hash-verify all `.claude/` assets → silently block overwrite of user-modified files.
  - Files: `src/harness_maker/reconcile.py` (extended), `templates/commands/hm/refresh.md.j2` (extended)
  - Done when: hash-based auto-classification verified in brownfield fixture
  - Verify: `bash .claude-verify.sh phase_8_reconcile_provenance`
  - Commit: `feat(phase8): wire provenance into Reconciler + /hm:refresh`

**Phase 8 Exit Criteria:**
```bash
uv run pytest tests/unit/test_context_lint.py tests/unit/test_provenance.py tests/unit/test_reconcile.py -v \
  && uv run python -m harness_maker.cli make tests/fixtures/prod-tauri-app --autoloop \
  && python -c "
import json, yaml
from pathlib import Path
for agent in ['code-reviewer','security-reviewer','security-auditor','performance-reviewer','ux-reviewer','concurrency-reviewer']:
    md = Path('tests/fixtures/prod-tauri-app/.claude/agents/' + agent + '.md').read_text()
    fm = yaml.safe_load(md.split('---')[1])
    assert 'Write(*)' in fm['permissions']['deny'], agent + ' missing Write deny'
    assert 'Edit(*)' in fm['permissions']['deny'], agent + ' missing Edit deny'
print('reviewer permission separation OK')
"
```

---

### Phase 11: Dogfood — apply to sandbox

**Objective:** Apply harness-maker itself to one sandbox project and verify that all R1-R6 requirements and all mechanisms work correctly. Validate both the Python CLI entry and the Claude Code plugin entry.

**Research targets:** None — Phase 9 is integration test only. No external doc fetch required.

#### Tasks

- **Task 9.1: Create sandbox project**
  - Do: `tests/e2e/sandbox/` — empty Python project directory. pyproject.toml + 1 hello_world.py. git init.
  - Files: `tests/e2e/sandbox/`, `tests/e2e/sandbox/pyproject.toml`, `tests/e2e/sandbox/hello_world.py`
  - Done when: directory + seed files exist, git init complete
  - Verify: `bash .claude-verify.sh phase_9_sandbox_init`
  - Commit: `test(phase9): create sandbox project for dogfood`

- **Task 9.2: Apply /harness-maker:make**
  - Do: Run `uv run python -m harness_maker.cli make tests/e2e/sandbox --autoloop` in sandbox. Apply Side preset. Confirm all assets generated (harness.yaml, commands/hm/*, skills/, agents/, hooks/, observability/dashboard.md).
  - Files: `tests/e2e/sandbox/.claude/` (generated)
  - Done when: .claude/ directory contains 25-30 files, all with provenance frontmatter
  - Verify: `bash .claude-verify.sh phase_9_apply`
  - Commit: `test(phase9): apply harness-maker to sandbox`

- **Task 9.3: Verify generated command execution**
  - Do: e2e test — confirm each of `/hm:quick`, `/hm:dev`, `/hm:loop`, `/hm:monitor`, `/hm:refresh` in the user harness is callable (no actual LLM calls — command file exists + valid frontmatter + parseable). `/hm:execute` demonstrates worktree isolation (mock).
  - Files: `tests/e2e/test_dogfood_sandbox.py`
  - Done when: all 5+ commands valid + parseable + `.worktrees/` created on worktree skill invocation
  - Verify: `bash .claude-verify.sh phase_9_commands`
  - Commit: `test(phase9): verify all generated commands callable`

- **Task 9.4: Verify security gate behavior**
  - Do: Intentionally seed the sandbox: fake .env (AWS_ACCESS_KEY=AKIA...), `Bash(*)` overly broad in settings.json, `curl url | sh` in hooks.json, known vulnerable package in requirements.txt, hidden instruction in code. Invoke `/hm:verify` or call security_scanner.scan_all directly → all 7 findings detected.
  - Files: `tests/e2e/sandbox/.env.seeded`, etc. + `tests/e2e/test_dogfood_sandbox.py` (extended)
  - Done when: all 7 findings correctly classified
  - Verify: `bash .claude-verify.sh phase_9_security`
  - Commit: `test(phase9): verify all 5 security gates detect seeded vulns`

- **Task 9.5: Verify 3 metrics output**
  - Do: Seed mock metrics.jsonl in sandbox, invoke `/hm:monitor` → dashboard.md updated, all 3 metrics displayed.
  - Files: `tests/e2e/test_dogfood_sandbox.py` (extended)
  - Done when: dashboard.md contains Health 6-dim + Agent quality sections, all of token, goal, and iteration indicators present
  - Verify: `bash .claude-verify.sh phase_9_metrics`
  - Commit: `test(phase9): verify 3 metrics displayed correctly`

- **Task 9.6: Verify Reconcile (Brownfield)**
  - Do: Intentionally create one user-modified file in sandbox `.claude/` (break the hash). Re-run `make` → reconcile decides KEEP (automatic in autoloop). Confirm user-modified file is preserved.
  - Files: `tests/e2e/test_dogfood_sandbox.py` (extended)
  - Done when: user-modified file unchanged, other files updated
  - Verify: `bash .claude-verify.sh phase_9_reconcile`
  - Commit: `test(phase9): verify Brownfield reconcile preserves user edits`

- **Task 9.7: Verify plugin entry (Claude Code invocation)**
  - Do: Run via subprocess: `claude --plugin-dir /home/noel/harness-maker -p "/harness-maker:make tests/e2e/sandbox-plugin-test --autoloop"` (add `--dangerously-skip-permissions` if required). Claude Code loads this plugin → routes /harness-maker:make command → calls `python -m harness_maker.cli make` → verify `sandbox-plugin-test/.claude/` is generated. **Both the Python CLI entry and the plugin entry must produce identical results.**
  - Files: `tests/e2e/test_plugin_entry.py`, `tests/e2e/sandbox-plugin-test/`
  - Done when: subprocess exit 0, sandbox-plugin-test/.claude/harness.yaml exists, file count and content match Python CLI result (ignoring timestamps)
  - Verify: `bash .claude-verify.sh phase_9_plugin_entry`
  - Commit: `test(phase9): verify Claude Code plugin entry matches CLI entry`

**Phase 9 Exit Criteria:**
```bash
uv run pytest tests/e2e/ -v \
  && test -f tests/e2e/sandbox/.claude/harness.yaml \
  && test -f tests/e2e/sandbox/.claude/commands/hm/loop.md \
  && test -f tests/e2e/sandbox/.claude/commands/hm/monitor.md \
  && test -f tests/e2e/sandbox/.claude/commands/hm/refresh.md \
  && test -f tests/e2e/sandbox/.claude/observability/dashboard.md \
  && test -f tests/e2e/sandbox-plugin-test/.claude/harness.yaml  # plugin entry path
```

---

### Phase 12: Polish (README + Docs + Final Cleanup)

**Objective:** Reach a state suitable for public release. Complete README, CONTRIBUTING, final lint/type/test with 0 errors.

**Research targets (autoloop Stage 1 auto-fetch):**
- Claude Code marketplace registration: https://code.claude.com/docs/en/plugin-marketplaces
- README best practices: https://www.makeareadme.com/

#### Tasks

- **Task 10.1: Complete README.md**
  - Do: 1-page README — project introduction (1 paragraph), Quick Start (`uv sync && claude --plugin-dir . && /harness-maker:make`), feature summary (single command, 2 presets, 3 metrics, anti-rot, worktree, security), comparison table (vs ohmyclaudecode/superpowers/Archon — brief differentiators), License.
  - Files: `README.md` (extended)
  - Done when: README includes Quick Start + feature summary + comparison + License
  - Verify: `bash .claude-verify.sh phase_10_readme`
  - Commit: `docs(phase10): write comprehensive README`

- **Task 10.2: CONTRIBUTING.md**
  - Do: `docs/CONTRIBUTING.md` — contribution guide. How to add new skill/agent templates, how to add a new preset (yaml schema extension), test writing patterns, PR checklist.
  - Files: `docs/CONTRIBUTING.md`
  - Done when: guide is complete enough for an external contributor to follow
  - Verify: `bash .claude-verify.sh phase_10_contributing`
  - Commit: `docs(phase10): write contributing guide`

- **Task 10.3: ARCHITECTURE.md (domain knowledge extraction)**
  - Do: `docs/ARCHITECTURE.md` — explanation of the 13 mechanisms from TECH_SPEC Section 3 written for an external reader. System diagram, data flow, intent of each mechanism.
  - Files: `docs/ARCHITECTURE.md`
  - Done when: an external reader can understand the system without reading the code
  - Verify: `bash .claude-verify.sh phase_10_architecture`
  - Commit: `docs(phase10): write ARCHITECTURE.md`

- **Task 10.4: Final lint + type + test**
  - Do: Apply ruff format across the entire codebase, ruff check 0 errors, mypy --strict 0 errors, all pytest tests pass. pyproject.toml version bump? (hold at 0.1.0).
  - Files: entire codebase
  - Done when: lint 0, type 0, pytest 0 failures
  - Verify: `bash .claude-verify.sh phase_10_final_quality`
  - Commit: `chore(phase10): final cleanup — lint, type, test all green`

- **Task 10.5: Marketplace prep (optional)**
  - Do: Add `homepage`, `repository` (placeholder), and `keywords` to `.claude-plugin/plugin.json`. Add marketplace registration procedure placeholder to README.
  - Files: `.claude-plugin/plugin.json`, `README.md` (extended)
  - Done when: plugin.json is compatible with marketplace schema (per Claude Code official spec)
  - Verify: `bash .claude-verify.sh phase_10_marketplace`
  - Commit: `feat(phase10): prepare plugin.json for marketplace submission`

**Phase 10 Exit Criteria:**
```bash
uv run ruff check src/ tests/ \
  && uv run ruff format --check src/ tests/ \
  && uv run mypy --strict src/ \
  && uv run pytest tests/ -v --tb=short \
  && test -f README.md && test -f docs/CONTRIBUTING.md && test -f docs/ARCHITECTURE.md \
  && grep -q "Quick Start" README.md \
  && grep -q "license" .claude-plugin/plugin.json
```

---

## 5. Final Acceptance Criteria

### R1-R6 Verification (All Core Requirements)

- [ ] **R1 Locale-first**: Invoking `cli make --interactive` in an empty sandbox, Q1 (Korean/English) must be the first question. The `locale` key is saved to `.claude/harness.yaml`.
- [ ] **R2 Anti-rot**: All 4 source crawlers are callable. The relevance filter adaptive threshold operates correctly. `/hm:refresh` proceeds through the propose step and then waits for manual confirm (auto-apply absolutely prohibited).
- [ ] **R3 Monitoring**: `/hm:ai-readiness` report shows all three metrics: efficiency%, Health, and fresh (days since refresh). `dashboard.md` includes a Health 6-dim section and an Agent quality drill-down (Platinum/Gold/Silver/Bronze) section. Zero external transmission of `metrics.jsonl`.
- [ ] **R4 Workflow**: 7 atomic stages (`/hm:research` ... `/hm:verify`) auto-exposed. N user-named fused workflows (`/hm:dev`, `/hm:careful`) callable as a single command. Both atomic and fused workflows operate correctly.
- [ ] **R5 Autoloop**: Invoking `/hm:loop "<goal>"` causes the driver to iterate autonomously with unlimited tokens, defaulting to 8h/30 iterations. Dry-run mode works. Iter-5 ping and 3-fail stop operate correctly.
- [ ] **R6 Per-project preset**: 2 presets (Side/Production) interview flow → 10+ dimension overrides → saved to `harness.yaml`. All 4 fixtures match expected blueprints.

### Mechanism Verification

- [ ] (M1) Profiler → Interviewer → Synthesizer → Renderer pipeline passes 4 fixtures
- [ ] (M2) Reconciler performs hash-based automatic classification and creates a backup directory
- [ ] (M3) Workflow Engine renders both atomic and fused workflows
- [ ] (M4) Anti-rot 4 sources callable + adaptive threshold adapts
- [ ] (M5) 3 real-time metrics + Health 6-dim + Agent quality drill-down
- [ ] (M6) Conditional Router auto-selects reviewer based on `changed_files`
- [ ] (M7) Autoloop driver state machine operates correctly
- [ ] (M8) Verify-before-completion executes all 6 checks immediately before wrapup
- [ ] (M9) Worktree isolation — `.worktrees/<workflow>-<ts>/` is created and cleaned up
- [ ] (M10) All 7 Security Gates detect seeded vulnerabilities
- [ ] (M11) Context Lint blocks verbose output
- [ ] (M12) Privilege Separation — reviewer `settings.json` has `Write` denied, executor has `Write(.worktrees/**)` allowed
- [ ] (M13) Provenance Frontmatter — all generated files have hash + version; user modifications detected on refresh
- [ ] (M14) Multi-target Rendering — Cursor target renders `.cursor/rules/harness.mdc` + `.cursor/mcp.json`; Codex target renders `AGENTS.md`, `.codex/`, and `.agents/skills/`; plugin manifests stay synchronized

### Asset Existence Verification

- [ ] Skills (11): verify-before-completion, conditional-router, ai-readiness-rubric, agent-quality-rubric, research-crawler, relevance-filter, autoloop-driver, worktree-isolator, security-scanner, context-linter, refdocs-search
- [ ] Agents (9): code-reviewer, security-reviewer, security-auditor, performance-reviewer, ux-reviewer, concurrency-reviewer, consensus-arbiter, autoloop-coder, executor
- [ ] Commands (10+): /hm:research, spec, plan, execute, review, wrapup, verify (7 atomic) + /hm:loop, /hm:monitor, /hm:refresh (3 meta) + N user workflows
- [ ] Hooks: `hooks.json` contains telemetry-collector
- [ ] Templates: harness-yaml/{Side,Production} + claude-md × {ko,en} × 2 presets + memory × {failures,wiki} × {ko,en} + settings × 2 presets + dashboard × {ko,en}

### Verification Script (`.claude-verify.sh`)

See `.claude-verify.sh all` for details. All checks support both per-phase and final `all` modes.

```bash
bash .claude-verify.sh all
# Checks all items above → exit 0 = all passed / non-zero = prints failed items
```

---

## 6. Risks & Decisions

### Architecture Decision Records

- **ADR-1: Python only (no Bash)**
  - Context: Initial spec mixed Bash and Python.
  - Decision: Python exclusively — Bash removed.
  - Rationale: Consistency, type checking, test framework integration, and WSL2 environment stability.

- **ADR-2: Single meta-tool command**
  - Context: Initial spec had 6 commands: /harness-maker:make + refresh + audit + monitor + loop + add.
  - Decision: `/harness-maker:make` only. `audit/add/remove/promote` are flags.
  - Rationale: "Meta-tool is a generator" principle. Day-to-day commands like /loop /monitor /refresh are rendered into the user harness (`/hm:` prefix).

- **ADR-3: /hm: prefix (subdirectory namespace)**
  - Context: Need to distinguish ownership between user-authored commands and harness-generated commands.
  - Decision: `.claude/commands/hm/<name>.md` → `/hm:<name>`. User commands have no prefix: `.claude/commands/<name>.md` → `/<name>`.
  - Rationale: No manifest tracking needed. Natural ownership separation.

- **ADR-4: Workflow = Prompt Fusion (user-named)**
  - Context: Started as a spec/task methodology 2x2 matrix.
  - Decision: Generalized — 7 atomic stages + N user-named fused workflows. Renderer synthesizes stage prompt fragments into a single command file.
  - Rationale: Minimizes human-in-the-loop (1 input → 1 turn). Users name domain-specific workflows.

- **ADR-5: 100% local telemetry**
  - Context: External observability was possible.
  - Decision: `metrics.jsonl` stored only in `.claude/observability/`; zero external transmission.
  - Rationale: Privacy and trust. Anti-rot service calls are user-initiated only.

- **ADR-6: Anti-rot always requires manual confirm**
  - Context: Low-risk auto-apply option was considered.
  - Decision: User confirm enforced at all risk levels. `auto_apply=false` fixed.
  - Rationale: Prevents silent changes. Mitigates K1 (bad patch) risk.

- **ADR-7: Worktree per execute (Archon/superpowers/OMX standard)**
  - Context: Method for change isolation.
  - Decision: `/hm:execute` automatically creates a git worktree; cleans up on success.
  - Rationale: Prevents main branch contamination. Isolates each autoloop iteration. Industry standard.

- **ADR-8: Privilege separation architecture (OpenClaw)**
  - Context: Defense against prompt injection.
  - Decision: reviewer = Read+Grep only / executor = Write(.worktrees/**) only. Explicit deny list in `settings.json`.
  - Rationale: arxiv 2603.13424 — filter alone: 14% ASR vs privilege separation: 0.31% (323x reduction).

- **ADR-9: Provenance Frontmatter (Supply-Chain Poisoning defense)**
  - Context: Skill default-trust risk (CVE-2025-59536).
  - Decision: All generated assets have frontmatter (`generated_by` + `content_hash` + `source_template` + `version`).
  - Rationale: arxiv 2604.03081. Blocks silent overwrite. Strengthens ours/theirs determination in brownfield reconcile.

- **ADR-10: Context Lint (block verbose)**
  - Context: Verbose AGENTS.md decreases success rate.
  - Decision: Apply length limits in Renderer (CLAUDE.md Side 200/Prod 500, etc.).
  - Rationale: arxiv 2602.11988 — verbose context = lower success rate, +20% cost.

- **ADR-11: Targets axis — Cursor as native consumer of `.claude/` (0.5.0)**
  - Context: Confirmed that Cursor IDE 2.4+ natively reads `.claude/agents/`, `.claude/skills/`.
  - Decision: Both IDEs share a single-source `.claude/`. Only Cursor-only assets (rules, mcp.json) are rendered separately. Auto-detect prohibited — user must explicitly select.
  - Rationale: Dual IDE support without duplication. User intent confirmation required (inferring from `.cursor/` directory presence causes false positives).

- **ADR-12: recommended_model + no model-agnostic rewrite (0.5.0)**
  - Context: Cursor users can freely choose their model. Harness prompts contain Claude-specific expressions like `<thinking>` blocks.
  - Decision: `harness.yaml.recommended_model: claude-opus-4-7` as default, propagated to agent frontmatter. Prompts themselves are not rewritten.
  - Rationale: Rewriting prompts risks quality degradation. Users choosing a different model do so at their own discretion and accept the consequences.

- **ADR-13: Manifest version synchronization invariant (0.4.9, extended for Cursor and Codex targets)**
  - Context: In 0.4.9 release, only `pyproject.toml` was bumped while `plugin.json` was neglected → marketplace falsely reported "already at latest".
  - Decision: Version changes must simultaneously modify all runtime manifests plus package metadata: `.claude-plugin/plugin.json` + `.cursor-plugin/plugin.json` + `.codex-plugin/plugin.json` + `pyproject.toml` + `src/harness_maker/__init__.py`. Required as a PR checklist item and CI gate.
  - Rationale: Guarantees runtime and marketplace synchronization. Without it, users mistake a stale plugin for the latest version.

### Risks (K1-K17)

| ID | Risk | Impact | Mitigation |
|---|---|---|---|
| K1 | arxiv crawl noise → bad patch | high | adaptive threshold + always manual confirm |
| K2 | autoloop runaway | high | iter cap + time cap + 3-fail stop + iter-5 ping |
| K3 | Template itself goes stale → self-referential cycle | med | include self-template in refresh targets |
| K4 | Monitoring becomes overwhelming | med | ai-readiness fixed at 3 metrics, dashboard on-demand |
| K5 | i18n asymmetry | med | build fails on template diff asymmetry (CI gate) |
| K6 | hiloop skill name collision | low | explicit `harness-maker:` namespace |
| K7 | Applying to 22 projects at once → regression explosion | high | dry-run forced on first run / per-project apply / backup preserved |
| K8 | WSL2 NTFS Edit hazard | med | renderer automatically enforces Write tool |
| K9 | autoloop external service call cost | med | dry-run default, confirm before external API calls |
| K10 | User voice leak | low | voice guide awareness in prefs (memory) |
| K11 | Rich brownfield `.claude/` → complex reconcile | high | backup + ADD-only + per-item reconcile UI + provenance hash |
| K12 | Worktree remnants accumulate on disk | med | auto `.gitignore` + `cleanup=on_success` default + weekly cleanup hook |
| K13 | Security scan false positive explosion | med | `on_finding.high=warn` (Side default) + allowlist file + per-finding silence |
| K14 | Security scan results leak | low | findings `.gitignore` + 100% local policy |
| K15 | Context verbose → lower success rate, +20% cost | high | context-linter Side 200 / Prod 500 limits |
| K16 | Reviewer agent prompt injection to gain Write permission | high | `settings.json` privilege separation — reviewer Write/Edit denied (closed in 0.7.1, ADR-108) |
| K17 | Silent overwrite of user-modified files | med | provenance hash comparison → confirm required on mismatch |

---

## 7. Personalization Architecture (0.12.0)

> Added in 0.12.0 — PLAN-personalization-depth-2026-05. Tracks A (Detection Depth) + D (Foreign AI Config Migration) + B-start (Adaptive Self-Tuning) landed as 11 active features (Phase 7 merged into Phase 6 per validator W5). 11 ADRs locked in `work-docs/PLAN-personalization-depth-2026-05.md`. README mirrors this section at a higher level.

### 7.1 Three Tracks

**Track A — Detection Depth.** `harness_maker.profile.profile()` detects 12+ language stacks (java/kotlin/swift/dart/ruby/php/csharp/elixir/scala/c-cpp/zig/haskell on top of python/node/rust/cmake/go), parses framework deps (fastapi/django/flask/streamlit/jupyter/react/vue/next/express/nestjs/remix/astro/tauri/axum/tokio/bevy/etc), and surfaces `package_manager` (uv/poetry/pip/pipenv/npm/pnpm/yarn/bun/cargo) + `ci_provider` (github-actions/gitlab-ci/circleci/jenkins/travis). Results flow through `Recommendation` (ADR-001/002).

**Track D — Foreign AI Config Migration.** Detects 6 known foreign configs: `.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`, `.github/copilot-instructions.md`. With user confirmation, `foreign_config.llm_map()` (single Anthropic call, sha256+24h cached) extracts axis mappings into `harness.yaml`, then `foreign_config.apply()` re-renders the foreign file with `@hm:harness:*` inverted markers preserving user content outside marked regions (ADR-003 + ADR-009).

**Track B-start — Adaptive Self-Tuning.** `harness_yaml_override` telemetry event (schema_version=1) captures axis edits at two sites (`/hm:configure`-exit primary + SessionStart secondary, dedup-keyed). `/hm:personalization-audit` consumes telemetry + `harness.yaml` + `ProjectProfile` cache and emits a composite-score `ImprovementPlan` with evidence-bearing `ActionItem` list. SessionStart drift surface fires after 30 overrides or 14 days without audit (ADR-005, ADR-006).

### 7.2 Confidence-Bucketed Recommendation UI (ADR-004, ADR-007)

Every `recommend_<axis>(profile, project_dir) -> Recommendation | None` declares its own `Confidence`:
- **HIGH** — explicit manifest match (e.g., pyproject lists `fastapi` as dep). Silent default + `# detected: <axis>=<value> (high) — <signal>` yaml comment in `harness.yaml`. User can audit but isn't prompted.
- **MEDIUM** — inferred / opinion mapping (e.g., framework→MCP server suggestion). Explicit `AskUserQuestion` during `/hm:configure`.
- **LOW** — pure heuristic guess. No recommendation surfaced; stock default used.

Backward-compat for 0.11.x users (Validator W3): the four pre-existing transitive recommends (`preset`, `dev_mode`, `mechanical_checks`, `vault_member`) were assigned MEDIUM/MEDIUM/HIGH/HIGH respectively to preserve 0.11.x UX. Regression test `test_load_0_11_x_harness_yaml_zero_diff_on_legacy_axes` enforces zero diff.

### 7.3 Foreign Config Marker Family — `@hm:harness:*` inverted (ADR-009, ADR-009 amendment)

`block_merge.py` now dispatches on `MarkerStyle`:
- `HTML_COMMENT` (default, `.md` / `.mdc`): `<!-- @hm:harness:<id> -->` ... `<!-- @hm:/harness:<id> -->`
- `HASH_COMMENT` (`.yml` / `.yaml`): `# @hm:harness:<id>` ... `# @hm:/harness:<id>`
- `JSON_KEY` (`.json`): top-level `_hm_harness` key holds harness-managed content; merge preserves all other user keys

Semantics are **inverted** vs the existing `@hm:user:*` family: with `@hm:harness:*`, content INSIDE the markers is harness-owned (replaced on every render); content OUTSIDE is user-owned (byte-for-byte preserved). The two marker families coexist orthogonally in the same file — neither affects the other.

Typed errors `MarkerMismatchError` + `MarkerNestedError` raised on malformed inputs. Literal `@hm:` strings inside fenced code blocks are correctly skipped by the parser.

**0.11.x migration (ADR-009 amendment):** files with `generated_by: harness-maker` frontmatter AND zero `@hm:harness:*` markers are treated as wholly harness-owned on first encounter post-upgrade; re-rendered into the new marker family. Second render is no-op (idempotent).

### 7.4 Personalization Rubric — `/hm:personalization-audit` (ADR-011)

`rubrics/personalization.yaml` v0 (locked formulas, calibration deferred to follow-up PLAN after 30+ projects):

**Composite score** = `L1×0.4 + L2×0.3 + L3×0.3`, range [0, 100].

| Layer | Formula |
|-------|---------|
| L1 conversion | `(medium_accepted + high_silent) / max(total_recommendations, 1) × 100` |
| L2 stability  | `100 - min(100, override_events_last_30d × 5)` |
| L3 cadence    | `100` if audit within 14d AND `disable_telemetry==False`; `50` if one met; `0` otherwise |

| Tier | Composite range |
|------|-----------------|
| Bronze | 0–39 |
| Silver | 40–64 |
| Gold | 65–84 |
| Platinum | 85–100 |

Every emitted `ActionItem` carries `evidence: {n_observations: int, top_3_signals: list[str], confidence: Confidence}`. Items with `n_observations == 0` OR empty `top_3_signals` are dropped (ADR-010 mode C noise mitigation).

### 7.5 Telemetry — Local-Only, Opt-Out (ADR-005)

`harness.yaml.adaptive.disable_telemetry: false` by default (opt-out). All telemetry (`harness_yaml_override` events + audit reads) is read-only suggestion-only — **never auto-applies**. Stored as JSONL at `.claude/observability/adaptive/overrides.jsonl` with `schema_version: 1` mandatory on every record (Validator C3).

**ADR-005 positive obligation enforced by `tests/unit/test_no_network.py`:** monkeypatches `socket.socket` to raise on any outbound connection, then invokes `emit_override`, `load_overrides`, `compute_yaml_diff`, and the SessionStart hook's `run()` — all 4 paths must complete without triggering the patched socket. Any future regression that adds an HTTP call to telemetry/audit/hook fails CI.

Dual capture (Validator W8): primary site is `/hm:configure` exit pre/post yaml diff (no git dependency, catches uncommitted edits); secondary is SessionStart hook reading `git diff` since last recorded override `ts` (no fixed HEAD~N window). Both share a dedup key `(ts, axis_path, after)` so the same event never records twice.

### 7.6 Cursor Power-User Constraint (ADR-003)

Single-source means harness-maker re-generates `.cursor/rules/` on every render (with `@hm:harness:*` markers preserving user customizations inside `.mdc` files). For users who want Cursor-only ownership of their rules directory, the current opt-out is to drop `cursor` from `harness.yaml.targets`. A finer-grained `harness.yaml.cursor.opt_out_render: bool` flag is deferred to a follow-up PLAN.

---

## Appendix A: Decisions Log (v0.1 → v2.0)

Detailed change history is absorbed into all ADR + Risk + Goal decisions in this spec. Key evolution:

- **v0.1** (Draft): 6 R requirements, M1-M4 mode classification, 5 monitoring metrics, 4 commands, 8 phases
- **v1.0**: M1-M4 retired, 2 presets (Side/Production), 3 metrics consolidated, single meta command, 12-week phases
- **v1.1**: Meta-tool / runtime separation (all day-to-day commands moved to user harness)
- **v1.2**: /hm: prefix
- **v1.3**: Workflow abstraction (atomic + fused) + Model tier configuration
- **v1.4**: Worktree isolation + 5 Security Gates (influenced by Archon/ECC)
- **v1.5**: Agent quality drill-down (sub-rubric of Health)
- **v1.6**: Context lint + Privilege separation + Provenance frontmatter (arxiv 2602.11988 / 2603.13424 / 2604.03081)
- **v2.0**: autoloop-ready format — Section 0-6 structure, 10 phases, all R/M/A entries explicitly mapped to Section 4 tasks or Section 5 verify
- **v2.1**: autoloop dry-run analysis 10 fixes — (C1) Renderer freeze_time, (C2) plugin entry subprocess task, (C3) Anthropic URL explicit, (I1) SubAgent permissions schema research, (I2) remove vault path dependency, (I3-I5) atomic write/LLM mock/worktree cleanup CLAUDE.md, (M1-M2) Phase 9 marker + file count assertion
- **v2.2** (this spec): 2nd dry-run analysis expanded fix set — (a) **Phase 2 split** (9 tasks → Phase 2 Foundations 3 + Phase 3 Pipeline 6) — autoloop's own recommendation. (b) **Phase 7 split** (9 tasks → Phase 8 Worktree 3 + Phase 9 Security 6) — same pattern. (c) **Task 1.0 env precheck** (uv/python3.12+/git/cache write — fail fast). (d) **Cross-phase invariant gate** — each phase Exit Criteria calls `phase_<N>_invariants` (validates frontmatter of generated `.claude/` assets). (e) Total phases: 10 → **12**. (f) Verify script fully revised — 12 phase functions, env check, invariants helper. (g) `max_global_iterations` 100 maintained (12×5=60 worst case, sufficient margin).
- **v2.3** (0.5.x status update, 2026-05): (a) M1 targets/recommended_model/locale-en additions. (b) M4 anti-rot GitHub source actual values reflected (anthropics/claude-code default). (c) M5 SessionStart drift reminder hook + hybrid telemetry schema. (d) M7 feature/improve mode + per-loop worktree (wrapup once). (e) M9 worktree path `.worktrees/` (project root) + prefix-match cleanup. (f) M13 pre-Codex manifest version invariant. (g) **M14 new** — Cursor target rendering. (h) §5 skills 10→11 (refdocs-search added), M14 verify row. (i) ADR-11/12/13 new.
- **v2.4 (0.9.3, 2026-05-10)** — Codex target added as a first-class render target: `AGENTS.md`, `.codex/config.toml`, `.codex/hooks.json`, `.codex/agents/*.toml`, and `.agents/skills/*/SKILL.md`. `/harness-maker:make` supports `ref_folders` and `sibling_repos`; refdocs indexing is built after render, and sibling repositories participate in worktree isolation.
- **v2.1 (0.7.1, 2026-05-08)** — Patch release closing 9 deferred review findings. ADR-101 to ADR-108: scope, telemetry env-var cwd, daily metrics rotation, doc-only read-staleness, pure-filesystem hallucination, threading.local re-entrant flock, tool_input whitelist + secret redaction, drift_monitor XML fence. /hm:review round-2 P0 fixes: flock-before-depth ordering; raw os.write for atomic O_APPEND.

---

## Appendix B: Glossary

| Term | Meaning |
|---|---|
| Harness | A per-project bundle of configuration, scripts, and memory for using Claude Code (the `.claude/` tree) |
| Synthesizer | Maps preset + user responses → blueprint (deterministic) |
| Blueprint | The list of files to be generated along with their contents (the step before Apply) |
| Preset | Side / Production — a bundle of defaults across 10+ dimensions |
| Reconciler | Resolves conflicts between existing `.claude/` assets and a new blueprint in brownfield projects |
| Anti-rot | Automatically keeps the harness current so it does not go stale over time (manual confirm required) |
| Autoloop | One-line goal → autonomous iteration cycle until convergence (default: 8h/30 iterations) |
| Efficiency / Health / fresh | 3 core metrics (cache hit% / readiness 0-100 / days since last refresh) |
| Atomic stage | 7 built-in stages (`research`, `spec`, `plan`, `execute`, `review`, `wrapup`, `verify`), each as `/hm:<stage>` |
| Workflow (fused) | A user-named stage sequence. Renderer synthesizes fragments → 1 command, 1 turn |
| Conditional Routing | Selects reviewer based on the region of changed files |
| Verify-before-completion | Automatic gate immediately before `/hm:wrapup` |
| Modular installer | Per-unit installation outside of preset (`make --add reviewer:security`) |
| Worktree isolation | `/hm:execute` operates only inside a git worktree |
| 7 security gates | secrets · permissions · hook injection · CVE · prompt injection · hallucination · prod-name guard |
| Agent quality rubric | Per-agent Platinum/Gold/Silver/Bronze rating (Health drill-down) |
| Context lint | Blocks verbose output at the generator stage |
| Privilege separation | reviewer = Read/Grep only, executor = Write(.worktrees/**) only |
| Provenance frontmatter | All generated assets include `generated_by` + `content_hash` + `source_template` |
| fixture | A synthetic project used for validation (Side/Production × Python/Tauri/Firmware) |
| targets | Runtime selection axis in HarnessConfig — `claude-code` \| `cursor` \| `codex` \| any combination. User makes an explicit selection during interview (auto-detect prohibited) |
| recommended_model | Recommended model ID stored in `harness.yaml`; propagated to agent frontmatter (default: claude-opus-4-7) |
| Multi-target Rendering (M14) | `.claude/` for Claude Code and Cursor, `.cursor/` for Cursor glue, `.codex/` + `.agents/skills/` + `AGENTS.md` for Codex |
| SessionStart drift reminder | Hook that warns at session start when harness-maker version differs from the version at render time |

---

## Appendix C: Sources & Citations

**Competing/reference frameworks:**
- hiloop: ai-readiness-rubric (Health), failures.md/wiki.md memory, autoloop-coder agent
- Synthesis (Rajiv Pant, 2026-04): `.agents/` convention, adopted for Codex skill discovery in 0.9.0
- claude-statusline-enhanced: cache hit display (statusLine feature — removed in harness-maker, replaced by ai-readiness)
- obra/superpowers: verify-before-completion gate, multi-host manifests
- wshobson/agents: Conditional Routing + per-agent model tier + 3-layer eval (agent quality)
- davila7/claude-code-templates: Modular installer pattern
- coleam00/Archon (added v1.4): YAML workflow + worktree isolation + deterministic nodes
- affaan-m/everything-claude-code (ECC): AgentShield security scaffolding
- scalarian/oh-my-codex: tmux worktree lifecycle
- HKUDS/OpenHarness: Auto-Compaction multi-day sessions
- Yeachan-Heo/oh-my-claudecode: keyword-based mode auto-activation pattern

**arxiv academic foundations (v1.6, 2025-11~2026-05):**
- AHE — Agentic Harness Engineering ([arxiv 2604.25850](https://arxiv.org/abs/2604.25850)): justifies anti-rot automatic evolution closed-loop
- OpenDev ([arxiv 2603.05344](https://arxiv.org/abs/2603.05344)): 5-layer defense-in-depth → justifies 5 security gates
- Inside the Scaffold ([arxiv 2604.03515](https://arxiv.org/abs/2604.03515)): classifies 5 loop primitives
- Evaluating AGENTS.md ([arxiv 2602.11988](https://arxiv.org/abs/2602.11988)): verbose context = lower success rate, +20% cost → basis for context lint introduction
- Routing/Cascades ([arxiv 2602.09902](https://arxiv.org/abs/2602.09902)): static routing optimal → justifies model tier
- OpenClaw — Privilege Separation ([arxiv 2603.13424](https://arxiv.org/abs/2603.13424)): privilege separation ASR 0.31% vs filter 14% → basis for privilege separation introduction
- Supply-Chain Poisoning ([arxiv 2604.03081](https://arxiv.org/abs/2604.03081), CVE-2025-59536): basis for provenance frontmatter introduction

---

**v2.0 finalized** (autoloop-ready). `vault/.claude/commands/autoloop.md` can parse Sections 0-6 of this spec and perform autonomous builds. Phase 0 kickoff is ready.

---

*Document health: Last reconciled against code 2026-05-07 (0.5.x). M14 + ADR-11/12/13 + 0.5.x addenda added in v2.3.*
