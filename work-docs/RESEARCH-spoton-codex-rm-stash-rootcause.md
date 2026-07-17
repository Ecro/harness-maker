---
type: research
task_slug: spoton-codex-rm-stash-rootcause
status: complete
created: 2026-06-02
tags: [harness-maker, research, permissions, worktree, codex, settings-merge]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: []
summary: "3 spoton symptoms = 1 live template bug (tools-vs-perms) + 2 upgrade-can't-undo cases (deny union-merge, observability tracked)"
---

# RESEARCH — spoton: codex-skip / rm-denied / recurring-stash root cause

## 🎯 Recommended Direction

The three symptoms in `~/spoton` are **not one bug**. They split cleanly:

- **Issue 1 (codex second opinion skipped — "validator env had no Bash")** = a **live harness-maker template bug** affecting *every* 0.28.4 install with `codex_second_opinion` enabled. The codex permission partial adds `Bash(codex exec:*)` to `permissions.allow` but **never adds `Bash` to the agent's `tools:` frontmatter line** — and in Claude Code the `tools:` field is the hard gate on tool availability. No Bash tool → `codex exec` cannot run → skip → warn-and-proceed. **Fix in harness-maker template, then re-render.**

- **Issue 2 (rm permission denied)** = **upgrade-can't-undo**. spoton was scaffolded at harness-maker **0.23.2** (commit `1a16a6c`), when the main-session `settings.json` shipped a deny baseline including `Bash(rm:*)`. The 2026-05-31 "deny default OFF" policy only changes *fresh* renders; `render._merge_permissions` **unions** deny lists across re-renders, so the stale `Bash(rm:*)` survives forever. **Fix = manual one-shot edit of spoton's `settings.json` (or harness-maker gains a deny-reconciliation path).**

- **Issue 3 (recurring worktree stash)** = **upgrade-can't-undo**. `.claude/observability/` was **committed** at 0.23.2, *before* a later version added it to `.gitignore`. gitignore cannot untrack already-committed files, so every run dirties tracked observability files; the finalize stash sweeps them (the artifact filter only suppresses the *trigger*, not what `git stash push -u` captures). A stale untracked `work-docs/RESEARCH-*.md` deliverable supplies the trigger; an **orphan `.hm-loop-execute-*` marker** (worktree already gone) is collateral. **Fix = `git rm -r --cached .claude/observability …` + commit in spoton; delete the orphan marker.**

Common thread for #2 and #3: **harness-maker's upgrade path deliberately never auto-rewrites user-owned committed state** (git policy + preserve-user-content policy). So policy changes that postdate an install do not retroactively clean an old project. The binding trade-off is *safety/preservation vs. self-healing upgrades*.

## 🔍 Refinement Decisions

- Discovery lens: **Risk / permission / config** (primary) + **Technical architecture / implementation**. `--deep` not set; dived directly because the topic was concrete (three reproducible symptoms with a known target repo).
- Investigation was empirical: compared spoton's *rendered* `.claude/` output and live git state against harness-maker's *source* templates and `render.py` / `worktree.py` logic.

## 🛠️ Approaches Found

### Issue 1 — codex agent has the permission but not the tool

| Field | Content |
|-------|---------|
| Approach | Add `Bash` (or scoped `Bash(codex exec:*)`) to the `tools:` frontmatter of the 3 codex agents when `codex_second_opinion` is enabled |
| Assumption | Claude Code's subagent `tools:` field is the hard allowlist; `permissions.allow` is a *secondary* filter that cannot grant a tool the agent doesn't have |
| Evidence | `templates/agents/{plan-validator,code-reviewer,consensus-arbiter}.md.j2` line 5 = `tools: Read, Grep, Glob`. `_partials/codex_permission_line.md.j2` injects `- "Bash(codex exec:*)"` into `permissions.allow` only. spoton's rendered `plan-validator.md`: `tools: Read, Grep, Glob` + `permissions.allow: … Bash(codex exec:*)`. All 3 spoton codex agents show the same contradiction. |
| Trade-off | Granting Bash widens the reviewer's tool surface. Mitigate by relying on `permissions.allow`/`deny` to scope Bash to `codex exec:*` only (deny already blocks python/node/sh/bash/rm/curl). |
| Compatibility | Matches how `security-auditor.md.j2` (`tools: …, Bash`) and `trajectory-monitor.md.j2` (`tools: Read, Grep, Bash`) already work — they CAN run Bash. The codex agents are the outliers. |
| Risk | low (fix is additive + conditional on `codex_second_opinion.enabled`) |

