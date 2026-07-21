---
type: research
task_slug: latest-render-state-review
status: complete
created: 2026-07-18
tags: [harness-maker, research, release-readiness, render, autopilot, versioning]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[REVIEW-autopilot-guard-interactive-scope-2026-07-18]]", "[[PLAN-permission-deny-and-hooks-wiring]]"]
summary: "0.42.0 is premature — [Unreleased] is empty and 0.41.0 render is clean/committed; only open item is self-dogfooding guard_when"
---

# RESEARCH — Latest version render state review (is 0.42.0 warranted?)

## 🎯 Recommended Direction

**Do not cut 0.42.0 yet.** The 0.41.0 render is fully consistent and committed —
all five version files agree, the working tree is clean, `git-status` reports the
rendered roots as already-committed with zero untracked files, and `[Unreleased]`
in `CHANGELOG.md` is **empty**. A 0.42.0 tag right now would ship nothing.

The single actionable finding is **self-dogfooding**: the maintainer's own
`.claude/harness.yaml` runs `autopilot_persistent: true` + `guard_when: "always"`
— the exact "pure friction" combination that 0.41.0's headline feature
(`guard_when: pipeline_only`) was built to relieve. Adopting `pipeline_only` in
this repo's own harness is the natural next change, and would be the first real
`[Unreleased]` entry toward a 0.42.0.

## 🔍 Refinement Decisions

- **Discovery lens:** Technical architecture / implementation + Risk/compliance.
  This is a concrete state-review of the maintainer's own rendered output, not a
  broad product-opportunity / roadmap question, so the user-workflow product lens
  and its coverage guard do not apply.
- `--deep` not set → Phase 0 / Phase 0.5 interview skipped.

## 🛠️ Approaches Found

### Approach A — Hold at 0.41.0, no release (recommended)

| Field | Content |
|-------|---------|
| Approach | Keep current tag; do not bump to 0.42.0 |
| Assumption | A release must carry user-visible `[Unreleased]` content |
| Evidence | `CHANGELOG.md` `[Unreleased]` section is empty; only commit past `v0.41.0` tag is `ccb5f68a chore: re-render harness to harness-maker 0.41.0` (a chore, not a feature) |
| Trade-off | None — avoids an empty/no-op release that would falsely signal "already at latest" to `/plugin update` across 3 marketplaces |
| Compatibility | Full — matches the release procedure in CLAUDE.md ("5-file sync + CHANGELOG entry" precedes a tag) |
| Risk | low |

### Approach B — Dogfood 0.41.0: flip `guard_when: pipeline_only`, then release 0.42.0

| Field | Content |
|-------|---------|
| Approach | Change this repo's `.claude/harness.yaml` `autonomy.guard_when` from `always` → `pipeline_only`, re-render, add a CHANGELOG entry, release as 0.42.0 |
| Assumption | The maintainer wants the interactive-friction relief that persistent-autopilot users get |
| Evidence | 0.41.0 CHANGELOG explicitly frames `autopilot_persistent: true` + `always` as "pure friction … blocks never-auto ops + nags on Stop even in plain interactive chats" — which is this repo's live config (`harness.yaml:174-175`) |
| Trade-off | `pipeline_only` only stands down in **non-pipeline** interactive sessions; a guard-active pipeline stage (like this `/hm:research`) still blocks `.claude`-touching writes by design. So it does not remove all friction, only the plain-chat class. |
| Compatibility | Config + re-render only, no code change; `_guard_when` fail-safes a typo back to `always` |
| Risk | low |

### Approach C — Loosen the read-only allowlist (broaden `_SURFACE_READ_ONLY`)

