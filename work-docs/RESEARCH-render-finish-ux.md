---
type: research
task_slug: render-finish-ux
status: complete
created: 2026-06-27
tags: [harness-maker, research, python, ux, onboarding, git]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[PLAN-onboarding-ux-2026-05]]"
  - "[[PLAN-onboarding-backup-friction]]"
  - "[[RESEARCH-install-without-claude-code]]"
summary: "Slash-owned friendly render narrative + dry-run preview (NOT worktree) + post-render git-disposition step"
---

# RESEARCH — render-finish-ux

## 🎯 Recommended Direction

**Make `/harness-maker:make` a guided experience that runs all the way to "your files are
in git the way you want" — without a worktree.** Three coordinated changes: (1) the slash
command (Claude) owns a clean, locale-aware **render narrative** ("what changed / what was
preserved / what's next"), the Python CLI stays machine-parseable; (2) instead of a worktree,
promote the existing **`--dry-run` preview into a "preview → confirm → apply" step** for
re-renders over an existing `.claude/`; (3) add a **post-render git-disposition step** that
detects git state and asks the user to *commit* (share with team — recommended default) or
*gitignore* `.claude/` (keep local), then performs the chosen action idempotently.

Rationale: the render *mechanics* are already safe (backup + reconcile KEEP/MERGE + churn
gitignore). What's missing is **narrative clarity and the last mile** — the user is left with
freshly written files and no guidance on the one decision every project owner must make: do
these go into version control or not. A worktree adds a merge round-trip and a hard git
dependency without solving either gap; a dry-run preview solves the "don't surprise me"
concern more cheaply.

## 🔍 Refinement Decisions

- Discovery lens: **User-workflow / product opportunity** (primary — onboarding friction,
  "what do I do with these files now") + **Technical architecture** (where the render
  narrative and git step live: CLI vs slash command).
- `--deep` not set; dived directly per topic clarity.

## 🛠️ Approaches Found

### Concern 1 — "Render is unfamiliar; make it clean and friendly"

| Field | Content |
|-------|---------|
| Approach | **A. Slash-owned narrative, CLI stays machine output** (recommended) |
| Assumption | Claude (slash command) is the right layer for friendly locale prose; Python owns type-contracts/safety only |
| Evidence | `CLAUDE.md` LLM-활용 원칙: "Python 레이어는 타입 계약·저장·안전 레일만"; `PLAN-onboarding-ux-2026-05` ADR-001 already chose "slash-command prose is the receipt source" |
| Trade-off | Narrative quality depends on Claude reading CLI output faithfully; needs a stable machine-readable summary line from the CLI to anchor on |
| Compatibility | Fits `make.md` §6 (Report + Quick start) — extend it into a structured "what changed" story |
| Risk | low |

| Field | Content |
|-------|---------|
| Approach | **B. Prettier CLI output (rich/colored, progress bars)** |
| Assumption | The terminal dump itself should be the friendly surface |
| Evidence | `cli.py` currently prints `───` separators + `_emit_install_summary` + `_emit_post_make_readiness` (structural-health dump fires immediately after install — noisy for a first-timer) |
| Trade-off | Double-formatting (CLI output is relayed by Claude in slash context); adds a TUI dependency; violates the "Python = safety rails only" principle |
| Compatibility | Conflicts with slash-driven onboarding; would compete with Claude's narrative |
| Risk | medium |

**Binding trade-off:** the render output is consumed *through Claude* in slash context, so
the friendly surface belongs in the slash command. The CLI's job is to emit a **stable,
parseable summary** (counts: NEW / REPLACE / KEEP / MERGE_BLOCK, target roots, backup path)
that Claude turns into locale prose. Concrete sub-fixes: (a) demote the immediate
structural-health dump to a one-line pointer to `/hm:health` on fresh install, (b) give the
CLI a `--json`/summary line for the render result so the narrative is grounded in facts not
guesses.

### Concern 2 — "Should render happen in a worktree?"

| Field | Content |
|-------|---------|
| Approach | **No worktree; promote `--dry-run` into preview→confirm→apply** (recommended) |
| Assumption | The real desire is "let me see/approve what render will touch before it touches my tree," not branch isolation |
| Evidence | `make` writes to the *real* `<cwd>/.claude/` (`cli.py:394` `target_dotclaude = target / ".claude"`); safety already = `backup()` + `reconcile()` KEEP/MERGE_BLOCK + `_ensure_harness_gitignore`; `_emit_dry_run_summary` already exists |
| Trade-off | Preview adds one confirm step on re-render; no isolation guarantee (but none is needed — backup is the rollback) |
| Compatibility | `--dry-run` already implemented; just needs to be wired into the slash flow for the over-existing-files case |
| Risk | low |

| Field | Content |
|-------|---------|
| Approach | **B. Render inside `.worktrees/<slug>/`, merge back** |
| Assumption | Branch isolation makes render safer/reviewable |
| Evidence | The worktree model (`worktree.py`, `feature_branch_workflow`) is built for `/hm:` *task stages*, not for installing `.claude/` itself |
| Trade-off | (1) Hard git dependency — `RESEARCH-install-without-claude-code` shows fresh/non-git targets are a real install case; a worktree would block them. (2) `.claude/` must end up at the project root, so a worktree render needs a merge-back round-trip = more friction, the exact thing this task is trying to reduce. (3) No safety gain over the existing backup. |
| Compatibility | Poor — make is the bootstrap command, distinct from task stages |
| Risk | high (friction + git-only regression) |

**Binding trade-off:** a worktree trades a hard git requirement and a merge round-trip for
isolation that the backup already provides. Reject it. If isolation-style review is wanted,
a lighter option is render-to-tempdir + `git diff --no-index` preview — but `--dry-run`
already covers the same need.

### Concern 3 — "After render, ask: gitignore `.claude/` or commit it?"

| Field | Content |
|-------|---------|
| Approach | **Post-render git-disposition step: detect state → ask commit/gitignore → act idempotently** (recommended) |
| Assumption | Every project owner must decide whether the harness is team-shared (commit) or personal (ignore); we currently leave them hanging |
| Evidence | Auto-gitignore today covers **only churn** (`worktree.py:91-127` `_HARNESS_CHURN_*` → observability, iter-receipts, markers, loop-context) + `.backup-*/`. The actual content (`harness.yaml`, agents, commands, skills, hooks) is neither ignored nor prompted. `make.md` §6 ends at "Quick start" with no git guidance. `HOW-IT-WORKS.md` commit guidance is all about `/hm:wrapup`, never the install. |
| Trade-off | One more interactive step; must be idempotent so re-render doesn't re-nag |
| Compatibility | High — `_ensure_gitignore_entry` (idempotent, subsumption-safe, WSL2-safe append) already exists; churn already gitignored means "commit `.claude/`" is *clean* (no receipts/backups leak in) |
| Risk | low-medium |

**Design notes for this approach (informational — `plan` locks them):**
- **Detect, don't persist** (checkpoint #6): infer prior decision from git state each run —
  `.claude/` already tracked → already in "commit" mode; `.claude/` already matched by
  `.gitignore` → "ignore" mode. No new `harness.yaml` key needed; avoids re-prompt (checkpoint #5).
- **Non-git guard** (checkpoint #8): `git rev-parse --is-inside-work-tree`; if not a repo,
  skip with a one-line note (offer `git init`).
- **Three options:** (a) *Commit `.claude/`* — recommended default for teams; `git add .claude`
  + `git commit` (explicit user action, allowed). Churn + `.backup-*` already gitignored, so
  the commit is clean. (b) *Gitignore `.claude/`* — append `.claude/` for solo/local use
  (the existing per-line churn entries become redundant-but-harmless). (c) *Decide later* — leave as-is.
- **CLI vs slash split** (checkpoint #4): slash command drives `AskUserQuestion` + runs the
  `git commit` (no `input()` in CLI); a thin testable CLI helper can own the **idempotent
  gitignore mutation + git-state detection** (checkpoint #8 e2e boundary). The CLI must **never
  auto-commit** (git policy: explicit-request-only).

## ⚠️ Pitfalls

- **Re-prompt on every re-render** (CLAUDE.md checkpoint #5 — fingerprint/auto-upgrade-vs-preserve):
  if the git step doesn't detect a prior decision it will nag on each `/hm:make`. Infer from
  git state; do not re-ask once `.claude/` is tracked or ignored.
- **Worktree-on-non-git regression** (`RESEARCH-install-without-claude-code`): any git-coupled
  render path breaks the documented non-git / CLI-fallback install case.
- **Gitignoring the whole `.claude/` defeats team sharing**: a teammate cloning the repo gets
  no harness. Make the trade-off explicit in the prose; default to commit-to-share.
- **Double-adding gitignore lines / WSL2 Edit corruption** (CLAUDE.md memory 2026-02-15):
  reuse the idempotent `_ensure_gitignore_entry` append helper, never a raw Edit.
- **Auto-commit footgun** (CLAUDE.md git policy): the CLI must never commit on its own; only
  the slash command commits, and only on explicit user choice.
- **Noisy first-run health dump**: `_emit_post_make_readiness` fires a structural-health scan
  immediately after install — intimidating for first-timers; demote to a pointer.
- **Committed-then-ignored churn cosmetic** (CLAUDE.md accepted limitation): a user who already
  committed `.claude/observability/` keeps a cosmetic `M` in status — gitignore can't untrack;
  do not auto `git rm --cached`.

## ❓ Open Questions

1. **Git step home:** pure slash-command prose vs a thin CLI helper (`harness-maker git-setup`)
   for the idempotent gitignore + detection. (Lean: slash asks + commits; CLI helper owns the
   mechanical/testable parts.)
2. **Default recommendation:** commit-to-share vs gitignore-local as the highlighted default?
   (Lean: commit-to-share.)
3. **Dry-run preview scope:** preview→confirm→apply for *all* re-renders over existing files,
   or only when REPLACE/MERGE counts exceed a threshold? Fresh installs skip preview?
4. **Render narrative depth:** how much of the structural-health scan to keep inline on fresh
   install vs collapse to a `/hm:health` pointer?
5. **Granular git option:** offer "commit `harness.yaml` only, ignore the rest" as a third
   path, or keep it binary (commit-all / ignore-all)?

## 📚 Sources

- Internal only (this is harness-maker self-architecture; no external libs in scope).
- `src/harness_maker/cli.py` — `make` flow, `_emit_install_summary`, `_emit_post_make_readiness`, `_emit_dry_run_summary`.
- `src/harness_maker/worktree.py:80-152` — `_HARNESS_CHURN_*`, `_ensure_harness_gitignore`, `_ensure_gitignore_entry`.
- `commands/make.md` — slash orchestration §6 Report + Quick start.
- `docs/HOW-IT-WORKS.md` — commit guidance (wrapup-only, confirms install-time gap).

## 🔗 Related Internal Docs

- [[PLAN-onboarding-ux-2026-05]] — locale-first onboarding + receipt prose (ADR-001 slash-prose-as-receipt). This task extends that receipt to the git last mile.
- [[PLAN-onboarding-backup-friction]] — `.backup-*/` auto-gitignore (the safety net that makes a worktree unnecessary).
- [[RESEARCH-install-without-claude-code]] — non-git / CLI-fallback install case (why worktree-for-render regresses).