Note: spoton's `code-reviewer.md` is **user-customized** (no provenance frontmatter — Zephyr/Flutter domain rewrite). Re-rendering harness-maker will NOT overwrite it; the user must add `Bash` to its `tools:` line by hand (or the template fix only helps `plan-validator` + `consensus-arbiter`).

### Issue 2 — deny union-merge cements stale baseline

| Field | Content |
|-------|---------|
| Approach A | Manual: edit spoton `.claude/settings.json` → remove `Bash(rm:*)` (and the relic `Bash(curl:*)`) from `permissions.deny`. Immediate, surgical. |
| Approach B | harness-maker: teach `_merge_permissions` to distinguish "stale template-shipped deny we want to retire" from "user-added guardrail". E.g. track a set of *retired* baseline entries and subtract them, or fingerprint template-origin entries. |
| Assumption | The user genuinely wants `rm` allowed in the main session (consistent with the 2026-05-31 solo-friendly policy and the memory of user feedback). |
| Evidence | `render._merge_permissions` docstring + code: `for item in (*new_list, *existing_list)` → union; `_SETTINGS_KEYS_OWNED_BY_HARNESS` includes `permissions`. `Production.json.j2` line 4 renders `"deny": []` when `deny_dangerous` falsy. spoton harness.yaml has **no** `permissions:` block (→ default `deny_dangerous=False`). spoton settings.json deny = 5 entries incl. `Bash(curl:*)` which matches *no* current branch → proven relic. Origin commit `1a16a6c` (0.23.2). |
| Trade-off | A is fast but doesn't help other old installs / can re-creep if a future template re-ships the entry. B is the durable fix but risks dropping a deny the user actually wanted. |
| Compatibility | A is pure user action. B touches a function with an explicit "preserve user denies" contract + byte-identical regression guard — needs care. |
| Risk | A: low. B: medium (security-posture-sensitive). |

### Issue 3 — observability tracked-then-gitignored + finalize stash sweep

| Field | Content |
|-------|---------|
| Approach A | Manual one-shot (already documented in CLAUDE.md "accepted limitation"): `cd ~/spoton && git rm -r --cached .claude/observability .claude/.hm-iter-receipts .claude/.hm-render-manifest.jsonl && git commit`. Removes the tracked dirt at the source. |
| Approach B | Delete the orphan `~/spoton/.claude/.hm-loop-execute-b50f000b4e93-20260601T1633Z` marker (its `.worktrees/execute-…` target no longer exists). |
| Approach C | harness-maker: have `_stash_base_dirty` (or a pre-finalize step) restrict `git stash push` to the *user_lines* paths via pathspec, so harness-artifact tracked files are never swept into the stash even when a real trigger exists. |
| Assumption | The recurring stash is driven by tracked observability churn flowing through both the base stash and the worktree squash-merge, plus a non-artifact trigger (the stray `work-docs/RESEARCH-product-physical-size.md`). |
| Evidence | spoton `.gitignore` line 38 ignores `.claude/observability/` **and** `git ls-files` shows 4 tracked observability files (committed `1a16a6c`, 0.23.2). `worktree._is_harness_artifact` matches them (churn dir prefix) → excluded from the *trigger* only. `_stash_base_dirty`: `if not user_lines: return None` else `git stash push -u` (sweeps everything). Live spoton status: `M .claude/observability/adaptive/overrides.jsonl` (staged) + `?? work-docs/RESEARCH-product-physical-size.md` (non-artifact → trigger). `.worktrees/` empty but loop marker present = orphan. |
| Trade-off | A/B are surgical and match documented policy (harness never auto-`git rm --cached`). C is the durable fix but changes well-tested finalize semantics (pathspec stash interacts with `-u` untracked handling and the merge-fence/pop logic). |
| Compatibility | A/B = user actions, zero harness change. C = touches the 5-layer worktree defense — high blast radius, needs the full review gate. |
| Risk | A/B: low. C: medium-high. |

## ⚠️ Pitfalls