| Field | Content |
|-------|---------|
| Approach | Add `ls`/`find`/`stat`/`wc` (and a read-only `sed -n` / `rg`) to `autopilot_guard._SURFACE_READ_ONLY` so read-only inspection of `.claude/` is not blocked under active autopilot |
| Assumption | Read-only `ls .claude/` blocking is over-restrictive friction rather than intended block-bias |
| Evidence | Observed live this session: `ls .claude/`, `find .claude`, `sed -n … .claude/harness.yaml` were all blocked as `permission-surface-write`; only `{cat, head, tail, grep, jq, git diff, git log}` are allowlisted (`autopilot_guard.py:84-85`) |
| Trade-off | Each added command widens the attack surface the guard docstring deliberately keeps small; `ls`/`find`/`wc` are genuinely write-incapable, but `sed`/`rg` have write-capable flags (`sed -i`, none for `rg`) and would need careful flag-gating. **Not release-blocking; a separate design task.** |
| Compatibility | Code change to the guard + new adversarial tests |
| Risk | medium (touches a security boundary that was hardened over 5 adversarial rounds in 0.40.2) |

## ⚠️ Pitfalls

- **Empty release is worse than no release.** Bumping the 5 version files without
  `[Unreleased]` content makes all three marketplaces report "already at latest"
  against a version with nothing new — the exact class of confusion CLAUDE.md's
  versioning section warns about (0.4.9 precedent). Only tag when there is a
  CHANGELOG entry to justify it.
- **`git_status` "commit" ≠ "up to date with templates".** `cli git-status`
  reports the git *disposition* (committed, no untracked), not render idempotence.
  The strong evidence for zero render drift is that HEAD is itself the
  `re-render to 0.41.0` commit **and** the tree is clean. A definitive re-render
  check (`make --update`) would mutate `.claude/` and is itself blocked under
  active autopilot, so it was not run — the clean-tree-after-re-render invariant
  stands in for it.
- **`pipeline_only` will not silence the guard during pipeline stages.** If the
  goal is "stop the guard blocking my `ls .claude/` right now," `pipeline_only`
  does not deliver it inside a `/hm:research`/`/hm:execute` stage (a pipeline is
  in flight). That is Approach C's territory, not Approach B's.
- **Release-time CHANGELOG conflict.** Per
  `[wiki:worktree-finalize-conflicts-with-parallel-main-edits]`, a squash-land
  while `[Unreleased]` is being edited surfaces CHANGELOG conflicts on files the
  worktree never touched — relevant if 0.42.0 work lands via a task worktree.

## ❓ Open Questions

1. **Intent of this review** — pre-release readiness gate (answer: not ready,
   empty changelog), or "why is the guard blocking my `.claude/` reads?" (answer:
   Approach C — intended block-bias, narrow allowlist). Which does the user want
   `/hm:plan` to act on?
2. **Adopt `guard_when: pipeline_only` in this repo?** (Approach B) — yes/no is a
   one-line config decision with a re-render.
3. **Broaden the read-only allowlist?** (Approach C) — is the `ls`/`find` block a
   bug to fix or accepted safety cost? This is the only item that would justify
   code + a 0.42.0 feature entry.

## 📚 Sources

- Internal only (no external fetch needed):
  - `.claude/harness.yaml:168-175` — `autonomy` block (`autopilot_persistent: true`, `guard_when: "always"`).
  - `src/harness_maker/hooks/autopilot_guard.py:84-85, 549-594` — read-only allowlist + `_surface_mention_backstop`.
  - `CHANGELOG.md` — empty `[Unreleased]`; 0.41.0 / 0.40.2 entries.
  - `python -m harness_maker.cli git-status` — `prior_decision: commit`, `decision_needed: false`, `untracked_files: []`.
  - `git log v0.41.0..HEAD` — single chore re-render commit.

## 🔗 Related Internal Docs

- [[REVIEW-autopilot-guard-interactive-scope-2026-07-18]]
- [[PLAN-permission-deny-and-hooks-wiring]]
- `[wiki:fresh-install-health-baseline]` — render migration semantics (`_merge_permissions`, `_preserve_yaml_user_keys`, content_hash recompute).
- `[wiki:model-routing-multi-ide]` — per-IDE (Claude/Cursor/Codex) render pinning.
- `[wiki:worktree-finalize-conflicts-with-parallel-main-edits]` — release-time CHANGELOG conflict pattern.
