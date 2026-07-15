# Showcase — same maintainer, two real projects, two structurally different harnesses

> Live render evidence for the README headline.
> Generated 2026-07-15 against `harness-maker @ v0.39.0`.
> Numbers below are fresh renders of each project's real `.claude/harness.yaml`
> through the actual `synthesize → render` pipeline — reproducible, not hand-counted.

This page captures what `harness-maker make` produces when you run it against two real repositories owned by the same maintainer (`Ecro`):

- **log_agent** — small Python log tool, single-developer cadence → user picked **`Side` preset, `claude-code` target only**.
- **spoton** — firmware + app product, spec-driven, multi-model review → user picked **`Production` preset, `claude-code + codex` targets**.

Same maintainer, same base stack. Different `.claude/` shape because the **preset and targets are different inputs**, not because we hand-tuned the output. The interview locked these choices once; every `harness-maker make` since reproduces them.

---

## The two axes — and what each one actually changes

harness-maker's output is a pure function of `(profile, harness.yaml)`. Two independent axes drive the diff between these projects, and they change **different things**:

| Axis | What it changes | Between these two projects |
|---|---|---|
| **`targets`** (`claude-code` / `cursor` / `codex`) | The **file set** — which IDE-native assets get rendered | spoton adds the whole `codex` surface; log_agent stays `claude-code`-only |
| **`preset`** (`Side` / `Production`) | The **content and behavior** of the *same* files — model tiers, dev_mode default, reviewer depth, gates, worktree model, context budgets | identical file *names*, different *values* inside them |

The key correction over earlier drafts of this page: **preset does not add or remove agent/skill files.** `synthesize.py:101` is explicit — *"Every preset installs the full reviewer/skill inventory; activation is data, not file presence."* Both presets render the **identical 14-agent set**. The file-set diff you see below comes almost entirely from `targets`, not `preset`.

---

## Rendered file count

| Surface | Side · log_agent | Production · spoton | Δ |
|---|---:|---:|---|
| `.claude/agents/*.md` | **14** | **14** | 0 |
| `.claude/skills/*/SKILL.md` | 9 | 9 | 0 |
| `.claude/commands/hm/*.md` | 20 | 20 | 0 |
| `.claude/stages/*.md` | 7 | 7 | 0 |
| `.claude/rubrics/*.yaml` | 4 | 4 | 0 |
| `.codex/agents/*.toml` | — | **14** | +14 |
| `.agents/skills/*/SKILL.md` (codex dual-render) | — | **24** | +24 |
| `.codex/*` config | — | 2 | +2 |
| `AGENTS.md` (project root) | — | 1 | +1 |
| `.claude/schemas/second-opinion-*.json` | — | 1 | +1 |
| **Total rendered files** | **62** | **104** | **+42** |

The +42 is **not** a "Production ships more agents" effect. It is the `codex` target rendering an entire second IDE surface (14 agent TOMLs + 24 codex-path skill dual-renders + 2 `.codex/` config files + root `AGENTS.md`), plus one JSON schema pulled in because spoton enabled cross-model second opinion. Turn the `codex` target off and spoton's file *set* collapses to log_agent's.

---

## Agent set — identical across presets (this is the corrected claim)

Both projects render the **same 14 agents**. A fresh render of each real config confirms the symmetric difference is empty:

```
.claude/agents/   (14 files, IDENTICAL set in Side and Production)
├── autoloop-coder.md        ├── performance-reviewer.md
├── code-reviewer.md         ├── plan-validator.md
├── code-verifier.md         ├── security-auditor.md
├── concurrency-reviewer.md  ├── security-reviewer.md
├── consensus-arbiter.md     ├── stuck.md
├── executor.md              ├── test-reviewer.md
├── judgment-reviewer.md     └── ux-reviewer.md
```

`autoloop-coder`, `concurrency-reviewer`, `plan-validator`, `stuck`, and `test-reviewer` ship on **both** sides. The renderer installs the full inventory unconditionally (`synthesize._ALL_AGENTS`); the preset decides how those agents are *configured and activated*, not whether the file exists.

> **Caveat if you `ls` spoton directly:** spoton's on-disk `.claude/.harness-manifest.json` lists only 11 `.claude/agents/`. That is a **customization** artifact, not a preset one — the maintainer hand-edited `code-reviewer` / `concurrency-reviewer` / `performance-reviewer` (they lost their `generated_by:` frontmatter and were bumped to `model: opus`), so reconcile made them user-owned and dropped them from the *generated* manifest. A clean render of spoton's `harness.yaml` produces all 14.

---

## What the **preset** actually changes (same files, different content)

This is where `Side` vs `Production` lives — inside the identical files:

| Dimension | Side · log_agent | Production · spoton | Source |
|---|---|---|---|
| `dev_mode` default | `task-driven` | `spec-driven` (SPEC gate + plan-validator engage) | preset default |
| Agent **model tier** | all `sonnet` | reasoning agents (`autoloop-coder`, `plan-validator`, `stuck`) → `opus/high`; reviewers → `sonnet/medium` | `presets.py` `_SIDE_MAP` / `_PRODUCTION_MAP` |
| Reviewers enabled | `[code-reviewer]` (1) | `[code, security, performance, ux, concurrency]` (5) | `reviewers.enabled` |
| Grade threshold | `B` | `A` | `reviewers.grade_threshold` |
| Max review rounds | `2` | `3` | `reviewers.max_review_rounds` |
| Worktree model | `feature_branch_workflow: false`, scope `[execute]` | `feature_branch_workflow: true`, scope `[execute, plan]` | `worktree.*` |
| Cross-model 2nd opinion | none | `models: [codex, antigravity]` | `second_opinion` |
| Context budgets (lint) | CLAUDE.md 200 / agent 150 / skill 100 | CLAUDE.md 500 / agent 200 / skill 150 | `context_lint.py` |

None of these are file-count differences — they are the *values the renderer writes into* `harness.yaml`, `settings.json`, each agent's `model:` frontmatter, and the stage/command bodies.

---

## What `harness.yaml` looks like for each

The single source of truth that drives every render (real excerpts):

**Side · log_agent**
```yaml
preset: Side
locale: ko
dev_mode: task-driven        # no SPEC gate
targets:
  - claude-code              # one IDE → no .codex/, no AGENTS.md
reviewers:
  enabled:
    - code-reviewer          # 1 active reviewer
  grade_threshold: B
  max_review_rounds: 2
worktree:
  scope: [execute]           # plan does not run in a worktree
# no second_opinion block
```

**Production · spoton**
```yaml
preset: Production
locale: ko
dev_mode: spec-driven        # SPEC gate + plan-validator engage
targets:
  - claude-code
  - codex                    # → 14 .codex/agents/*.toml + AGENTS.md + .agents/skills/*
reviewers:
  enabled:
    - code-reviewer
    - security-reviewer
    - performance-reviewer
    - ux-reviewer
    - concurrency-reviewer   # 5 active reviewers
  grade_threshold: A
  max_review_rounds: 3
worktree:
  scope: [execute, plan]     # plan also runs in a worktree
  feature_branch_workflow: true
second_opinion:
  models: [codex, antigravity]   # cross-model consensus, K=2
  agents: [code-reviewer, consensus-arbiter, plan-validator]
```

Neither shape was guessed. Both came from the interview each maintainer answered once per project, and both re-render deterministically.

---

## How to reproduce this exact comparison

The renders are a pure function of `harness.yaml`. To verify the file-set diff:

```bash
# Fresh-render each project's real config into a temp dir and diff the file lists:
harness-maker make /path/to/log_agent --preset Side    --targets claude-code
harness-maker make /path/to/spoton    --preset Production --targets claude-code,codex

diff <(jq -r '.files[]' /path/to/log_agent/.claude/.harness-manifest.json | sort) \
     <(jq -r '.files[]' /path/to/spoton/.claude/.harness-manifest.json   | sort)
```

You will see the **+42 codex-target files** as the structural diff, and an **identical `.claude/agents/` set** on both sides. The preset difference is not in the file list at all — it is inside the files (`grep -H '^model:' */.claude/agents/*.md` shows `opus` only on Production's three reasoning agents).

---

## Why this matters for the headline

> **"Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness."**

The headline holds — but the proof is two-part, not "Production has more files":

- **Targets** produces a genuinely different *file set*: spoton carries a full `.codex/` IDE surface + `AGENTS.md`; log_agent does not.
- **Preset** produces a different *harness behavior* in the same files: opus reasoning agents vs all-sonnet, a 5-reviewer grade-A spec-driven gate vs a 1-reviewer grade-B task-driven flow, a per-task feature-branch worktree model vs a single-scope one, cross-model second opinion vs none.

Other harnesses (BMAD, SuperClaude, claude-flow, agent-os, spec-kit) ship a fixed bundle — two projects get identical files *and* identical behavior. harness-maker ships a **renderer**: two projects owned by the same person, on the same base stack, get a different file set *and* different behavior because their `harness.yaml` answered different questions.

---

*See also: [RESEARCH-harness-maker-cold-eval.md](../../work-docs/RESEARCH-harness-maker-cold-eval.md) for the cold evaluation that locked this headline, and [PLAN-harness-maker-cold-eval.md](../../work-docs/PLAN-harness-maker-cold-eval.md) ADR-002 for the showcase decision and its quantitative threshold.*
