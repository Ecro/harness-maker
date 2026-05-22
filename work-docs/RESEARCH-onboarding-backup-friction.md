---
type: research
task_slug: onboarding-backup-friction
status: complete
created: 2026-05-22
tags: [harness-maker, research, onboarding, ux, backup, reconcile, brownfield]
mtime_warn_days: 7
libs_fetched: []
sources:
  - src/harness_maker/cli.py:353-354
  - src/harness_maker/reconcile.py:259-288
  - src/harness_maker/render.py:180-209
  - src/harness_maker/render.py:620-682
  - commands/make.md:118,199-202,278-282
  - docs/ARCHITECTURE.md:130-139
  - work-docs/RESEARCH-onboarding-ux-2026-05.md
related_docs:
  - "[[RESEARCH-onboarding-ux-2026-05]]"
  - "[[ARCHITECTURE]]"
  - "[[block-merge-spec]]"
summary: "Make the .backup-<ts>/ copy conditional on reconcile finding destructive ops; auto-gitignore + retention; expose --no-backup."
---

# RESEARCH — Onboarding backup friction (`.backup-<ts>/` is unconditional)

## 🎯 Recommended Direction

**Make the backup conditional on reconcile finding at least one REPLACE / MERGE_BLOCK, auto-add `.backup-*/` to the user's `.gitignore`, and expose a `--no-backup` opt-out.** For the common first-onboarding case where the user has their own `.claude/` content and reconcile would KEEP every file, we should print a one-line receipt ("kept N user files as-is, no backup needed") and exit without copying anything. When destructive ops do fire, keep the current copy but make it invisible to git so it stops surfacing in `git status`. The trade-off that binds is **trust vs friction**: the unconditional copy is the "belt" beneath reconcile's "suspenders", but the disk receipt (108 backup dirs in this repo alone) and the on-first-impression confusion outweigh the marginal safety in the KEEP-only path. A full per-file receipt-first preview (overlapping with `[[RESEARCH-onboarding-ux-2026-05]]` Approach A) is a larger project that should land in a follow-on PLAN, not be conflated with the immediate fix.

## 🔍 Refinement Decisions

Discovery lens: **technical architecture / implementation** (where `backup()` is called and what preservation primitives already exist) + **user-workflow / product opportunity** (the perceived friction is psychological, not just disk-cost). Phase 0 / 0.5 skipped — no `--deep` flag and the topic is concretely scoped to a single subsystem.

## 🛠️ Approaches Found

### Approach A — Conditional backup (skip when reconcile has no destructive ops)

| Field | Content |
|-------|---------|
| Approach | Run `reconcile()` first; if every decision is KEEP or BOTH (no REPLACE, no MERGE_BLOCK), skip `backup()` entirely and print a receipt. Backup only when ≥1 file would be overwritten. |
| Assumption | The backup's only purpose is recovery from destructive ops. If no destructive op fires, the copy is pure friction. |
| Evidence | `cli.py:351-362` already computes `conflicts` *immediately after* `backup()` and uses the decisions to filter the blueprint — the same `reconcile()` call can be moved up one block. `reconcile.py:168-176` defaults to KEEP when there's no frontmatter (this is the common first-onboarding-with-existing-.claude state). `docs/ARCHITECTURE.md:139` already documents "Apply is ADD-only" — KEEP-only paths never lose user data. |
| Trade-off | One extra pass over file metadata before deciding. Recovery for the no-destructive path now lives in git (not a sibling dir). |
| Compatibility | High. Same `reconcile()` semantics; just reordered. Existing `reconcile()` tests still pass; we add a "no-op backup is skipped" assertion. |
| Risk | Low. Worst case: a reconcile bug mis-classifies a file as KEEP when it should REPLACE — but that bug already exists today; backup wouldn't help because `backup()` doesn't intercept the bad decision, it just snapshots state before render runs. |

### Approach B — `--no-backup` CLI flag + slash-command opt-out

