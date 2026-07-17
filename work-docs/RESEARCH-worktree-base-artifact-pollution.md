---
type: research
task_slug: worktree-base-artifact-pollution
status: complete
created: 2026-05-28
tags: [harness-maker, research, worktree, git, stash, parallel-sessions, gitignore, observability]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: [[PLAN-worktree-cross-session-data-loss-defense]], [[PLAN-worktree-finalize-stash-isolation]], [[PLAN-worktree-stash-phase4]]
summary: "Root cause of stash warnings = harness self-pollutes base repo; fix is keep-base-clean (gitignore + filter alignment), not more guards."
---

# RESEARCH — Worktree parallel-execute: base-repo artifact pollution

## 🎯 Recommended Direction

**The 5-layer defense treats symptoms; the disease is that the harness pollutes its own base repo.** Every session writes churn files into the base working tree that git can see, so `git status` is never clean — which makes finalize stash on every run (stash queue → queue-guard block) and makes `worktree create` abort on a "dirty base" that the *user* never dirtied.

The single most damning fact: **the telemetry hook is registered `PostToolUse` (`templates/hooks/hooks.json.j2:18`) and writes `<base>/.claude/observability/metrics-{date}.jsonl` on every tool call (`telemetry.py:216-235`).** Within seconds of *any* session the base is "dirty." This is not a race or an edge case — it is guaranteed on every session.

**Recommended direction (informational — `plan` decides):** stop the self-pollution so the existing defense apparatus goes quiet, rather than adding a 6th layer. Concretely, **Approach A — "keep the base clean"**: ship/append a comprehensive `.gitignore` for harness churn + align the two mismatched dirt-filters + close the orphan-stash drain gap. When the base stays clean, `_stash_base_dirty` returns `None` (worktree.py:419-422) → no stash → no queue → no warnings, and `_has_user_dirty_state` (worktree.py:636) returns `False` → parallel `create` just works. The 5 layers remain as a safety net but stop firing in normal operation. Impact is overwhelmingly internal maintainer ergonomics ("마음놓고 병렬").

## 🔍 Refinement Decisions

- **Discovery lens:** Technical architecture / implementation + Risk/compliance (data-loss). Not a product-opportunity topic.
- **Method:** 4 parallel sub-agent audits (source writers, stage/command templates, skills, lifecycle/cleanup) + direct reads of `worktree.py`, the two prior PLANs, and the telemetry hook. All claims below are cited to `file:line`.

## 🛠️ Approaches Found

### The two-filter asymmetry (the core bug, shared by all approaches)

There are **two** "is this dirt mine?" predicates and they disagree:

| Predicate | Used at | Recognizes as harness-owned |
|---|---|---|
| `_is_harness_artifact` (worktree.py:375-399) | **finalize** (`_stash_base_dirty`) | ONLY `.worktrees/`, `.claude/.hm-loop-`, `.claude/.hm-finalize-stash-` |
| `_is_create_guard_harness_artifact` (worktree.py:618-633) | **create** (dirty-base guard) | the narrow set **+ the entire `.claude/` tree** |

Neither excludes `work-docs/`. The finalize filter additionally fails to exclude almost everything under `.claude/` that the harness writes. Only **4** patterns are ever gitignored (`.claude/.hm-loop-*`, `.claude/.hm-finalize-stash-*`, `.claude/.hm-session-uuid`, `.backup-*/` — worktree.py:55,579,690 + cli.py:363); **no `.gitignore` template ships** (render.py:1081-1086). So everything else is visible in `git status`.