- **`permissions.allow` is a trap for tool availability.** Adding `Bash(codex exec:*)` to `permissions.allow` looks sufficient but is inert if `tools:` omits Bash. Any future "let agent X run command Y" change must touch **both** `tools:` and `permissions`. (Issue 1 is exactly this miss.)
- **Re-rendering does NOT fix Issues 2 & 3.** A user who runs `/harness-maker:make` again will see no change: the deny union-merge re-preserves `Bash(rm:*)`, and gitignore still can't untrack committed observability. Recommending "just re-render" would be wrong.
- **Re-rendering does NOT fix user-customized agents.** spoton's `code-reviewer.md` has no provenance → reconcile leaves it untouched. The Issue 1 template fix reaches `plan-validator`/`consensus-arbiter` only; `code-reviewer` needs a manual `tools:` edit.
- **Don't `git stash drop` the finalize stash blind.** CLAUDE.md ADR-008 contract: always `git stash show -p <ref>` before any drop. Relevant if a pop conflict is already queued.
- **The orphan loop marker can wedge the loop gate.** `prune_stale` only runs at the *next* `worktree create`; until then a stale `.hm-loop-execute-*` pointing at a deleted worktree may make the gate think a loop is live.
- **`deny_dangerous` default-OFF only governs fresh state.** The policy note in CLAUDE.md is accurate for new installs but silent on the union-merge cementing effect for upgrades — an easy false assumption.

## ❓ Open Questions

1. **Issue 1 fix scope:** add bare `Bash` to `tools:` for the codex agents, or a scoped form? Claude Code `tools:` does not accept argument scoping (`Bash(codex exec:*)` is a *permissions* concept, not a *tools* concept) — so `tools:` likely must list plain `Bash`, with scoping enforced via `permissions.allow`/`deny`. Needs confirmation against current Claude Code subagent spec. **(This is validator Q2 territory — the one open decision.)**
2. **Issue 1 conditionality:** should `Bash` appear in `tools:` only when `codex_second_opinion.enabled and name in agents` (mirroring the permission partial), or unconditionally? Conditional keeps the no-codex install's reviewers Bash-free (tighter), but adds a second `{% if %}` site that must stay in lockstep with the permission partial.
3. **Issue 2 durability:** is a manual settings.json edit acceptable, or does harness-maker need a "retire deny entry" mechanism (Approach B) so other/old projects self-heal? Decision is security-posture-sensitive.
4. **Issue 3 durability:** ship the pathspec-scoped finalize stash (Approach C), or treat it as a documented manual-cleanup limitation forever? C changes the most safety-critical subsystem.
5. **Should `/hm:health` surface these?** A health check could flag (a) codex agent with `Bash(codex exec)` perm but no Bash tool, (b) tracked-yet-gitignored `.claude/observability/`, (c) settings.json deny ≠ template branch, (d) orphan loop markers. Cheap, high-signal — but scope creep for this task.

## 📚 Sources

- All evidence is internal (code + live repo state); no external citations.
- harness-maker source: `src/harness_maker/templates/agents/plan-validator.md.j2:5`, `.../code-reviewer.md.j2:5`, `.../consensus-arbiter.md.j2:5`, `.../_partials/codex_permission_line.md.j2`, `src/harness_maker/templates/settings/Production.json.j2:4`, `src/harness_maker/render.py:118-260` (`_render_settings_json`, `_merge_permissions`, `_shallow_merge_existing_json`, `_SETTINGS_KEYS_OWNED_BY_HARNESS`, `_PERMISSIONS_LIST_KEYS`), `src/harness_maker/worktree.py:76` (`_HARNESS_CHURN_PREFIXES`), `:450-480` (`_is_harness_artifact`), `:508-548` (`_stash_base_dirty`).
- spoton live state: `.claude/harness.yaml` (v0.28.4, targets `[claude-code, codex]`, `codex_second_opinion.enabled: true`, no `permissions:` block), `.claude/settings.json` (deny = `[Bash(rm:*), Bash(curl * | sh), Write(/etc/**), Write(~/.ssh/**), Bash(curl:*)]`), `.claude/agents/{code-reviewer,plan-validator,consensus-arbiter}.md`, `git ls-files .claude/observability/` (4 tracked), `.gitignore:38`, orphan `.claude/.hm-loop-execute-b50f000b4e93-20260601T1633Z`, scaffolding commit `1a16a6c` (0.23.2).

## 🔗 Related Internal Docs

- `CLAUDE.md` §보안/권한 (deny default-OFF, 2026-05-31), §Multi-session worktree (5-layer defense + accepted limitation), §Keep-base-clean (`_HARNESS_CHURN_PREFIXES`).
- `[[project_review_grade_gate]]`, `[[feedback_stash_pop_conflict_pattern]]` (memory).
- PLAN-codex-second-llm-integration ADR-007 (codex permission line), PLAN-worktree-base-artifact-pollution ADR-002/005 (gitignore + ref drain), PLAN-worktree-finalize-stash-isolation ADR-001 (base stash envelope).