| Field | Content |
|-------|---------|
| Approach | Add `--no-backup` to `make`; surface as an option in `commands/make.md` §4.3 ("Looks right" branch): "I have git for recovery — skip backup". Default remains "always backup" until A lands. |
| Assumption | Some users (e.g. those on clean git workspaces) explicitly want to opt out. |
| Evidence | The CLI already has `--dry-run` and `--reinterview` flags that change destructive behaviour; flag surface is the canonical way to make safety toggles explicit. `commands/make.md:118` and `:278-282` already mention backup to the user as prose, so adding a "skip" option is a natural extension. |
| Trade-off | Footgun for users with uncommitted edits who type `--no-backup` and then discover reconcile chose REPLACE on an unread file. |
| Compatibility | High. Pure addition; no behaviour change for default invocations. |
| Risk | Low if default stays on; medium if user pairs it with `git stash`-but-forgot. Mitigation: refuse `--no-backup` when `git status --porcelain .claude/` shows uncommitted edits, unless `--force` is also set. |

### Approach C — Receipt-first preview with per-file backup (only the REPLACE/MERGE_BLOCK set)

| Field | Content |
|-------|---------|
| Approach | Always run reconcile first; if any destructive ops, show the user a structured receipt ("Would REPLACE M files, MERGE_BLOCK P files, KEEP N files") with a [Proceed] / [Skip backup] / [Cancel] choice. When backup is taken, only copy the M+P files that would be touched, not the whole tree. |
| Assumption | The user gets full information before any disk writes; backup size becomes proportional to what's at risk, not to the whole tree. |
| Evidence | `[[RESEARCH-onboarding-ux-2026-05]]` Approach A (recommended in that doc) already calls for receipt-first onboarding. Pitfall #4 of that document specifically flagged "Backup confidence without restore clarity". `cli.py` already has `_emit_reconcile_report()` and `_emit_dry_run_summary()` — the rendering layer exists. |
| Trade-off | Largest implementation effort. Backup helper needs a per-file mode. Receipt prose must stay in sync with the actual reconcile output. |
| Compatibility | Medium. Doesn't conflict with A or B, but order-of-operations changes (preview is shown BEFORE render dispatch instead of after) ripple into the slash-command flow. |
| Risk | Medium. Most surface area to test. Mitigated if landed after A so the structural skip-on-KEEP-only fix is already in. |

### Approach D — Keep current behaviour, add `.gitignore` wiring + retention

| Field | Content |
|-------|---------|
| Approach | `backup()` still always fires, but call `_ensure_gitignore_entry(project_root, ".backup-*/")` after the first one. Add a retention sweep that keeps only the last K (default 5) backups, or only those newer than N days (default 14). Print a "pruned X backups" receipt line. |
| Assumption | The disk cost and `git status` clutter are the friction, not the existence of the backup itself. |
| Evidence | `worktree.py:990-1025` already implements `_ensure_gitignore_entry()` and uses it for `.worktrees/` and `.claude/.hm-loop-*` — precedent for writing to the user's `.gitignore`. `render.py:799-804` explicitly notes the gitignore-template gap was left to a later phase. 108 backup dirs in the dogfood repo demonstrate the disk cost is non-trivial. |
| Trade-off | Doesn't address the "first run feels intrusive" psychological friction — the directory still appears, just stays out of `git status`. |
| Compatibility | High. Smallest behaviour change; orthogonal to A/B/C. |
| Risk | Low. Best-effort gitignore write already proven safe via worktree precedent. Pruning is destructive but only of our own files. |

### Approach E — Git-aware bypass

| Field | Content |
|-------|---------|
| Approach | Detect whether `.git/` exists AND `git status --porcelain .claude/ .cursor/ .codex/ .agents/ AGENTS.md` is empty. If clean, skip backup (recovery via git). If dirty or no git, keep current behaviour. |
| Assumption | Git is the canonical recovery mechanism when available; a parallel `.backup-<ts>/` is redundant in that case. |
| Evidence | The project already ships `git` shell-out elsewhere (worktree finalize, fresh-install health checks). The user's own dogfood pattern is git-everything; their friction confirms backup is largely redundant. |
| Trade-off | Requires `subprocess.run(["git", ...])` with timeout + error handling. False positives for users on jj/sapling/hg or for users who intentionally keep `.claude/` dirty as a staging area. |
| Compatibility | High. Falls back to current behaviour on detection failure. |
| Risk | Low for git users; medium for non-git users (false-negative path means we keep doing what we do today, which is "always backup" — strictly no regression). |

