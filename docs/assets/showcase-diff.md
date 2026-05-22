# Showcase — same maintainer, two real projects, two structurally different harnesses

> Live render evidence for the README headline.
> Generated 2026-05-22 against `harness-maker @ v0.21.0`.

This page captures what `harness-maker make` produces when you run it against two real public repositories owned by the same maintainer (`Ecro`):

- **embedeval** — Python embedded-firmware LLM benchmark. Smaller scope, single-developer cadence → user picks **`Side` preset, `claude-code` target only**.
- **harness-maker** (self) — Public OSS plugin, multi-IDE, public-facing → user picks **`Production` preset, `claude-code + cursor + codex` targets**.

Same maintainer. Same stack (Python + `uv` + Pydantic + GitHub Actions). Different `.claude/` shape because the **preset and targets are different inputs**, not because we hand-tuned the output. The interview locked these choices once; every `harness-maker make` since reproduces them.

---

## Rendered file count

| Surface | Side · embedeval | Production · harness-maker | Δ |
|---|---:|---:|---|
| `.claude/agents/*.md` | **8** | **13** | +5 |
| `.claude/skills/*/SKILL.md` | 11 | 11 | 0 |
| `.claude/commands/hm/*.md` | 17 | 17 | 0 |
| `.claude/stages/*.md` | 7 | 7 | 0 |
| `.claude/rubrics/*.yaml` | 4 | 4 | 0 |
| `.codex/agents/*.toml` | — | **13** | +13 |
| `.codex/config.toml` | — | 1 | +1 |
| `.cursor/hooks.json` | — | 1 | +1 |
| `AGENTS.md` (project root) | — | 1 | +1 |
| **Total rendered files** | **54** | **99** | **+45** |

The full file lists live in each project's `.claude/.harness-manifest.json`. Two axes drive the diff:

1. **Preset (`Side` vs `Production`)** — adds 5 agents on the Production side.
2. **Targets (`[claude-code]` vs `[claude-code, cursor, codex]`)** — adds 15 IDE-native files (13 Codex agent TOMLs + Codex config + Cursor hooks + AGENTS.md root file).

Neither axis was guessed. Both came from the 10-dim interview the user answered once per project.

---

## Agent set — the preset-driven core difference

Side (embedeval) ships the reviewers + executor scaffolding that a solo experimental project actually uses:

```
.claude/agents/
├── code-reviewer.md          ← primary reviewer
├── code-verifier.md          ← Phase 1.5 verifier
├── consensus-arbiter.md      ← reviewer consensus
├── executor.md               ← stage orchestrator
├── performance-reviewer.md   ← conditional-router activation
├── security-auditor.md       ← 5-gate scanner driver
├── security-reviewer.md      ← conditional-router activation
└── ux-reviewer.md            ← conditional-router activation
```

Production (harness-maker self) adds **5 agents** that only make sense once a project is going public and has multi-session collaboration:

```
.claude/agents/
├── (8 above — Side core)
├── autoloop-coder.md         ← autonomous /hm:loop coding agent
├── concurrency-reviewer.md   ← race / lock / ISR review
├── plan-validator.md         ← /hm:plan pre-write critique
├── stuck.md                  ← escalation analyst when /hm:execute blocks
└── test-reviewer.md          ← Phase A.5 test-quality gate
```

These are not "more is better" additions. Each one is **tied to a stage that exists on Production but not on Side**:
- `plan-validator` runs only when `dev_mode: spec-driven` engages `/hm:plan` deep-interview output.
- `test-reviewer` runs only when `dev_mode: spec-driven` engages Phase A.5.
- `stuck` runs only when `/hm:execute` blocks and the workflow has a stuck-escalation step.
- `concurrency-reviewer` runs only when the conditional router sees async / lock / ISR file paths.
- `autoloop-coder` runs only when `/hm:loop` is used.

Side disables these stages, so it does not render the agents. Production enables them, so it does.

---

## Skill set — identical 11 skills both sides

Both projects render the same 11 skills:

```
agent-quality-rubric · ai-readiness-rubric · autoloop-driver
conditional-router · context-linter · refdocs-search
relevance-filter · research-crawler · security-scanner
verify-before-completion · worktree-isolator
```

These are **mechanism skills** (deterministic Python-backed helpers), not preset-tied. Every harness gets them. The preset shapes *which agents call them* and *which workflows fire them*, not the skill set itself.

---

## What `harness.yaml` looks like for each

The single source of truth that drives every render:

**Side · embedeval** (excerpt):
```yaml
preset: Side
locale: en
dev_mode: task-driven       # no SPEC gate, no plan-validator
targets:
  - claude-code             # one IDE only
reviewers:
  enabled:
    - code-reviewer         # 1 active reviewer
  routing: conditional
  grade_threshold: A        # Side still defaults to A
worktree:
  scope: [execute]          # plan does not run in worktree
```

**Production · harness-maker self** (excerpt):
```yaml
preset: Production
locale: ko                  # maintainer's onboarding locale
dev_mode: task-driven       # task-driven by maintainer's choice — not preset-forced
targets:
  - claude-code             # all three IDEs
  - cursor
  - codex
reviewers:
  enabled:
    - code-reviewer
    - security-reviewer     # maintainer kept the set at 2 (preset default is 5)
  routing: conditional
  grade_threshold: A
  max_review_rounds: 3
worktree:
  scope: [execute, plan]    # plan also runs in worktree (Production default)
```

Note: harness-maker self uses `task-driven` not `spec-driven` — the maintainer overrode the preset default. The point of this showcase is not that *Production forces* certain settings, but that **the interview answers carry forward and produce different renders**. Even when `dev_mode` is the same in both, the preset still differs the agent set.

---

## How to reproduce this exact comparison

The renders are deterministic given the same `harness.yaml`. To verify:

```bash
# Render Side preset against any clean Python repo:
harness-maker make /path/to/your-repo --autoloop --preset Side --targets claude-code

# Render Production preset against any clean Python repo:
harness-maker make /path/to/your-repo --autoloop --preset Production \
  --targets claude-code,cursor,codex

# Compare:
diff <(jq -r '.files[]' /path/to/side-render/.claude/.harness-manifest.json | sort) \
     <(jq -r '.files[]' /path/to/prod-render/.claude/.harness-manifest.json | sort)
```

You will see the **+5 agents** and **+15 multi-IDE assets** as the structural diff. No keyword guessing, no hand-curated template — the profiler reads your repo's stack signals, the interview locks the 10 dimensions, and the render is a pure function of `(profile, harness.yaml)`.

---

## Why this matters for the headline

> **"Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness."**

The headline is verifiable, not marketing copy:
- Other harnesses (BMAD, SuperClaude, claude-flow, agent-os, spec-kit) ship a fixed bundle. Two projects using them get the same files.
- harness-maker ships a **renderer**. Two projects get different files because their `harness.yaml` answers different questions.

The 45-file diff between these two real projects, owned by the same person, on the same Python stack, is the cheapest concrete proof of that claim.

---

*See also: [RESEARCH-harness-maker-cold-eval.md](../../work-docs/RESEARCH-harness-maker-cold-eval.md) for the cold evaluation that locked this headline, and [PLAN-harness-maker-cold-eval.md](../../work-docs/PLAN-harness-maker-cold-eval.md) ADR-002 for the showcase decision and its quantitative threshold.*