**Confirmed self-pollution writers (base repo, not gitignored):**
- `.claude/observability/metrics-{date}.jsonl` — **every tool call** (telemetry.py:216; hooks.json.j2:18). Dominant offender.
- `.claude/observability/{review,verify}-{date}.jsonl`, `security/findings-*.jsonl`, `dashboard.md`, `adaptive/overrides.jsonl`+`last-audit.txt`, `health/decisions.jsonl`, `cg-marks-*.jsonl`, `docs_index.yaml`, `orphans-*.jsonl` — per review/verify/health/audit/make (review_telemetry.py:62, security_scanner.py:68, observability/dashboard.py, personalization_audit.py:556, common_ground.py:246, refdocs_index.py:81, reconcile.py:564).
- `.claude/memory/{semantic,episodic,profile}/*` (+`.lock`) — wrapup/memory writes (memory/*.py).
- `.claude/loop-specs/{slug}.yaml` — `/hm:loop` (loop.md.j2:404).
- **`work-docs/loop-context/{slug}.yaml`** — autoloop driver (autoloop_driver.py:305; loop.md.j2:364), written *before* the worktree exists.
- **`work-docs/RESEARCH-{slug}.md`, `work-docs/SPEC-{slug}.md(+.machine.yaml)`, `work-docs/p5-batch-state.yaml`** — research/spec/loop stages run in the BASE repo and are **never `git add`-ed by wrapup** (wrapup.md.j2:236 stages only `.claude/memory/ + PLAN + REVIEW`).

The `work-docs/*` and `loop-context/*` writers are the worst because they are outside `.claude/`, so they trip BOTH guards (block `create` directly, not just finalize). The `.claude/observability/*` writers slip past `create` but each one triggers a finalize stash whose accumulation then re-blocks `create` via the queue-guard.

| Field | Approach A — Keep base clean | Approach B — Relocate writes to worktree/scratch | Approach C — Finalize w/o touching base tree |
|---|---|---|---|
| Approach | gitignore harness churn + align both filters + auto-drain orphan stashes | route all churn (telemetry, observability, receipts) into the worktree or a clean-by-construction scratch path | replace `git merge --squash` in base (merge()@1136) with `merge-tree --write-tree` + `commit-tree` + ref update (git 2.39 present) |
| Assumption | git-invisible == not dirt; deliverables (PLAN/REVIEW) still committed | churn doesn't need to live in the base tree | base branch ref can advance without updating base's checked-out tree |
| Evidence | telemetry.py:216, the 4-pattern gitignore gap, dual-filter asymmetry | telemetry `cwd` is base even mid-execute; observability is cross-session-aggregated | `git merge-tree --write-tree` works on 2.39.5; stash exists *only* to protect base index during squash (PLAN-finalize-stash-isolation §Exec) |
| Trade-off | must re-render/migrate existing harnesses; must surgically separate churn from human deliverables (RESEARCH/SPEC) | bigger surgery across telemetry + observability + templates; cross-session metric aggregation harder | base is checked out on `main`; advancing the ref leaves new files looking "deleted" in base unless the tree is also updated — the very thing stash avoids |
| Compatibility | additive; 5 layers stay as net | medium churn to hook/observability layer | high; reworks the merge core + interacts with merge-fence |
| Risk | low | medium | medium-high (blocked by "base checked out on target branch") |

**Why A over B/C:** A removes the *trigger* (`git status` is clean → stash never fires, guards never trip) with the least surface and keeps the safety net intact. C is architecturally appealing (no stash ever) but the "base repo is checked out on `main`" reality means advancing the ref still needs the working tree updated — it does not actually eliminate the contention without changing where the user works. B is the fallback if gitignore is judged insufficient (it does not help users who have *committed* `.claude/` to their repo — a documented real case in CLAUDE.md; for them only filter-alignment helps, which is why A bundles both).

## ⚠️ Pitfalls

- **gitignore is not enough alone.** Users who committed `.claude/` to their repo still get `M .claude/observability/...` modifications (tracked files), which gitignore won't hide. Filter-alignment (broaden `_is_harness_artifact`) is required as defense-in-depth — but broadening to *all* `.claude/` would defeat the intentional design at worktree.py:609-617 that preserves genuine user `.claude/` edits during the stash. Scope the broadening to artifact subdirs only (`observability/`, `.hm-iter-receipts/`, `.hm-*`), not the whole tree.
- **Don't gitignore the deliverables.** `work-docs/PLAN-*.md`, `work-docs/REVIEW-*.md` and committed `.claude/memory/{wiki,failures}` are *meant* to land in git (wrapup.md.j2:236). RESEARCH/SPEC currently linger uncommitted — fixing that is a separate decision (commit them vs ignore them), not "ignore everything under work-docs/."
- **No automated drain for stuck stashes** (lifecycle audit). On `post-commit-pop` conflict (worktree.py:2197), killed-before-wrapup, cross-session UUID mismatch (worktree.py:2173), or schema-invalid/legacy refs (worktree.py:1376), the ref + stash are preserved and **only manual `git stash drop` removes them**. `prune_stale` runs from exactly one place — `_cli_create` (worktree.py:1533) — and only drains a ref when its content is already in HEAD. So orphans accumulate and permanently block `create` until hand-cleaned. Matches the memory note "orphan stash registrations indrainable by automation."
- **CLAUDE.md is stale on this exact topic.** It claims a "weekly cleanup hook (`/hm:health` Step 2) that cleans 24h+ stale worktrees" — **no such code exists**; `health.md.j2` has zero prune/stale references. It says "3 GITIGNORE_PATTERN constants" — there are **4**. Any plan should correct these so the next reader isn't misled.
- **Self-irony:** this very RESEARCH doc, written to `work-docs/`, dirties the base — demonstrating pitfall #2 live.

## ❓ Open Questions

1. **RESEARCH/SPEC handling:** should wrapup `git add` them (treat as committed deliverables), or should they be gitignored as scratch? They currently linger and block `create`. (Binds the work-docs gitignore scope.)
2. **gitignore vs filter-alignment vs both:** ship a `.gitignore` template, broaden `_is_harness_artifact`, or both? (Recommendation: both — but `plan` locks it.)
3. **Migration for existing harnesses:** new `.gitignore` lines only help re-rendered repos. Use `_ensure_gitignore_entry` append-on-next-`create`, or a one-shot `/hm:make` migration, or `/hm:health` repair?
4. **Auto-drain trigger:** where should the orphan-stash/`prune_stale` drain run beyond `_cli_create` — session-start hook, `/hm:health`, or wrapup tail? And what consent model (the ADR-008 "never drop without `git stash show -p`" contract must hold)?
5. **Should telemetry/observability write to the base repo at all?** Or to a HOME-cache / gitignored-by-construction path (cf. verification_cache.py already uses `~/.cache/harness-maker/`)? This is the Approach-B seed; decide if it's in scope or deferred.
6. **Keep the 5 layers as-is once base stays clean?** They become near-dormant; confirm we keep them as a net vs. simplify.

## 📚 Sources

- (internal only — no external libraries fetched; topic is codebase-internal)
- git 2.39.5 confirmed locally (`git --version`) → `git merge-tree --write-tree` available for Approach C.

## 🔗 Related Internal Docs

- [[PLAN-worktree-cross-session-data-loss-defense]] — the 5-layer defense (queue-guard, dirty-base-guard, session-UUID, merge-fence, scope-guard).
- [[PLAN-worktree-finalize-stash-isolation]] — why the base-side stash exists (squash runs in base index).
- [[PLAN-worktree-stash-phase4]] — prior stash-handling iteration.
- [[REVIEW-worktree-cross-session-data-loss-defense-2026-05-23]] — review of the defense.
- memory `[wiki:pattern] cross-session-worktree-defense-5-layer`, `[wiki:gotcha] orphan-stash-registration-drain-manual`, `[fail:design] worktree-finalize-pulls-orphan-wip-into-main`.