**Recommended composition for `/hm:plan`:** Approach **A** (conditional skip on KEEP-only) is the highest-leverage single change — it kills the friction in the common case at near-zero implementation cost. Add **D** (auto-gitignore + retention) as the floor for the destructive-op path. Surface **B** (`--no-backup` flag) as a one-liner power-user toggle. Defer **C** to a separate PLAN that aligns with `[[RESEARCH-onboarding-ux-2026-05]]` Approach A. **E** is interesting but should wait until A+D are proven — the marginal saving over A is small and the subprocess complexity isn't free.

## ⚠️ Pitfalls

1. **Reordering risk** — Currently `backup()` runs *before* `reconcile()` reads frontmatter. Approach A swaps the order. If we mis-handle the case where reconcile itself raises (corrupt frontmatter, unreadable file), we lose the safety net. Mitigation: wrap the reconcile call in try/except and fall back to "always backup" on any reconcile exception.

2. **The `.backup-*/` directory is at the project root, not under `.claude/`** — `reconcile.py:269` puts it at `existing_dir.parent / f".backup-{iso}"`. Any auto-gitignore entry needs the trailing slash (`.backup-*/`) to match a directory pattern, and must be appended to the project root's `.gitignore`, not `.claude/.gitignore` (which doesn't exist in user projects). `worktree.py:1004` already targets `project_root / ".gitignore"` — reuse that helper.

3. **`@hm:user:*` block markers and `_preserve_yaml_user_keys` already cover the most common preservation cases** — the user is partially fighting a ghost. The existing system already preserves their content during re-renders via in-place primitives; backup is the secondary safety net, not the primary preservation mechanism. The onboarding prose should make this distinction explicit so users stop reading `.backup-<ts>/` as "your stuff got moved".

4. **"Keep existing as-is" can mean two different things** — (a) keep the user's files where they are (already true via reconcile KEEP), or (b) don't add the harness-maker files at all (a `--audit-only` path that already exists). The slash command should disambiguate these before exposing a new option, or users will pick the wrong one.

5. **Backup retention pruning is irreversible** — Deleting old `.backup-*/` directories must be either user-gated (explicit `--prune-backups` flag) or accompanied by an audit line ("pruned 5 dirs, freed 14 MB"). Silent delete on every `/hm:make` violates `CLAUDE.md` §"체크포인트 1 — 사용자 상태 보존 계약을 먼저 그려라".

6. **Non-tty slash-command context cannot prompt** — Any new question added to `commands/make.md` §4.3 must have a sane default for the autoloop / `--ci` paths, since `AskUserQuestion` is unavailable there. Default for `--ci`: behave like the current "always backup", because automated callers can't react to a surprise.

7. **`backup()` already touches four sibling roots, not just `.claude/`** — `reconcile.py:274-287` copies `.claude/`, `.cursor/`, `.codex/`, `.agents/`, and `AGENTS.md`. Any "skip when no destructive op" logic must check reconcile decisions across the full blueprint, not just `.claude/`-prefixed files.

8. **Dogfood signal: this repo has 108 backup directories** — `du -sh .backup-* | wc -l` confirmed. Average ~3 MB each → ~325 MB of redundant snapshots in a single repo. This is hard evidence the current design pays a real cost; resist the temptation to dismiss it as "just disk".

## ❓ Open Questions

1. **Default policy for the new behaviour:** Should the "skip when KEEP-only" decision be hard-coded, or governed by a new `harness.yaml` key (`backup_policy: always | when_destructive | never`)? The latter is more flexible but adds config surface that needs documenting and gating in `/hm:configure`.

2. **Scope of the "conditional skip":** When reconcile reports REPLACE/MERGE_BLOCK for *some* files but KEEP for the rest, should backup copy the entire `.claude/` tree (current behaviour), only the affected files (Approach C), or affected files plus their containing subtree (e.g. all of `.claude/commands/`)?

3. **`.gitignore` wiring scope:** Add only `.backup-*/`, or also `.worktrees/` (currently added by worktree code path but not by `make`), `.hm-render-manifest.jsonl`, and `.claude/observability/orphans-*.jsonl`? Bundling them is cheap once we're touching the file; keeping the change minimal is also defensible.

4. **Retention defaults:** Last K snapshots (K=?) vs newer-than-N-days (N=?) vs both. Dogfood data suggests at least last-5 + newer-than-14d would have kept this repo under 5 backups instead of 108.

5. **`--no-backup` paired with dirty `.claude/` workspace:** Refuse, warn-and-continue, or accept silently? Refusing risks blocking power users; accepting risks data loss. Reasonable middle: warn and require `--force` to override.

6. **Receipt copy in `commands/make.md`:** When backup is skipped, what does the user see? Proposal: a single line like "no destructive ops detected — kept N user files in place, backup skipped (git is your recovery)". Needs locale-aware variants because slash-command prose is user-locale.

7. **Migration of existing `.backup-*/` directories:** Should `/hm:make` offer to prune pre-existing backups on first run after the new behaviour ships, or leave them for the user to clean up? Auto-pruning past backups feels intrusive; an opt-in "found 12 stale backups, prune them? [Yes/Show/No]" prompt feels more honest.

## 📚 Sources

- Internal: `src/harness_maker/cli.py:353-354` — unconditional `backup(target_dotclaude)` call site; gate is "directory exists AND non-empty".
- Internal: `src/harness_maker/reconcile.py:259-288` — `backup()` implementation; copies `.claude/`, `.cursor/`, `.codex/`, `.agents/`, `AGENTS.md` recursively to `.backup-<ISO>/`.
- Internal: `src/harness_maker/reconcile.py:84-231` — `reconcile()` decision matrix; KEEP / REPLACE / MERGE_BLOCK / BOTH per file. KEEP is the no-frontmatter default (line 168-176).
- Internal: `src/harness_maker/render.py:180-209` — `_merge_permissions()` (preserves user-added allow/deny/ask entries on re-render).
- Internal: `src/harness_maker/render.py:620-682` — `_preserve_yaml_user_keys()` (preserves arbitrary user-added top-level YAML keys).
- Internal: `src/harness_maker/render.py:799-804` — explicit acknowledgement that no gitignore template ships yet.
- Internal: `src/harness_maker/worktree.py:990-1025` — `_ensure_gitignore_entry()` precedent for safely writing the user's `.gitignore`.
- Internal: `commands/make.md:118, 199-202, 278-282` — current user-facing prose mentioning backup as a safety mechanism.
- Internal: `docs/ARCHITECTURE.md:130-139` — M2 reconciler design: backup-then-apply, ADD-only.
- Internal: `work-docs/RESEARCH-onboarding-ux-2026-05.md` — prior research; Pitfall #4 flagged backup-without-restore-clarity; recommended Approach A (receipt-first) overlaps with this doc's Approach C.
- Internal: `tests/unit/test_onboarding_ux_contract.py:29-48` — current UX-contract test that requires the `.backup-<timestamp>` string to appear in `commands/make.md` (any new behaviour must keep this test honest or update it).
- Memory: `[wiki:fresh-install-health-baseline] 2026-05-19` — `render.py` already had `_merge_permissions` + `_preserve_yaml_user_keys` + `content_hash` recompute, which together cover most additive-baseline cases without needing a flag. Same principle applies here: lean on existing preservation primitives before adding new safety machinery.

## 🔗 Related Internal Docs

- `[[RESEARCH-onboarding-ux-2026-05]]` — broader onboarding-UX research; this doc is a narrower follow-up on the backup-specific friction.
- `[[ARCHITECTURE]]` §M2 Reconciler — canonical description of the brownfield reconciliation contract.
- `[[block-merge-spec]]` — `@hm:user:*` block-marker semantics; the in-place preservation primitive that makes backup partially redundant.
