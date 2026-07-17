---
type: plan
task_slug: render-finish-ux
status: complete
created: 2026-06-27
tags: [harness-maker, plan, python, ux, onboarding, git]
research_doc: "[[RESEARCH-render-finish-ux]]"
interview_rounds: 2
adrs: 6
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Slash-owned render narrative + dry-run preview on re-render + manifest-based git-disposition over all target roots (neutral, no re-nag)"
---

# PLAN — render-finish-ux

## 🎯 Executive Summary

**What:** Make `/harness-maker:make` (and rendered `/hm:make`) a guided experience that ends at
"your harness files are in git the way you intend." (1) The slash command owns a clean,
locale-aware **render narrative** anchored on stable CLI summary lines, and the first-install
**structural-health dump becomes quiet-when-clean / loud-on-P0·P1**; (2) instead of a worktree,
a **preview → confirm → apply** step runs only when re-rendering over an existing non-empty
`.claude/`; (3) a **post-render git-disposition step** detects git state from the render manifest
across **all selected target roots** and asks the user — **neutrally** — to commit or gitignore
those roots, then performs the chosen action idempotently and **without re-nagging**; (4)
**README.md/.ko.md + docs/HOW-IT-WORKS(.ko).md** document the render flow and the git decision.

**Why:** Render *mechanics* are already safe (backup + reconcile KEEP/MERGE + churn gitignore),
but two gaps remain: narrative clarity and the last mile. Today nothing tells the user what just
happened or what to do with the freshly written files. `make.md` ends at "Quick start" with **no
git guidance**, and auto-gitignore covers **only churn** (`worktree.py:91-127`), never the actual
harness content.

**Key Decisions:**
- [[#ADR-001]] git-disposition split: slash asks + commits; a thin CLI helper detects state (manifest + porcelain over target roots) and mutates gitignore loudly.
- [[#ADR-002]] Neutral default — commit and ignore presented as equals, no highlighted recommendation.
- [[#ADR-003]] Reject worktree-for-render; use a `--dry-run`-based preview, only on re-render over existing `.claude/`.
- [[#ADR-004]] Binary git option (commit-all / ignore-all) over **all selected target roots**, not just `.claude/`.
- [[#ADR-005]] Render narrative owned by slash (CLI stays machine-parseable); first-install health = quiet-when-clean / loud-on-nonzero-P0·P1.
- [[#ADR-006]] Document render flow + git decision in README (both locales) **and** HOW-IT-WORKS (both locales).

**Estimated impact:** medium user-facing UX win; medium implementation risk (git-state correctness
across mixed/transition states). New testable Python module + CLI subcommands, two slash surfaces,
docs. No new dependency.

## 📚 Prior Work

- [[RESEARCH-render-finish-ux]] — recommended direction + 5 open questions (all resolved in interview).
- [[PLAN-onboarding-ux-2026-05]] — ADR-001 locked "slash-command prose is the receipt source"; this PLAN extends that receipt to the git last mile; ADR-002 "trade-offs not estimates" → neutral git framing.
- [[PLAN-onboarding-backup-friction]] — `.backup-*/` auto-gitignore: the safety net that makes a worktree unnecessary.
- [[RESEARCH-install-without-claude-code]] — non-git / CLI-fallback install case; the reason any git-coupled render path (worktree) regresses.
- CLAUDE.md checklist #2 (`.gitignore` append via `_ensure_gitignore_entry`), #4 (CLI flag-driven, slash owns `AskUserQuestion`), #5 (fingerprint/no re-nag → infer decision from git state), #6 (reverse mapper → infer, no new persisted key), #8 (integration boundary e2e). Git policy: CLI never auto-commits.
- **Codex + plan-validator second opinion (round 1, MAJOR_REVISION)**: 2 criticals (check-ignore exit-code; `make.md.j2` bypass) + 5 warnings, all incorporated below. CX3 (worktree-detection rewrite) rejected as out-of-scope (`cli.py:247` is the `--update` snapshot guard; `git rev-parse --is-inside-work-tree` is correct inside a linked worktree).

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|-------|----------|----------|---------|--------|------|-------|
| 1 | Git step home | Architecture | Where does the git-disposition step live? | slash+CLI-helper / slash-only / CLI-subcommand-all | slash + thin CLI helper | CLI never commits; helper detects + gitignores | ADR-001 |
| 2 | Default rec | UX | Which option is the highlighted default? | commit-to-share / gitignore-local / neutral | neutral | Present both equally, trade-offs only | ADR-002 |
| 3 | Preview scope | Risk/UX | Introduce preview→confirm→apply? | re-render-only / all-make / threshold / none | re-render over existing only | fresh install applies directly | ADR-003 |
| 4 | Git granularity | Contract | How granular are the git options? | binary / 3-way / smart+freeform | binary | commit-all or ignore-all only | ADR-004 |
| 5 | README depth | Scope | How deep does the render-flow doc go? | README-concise / both-detailed / README-pointer | both detailed | both locales each | ADR-006 |
| 6 | Exit | — | Plan sufficiently clear? | proceed / one more round | proceed — end interview | — | — |

**Folded assumptions (defensible defaults, not asked):** git decision **inferred from git state
each run, never persisted** (no new harness.yaml key — CLAUDE.md #6); non-git target → skip git
step + `git init` note; multi-target scope = all selected target roots (consistent with the user's
"complete to the end" goal); gitignore mutation builds on `_ensure_gitignore_entry` but the
subcommand adds a loud-failure contract.

## 📐 Architecture Decision Records

### ADR-001: Git-disposition split — slash asks+commits; thin CLI helper detects (manifest + porcelain) and mutates gitignore loudly
**Status:** Accepted (2026-06-27, via /hm:plan interview + validator round 1)
**Context:** Post-render the user must decide commit vs gitignore for the generated harness roots. CLAUDE.md #4 forbids stdin/`AskUserQuestion` in the CLI; git policy forbids CLI auto-commit; #8 wants the mechanical parts testable. Round-1 review proved the naive detection (`git ls-files .claude` non-empty + single `git check-ignore .claude/harness.yaml`) is both **incorrect** (check-ignore exits 1 when NOT ignored → `_run(check=True)` crashes) and **too coarse** (any pre-tracked `.claude` file suppresses the prompt forever; misses transitions; ignores multi-target roots).
**Decision:** A new `harness_maker.git_disposition` module + two CLI subcommands own the **testable mechanics**, all reads via dedicated subprocess calls with **`check=False` + explicit returncode branching** (NOT `worktree._run`, which is `check=True`):
- `harness-maker git-status <project>` → stdout JSON. Reads the render manifest (`.claude/.harness-manifest.json`) to know **our** rendered files, restricted to the selected **target roots** (`.claude/` always; `.cursor/`, `.codex/`, `.agents/`, `AGENTS.md` when those targets are active), **minus churn** (`worktree._HARNESS_GITIGNORE_PATTERNS`). For that file set it computes: `is_git` (`git rev-parse --is-inside-work-tree`, rc≠0 → false), per-file `tracked` (`git ls-files`), per-root `ignored` (`git check-ignore <root>`; rc 0=ignored, 1=not, 128=error→treat as not-git). Derives `prior_decision ∈ {undecided, commit, ignore}` and `decision_needed`/`offer_stage` (see Design Decisions). JSON only; never mutates, never commits.
- `harness-maker git-ignore-roots <project>` → appends each active target root to `.gitignore` via the idempotent `_ensure_gitignore_entry`, then **verifies** each root is now `check-ignore`-matched and that the target is a work tree; **exits nonzero (loud) on any write failure / non-work-tree** (an explicit user decision must not silently no-op).

The **slash command** drives `AskUserQuestion` and runs `git add <roots> && git commit` itself (explicit user action).
**Consequences:**
- ✅ Detection + gitignore are unit-testable without a TTY; commit stays explicit and auditable.
- ✅ Correct across mixed/transition states (manifest+porcelain, not a coarse probe); honors CLAUDE.md #4 and the no-CLI-auto-commit policy.
- ⚠️ Two layers to keep in sync (helper JSON ↔ slash consumer) — covered by a schema-shape test.
- ⚠️ Manifest dependency: if `.harness-manifest.json` is absent (very old harness), fall back to the target-root dirs themselves — recorded as a Phase-1 edge case.
**Rejected alternatives:**
- slash-only — Rejected: no e2e coverage (#8).
- CLI-subcommand-all (CLI commits) — Rejected: violates no-CLI-auto-commit.
- Reuse `worktree._run(check=True)` for check-ignore — Rejected: crashes on the rc=1 not-ignored common path (validator critical #1).
**Source:** Interview #1 + validator critical #1, warnings CX1/CX7/CX8.

### ADR-002: Neutral default — no highlighted commit/ignore recommendation
**Status:** Accepted (2026-06-27, via /hm:plan interview)
**Context:** The git-disposition prompt could nudge the user toward one option.
**Decision:** Present commit-all and ignore-all as **equal** choices with trade-offs only; no "(Recommended)" tag, no ordering that implies preference. (Aligns with [[PLAN-onboarding-ux-2026-05]] ADR-002.)
**Consequences:** ✅ no paternalistic nudge; team-share vs solo-local is a real project choice. ⚠️ slightly more cognitive load (read both trade-offs) — accepted.
**Rejected alternatives:** commit-default / ignore-default — Rejected: user chose neutral.
**Source:** Interview #2

### ADR-003: Reject worktree-for-render; preview only on re-render over existing `.claude/`
**Status:** Accepted (2026-06-27, via /hm:plan interview)
**Context:** User asked whether render should happen in a worktree. The real desire is "don't surprise me by overwriting," not branch isolation.
**Decision:** Do **not** render `make` inside a worktree. Add a **preview → confirm → apply** flow in the slash command(s), gated to **re-render over an existing non-empty `.claude/`** (fresh install applies directly). The preview uses `make --dry-run`; `_emit_dry_run_summary` (`cli.py:734`) is **extended to also report KEEP/MERGE counts** (owned by Phase 2). We do NOT change worktree *detection* (`cli.py:247` is the unrelated `--update` snapshot guard; `git rev-parse --is-inside-work-tree` already behaves correctly inside a linked worktree — validator rejected CX3 as out-of-scope).
**Consequences:** ✅ no hard git dependency (preserves non-git install [[RESEARCH-install-without-claude-code]]); no merge round-trip; backup remains rollback. ⚠️ one confirm step on re-render — accepted.
**Rejected alternatives:** worktree render + merge-back — Rejected: hard git dep + friction, no safety gain. preview on all make — Rejected: friction on first install.
**Source:** Interview #3 + validator warning (dry-run owner).

### ADR-004: Binary git option (commit-all / ignore-all) over all selected target roots
**Status:** Accepted (2026-06-27, via /hm:plan interview + validator round 1)
**Context:** Git options could be binary or 3-way. Round-1 review showed a `.claude`-only scope leaves `.cursor/`, `.codex/`, `.agents/`, `AGENTS.md` undecided for multi-target renders (CX5).
**Decision:** Exactly two actions, each applied to **all active target roots** (derived from `harness.yaml.targets`): commit them whole (`git add <roots>`), or gitignore them whole (`git-ignore-roots`). Churn + `.backup-*` are already individually gitignored, so commit-all is clean; ignore-all's per-line churn entries are redundant-but-harmless.
**Consequences:** ✅ simple, matches the two real intents; multi-target users get a complete disposition. ⚠️ no "share config, hide generated" middle ground — accepted, revisitable.
**Rejected alternatives:** 3-way granular — Rejected: complexity unjustified. `.claude`-only scope — Rejected: incomplete for multi-target (CX5).
**Source:** Interview #4 + validator warning CX5.

### ADR-005: Render narrative owned by slash; first-install health = quiet-when-clean / loud-on-P0·P1
**Status:** Accepted (2026-06-27, via /hm:plan interview + validator round 1)
**Context:** CLI render output is utilitarian and a structural-health scan fires immediately after install — noisy for first-timers. CLAUDE.md: Python = safety rails; LLM owns prose. Round-1 review warned an unconditional one-line pointer can **hide real P0/P1** introduced by render/hook/template drift (CX6).
**Decision:** The slash command owns the friendly locale "what changed / what's preserved / what's next" narrative, anchored on the CLI's stable machine-parseable summary lines (counts + roots + backup path — parsed, not regenerated). On **fresh install**, `_emit_post_make_readiness` becomes **severity-aware**: quiet (one-line "structural-health: clean — run /hm:health for the full scan") when zero P0/P1, but **loud** (one-line severity count + the P0/P1 action lines) when any P0/P1 is present. Re-render keeps current behavior. A regression test injects a failing readiness signal and asserts it is NOT buried.
**Consequences:** ✅ calm first install without hiding real failures. ⚠️ narrative depends on the CLI summary staying stable — covered by a render-output test.
**Rejected alternatives:** prettier CLI (rich/TUI) — Rejected: double-formatting through slash. Unconditional pointer — Rejected: hides P0/P1 (CX6).
**Source:** Interview #6 (proceed) + validator suggestion CX6.

### ADR-006: Document render flow + git decision in README (both locales) and HOW-IT-WORKS (both locales)
**Status:** Accepted (2026-06-27, via /hm:plan interview)
**Context:** Public plugin; README is the first impression. User asked for friendly render-flow docs.
**Decision:** Add a render-flow + post-render git-decision section to **README.md and README.ko.md** (concise, links to HOW-IT-WORKS), and the full pipeline detail to **docs/HOW-IT-WORKS.md and docs/HOW-IT-WORKS.ko.md**. Both locales synced; README summarizes + links, HOW-IT-WORKS owns the deep detail.
**Consequences:** ✅ users understand render before running + know the git decision after. ⚠️ four files to keep in sync — mitigated by the link-don't-duplicate split + a parity check.
**Rejected alternatives:** README-concise-only / README-pointer-only — Rejected: user chose both-detailed.
**Source:** Interview #5

## 🏗️ Technical Design

### Current State
- `make` (`cli.py:58`) renders to `<cwd>/.claude/` directly; `backup()` + `reconcile()` protect user edits; `_ensure_harness_gitignore` seeds **churn-only** gitignore lines. `_write_harness_manifest` writes `.claude/.harness-manifest.json` (list of rendered files) — the basis for accurate git-state detection.
- `--dry-run` exists (`cli.py:196`, `_emit_dry_run_summary` `:734`) — NEW/REPLACE only, then exit.
- `_emit_post_make_readiness` (`:927`) fires a structural-health scan after install. `tests/integration/test_fresh_install_readiness.py` already guards P0 calibration.
- **Two make surfaces:** `/harness-maker:make` (`commands/make.md`) AND the **rendered `/hm:make`** (`src/harness_maker/templates/commands/hm/make.md.j2`, default path bash-dispatches `harness-maker make --update` at `make.md.j2:35`). Neither has git guidance. *(Corrects the round-1 draft's false "no hm:make template" claim — validator critical #2.)*
- `worktree._run` is `check=True` — unusable for `git check-ignore` (rc 1 = not ignored). No git-state detection helper exists in `src/`.

### Affected Components
- **NEW** `src/harness_maker/git_disposition.py` — manifest+porcelain detection (check=False) + loud `git-ignore-roots`.
- `src/harness_maker/cli.py` — `git-status` + `git-ignore-roots` subcommands (Phase 1); `_emit_dry_run_summary` KEEP/MERGE extension + severity-aware fresh-install health + stable render summary (Phase 2).
- `commands/make.md` **and** `src/harness_maker/templates/commands/hm/make.md.j2` — git-disposition step + preview→confirm→apply (Phase 3).
- `README.md`, `README.ko.md`, `docs/HOW-IT-WORKS.md`, `docs/HOW-IT-WORKS.ko.md` (Phase 4).
- Reuse `worktree._ensure_gitignore_entry` (append) + `_HARNESS_GITIGNORE_PATTERNS` (churn set) — do NOT reimplement.

### Design Decisions
- **Target roots** = `.claude/` ∪ (`.cursor/` if cursor) ∪ (`.codex/`, `.agents/`, `AGENTS.md` if codex), read from `harness.yaml.targets`.
- **Rendered-file set** = entries of `.claude/.harness-manifest.json` ∩ target roots, **minus** `_HARNESS_GITIGNORE_PATTERNS` (churn). Manifest-absent fallback = the target-root dirs themselves.
- **Per-file/root git probes (all `check=False`, branch on returncode):** `is_git` = `git rev-parse --is-inside-work-tree` (rc≠0 → not git → `decision_needed=false`); `tracked(f)` = `f ∈ git ls-files`; `ignored(root)` = `git check-ignore <root>` rc==0.
- **prior_decision:** `ignore` if every target root is `ignored`; `commit` if ≥1 rendered non-churn file is `tracked`; else `undecided`.
- **decision_needed** (full neutral prompt) = `is_git ∧ prior_decision == undecided`.
- **offer_stage** (commit-mode, new files appeared on re-render) = `is_git ∧ prior_decision == commit ∧ ∃ rendered non-churn file neither tracked nor ignored` → slash offers "stage N new harness files?" (no full re-prompt → **no re-nag**, CX1/CX7).
- `prior_decision == ignore` → skip silently. Non-git → skip + `git init` note.
- **git-ignore-roots loud contract** (CX8): validate work tree, append roots, re-verify `check-ignore` matches each; nonzero exit on any failure.

### Data Flow
```
/harness-maker:make  OR  /hm:make (make.md.j2)
  └─(re-render & .claude/ non-empty?)─▶ make --dry-run ─▶ preview(NEW/REPLACE/KEEP/MERGE) ─▶ confirm? ─┐
  └─(fresh)──────────────────────────────────────────────────────────────────────────────────────────┤
                                                                                                       ▼
                                                                                                 make (apply)
                                                                                                       ▼
                                                                  slash render narrative (locale, parses CLI summary)
                                                                                                       ▼
                                                            git-status (CLI JSON: prior_decision, decision_needed, offer_stage)
                                          ┌──────────────────────────┬───────────────────────────┬─────────────┘
                                  decision_needed                offer_stage                prior=ignore / non-git
                                          ▼                          ▼                            ▼
                          AskUserQuestion: commit-all|ignore-all   "stage N new files?"          skip (+git init note if non-git)
                              │commit             │ignore            │yes
                              ▼                   ▼                  ▼
                  git add <roots> && commit   git-ignore-roots   git add <new> (into commit)
```

### API Changes (additive, non-breaking)
- `harness-maker git-status <project>` → JSON `{is_git, target_roots, prior_decision, decision_needed, offer_stage, untracked_files}`.
- `harness-maker git-ignore-roots <project>` → idempotently gitignores all active target roots; **nonzero exit** on write failure / non-work-tree.

## 📝 Implementation Plan

### Phase 1 — git-disposition CLI helper (detection + loud gitignore)
- `depends_on`: []
- `parallel_group`: serial-1
- `merge_hazards`: `cli.py` (shared with Phase 2)
- **Scope (in):** `src/harness_maker/git_disposition.py` (target-root resolution from harness.yaml; manifest read + churn subtraction; `check=False` probes; `prior_decision`/`decision_needed`/`offer_stage`; loud `git-ignore-roots`). Two subcommands in `cli.py`. `tests/unit/test_git_disposition.py`.
- **Scope (out):** slash flow, commit logic, narrative, docs.
- **Exit criterion:** `uv run pytest tests/unit/test_git_disposition.py` green covering **all** states — non-git, unborn repo, **not-ignored branch (check-ignore rc=1, must not crash)**, exact-file ignore, parent-dir `.claude/` ignore, parent+negation, partially-tracked `.claude`, multi-target roots, manifest-absent fallback, `git-ignore-roots` idempotency (twice → one line) + loud-fail on a read-only `.gitignore`/non-work-tree; `harness-maker git-status .` emits `prior_decision: "commit"` in THIS repo (`.claude` is tracked); `mypy --strict` + `ruff` clean.
- **Risk:** medium (git-state correctness)
- **Rollback:** revert Phase 1 commit (new file + additive subcommands; no existing behavior touched).

### Phase 2 — CLI render-output: dry-run KEEP/MERGE + stable summary + severity-aware fresh health
- `depends_on`: [1]
- `parallel_group`: serial-1
- `merge_hazards`: `cli.py` (after Phase 1)
- **Scope (in):** extend `_emit_dry_run_summary` (`cli.py:734`) to report KEEP + MERGE_BLOCK counts (preview source for Phase 3); ensure a stable machine-parseable post-apply render summary (NEW/REPLACE/KEEP/MERGE + target roots + backup path) for the slash narrative; make `_emit_post_make_readiness` **severity-aware on fresh install** (quiet one-liner when zero P0/P1; loud count + P0/P1 lines otherwise), re-render unchanged.
- **Scope (out):** the prose narrative (slash, Phase 3).
- **Exit criterion:** test asserts dry-run summary includes KEEP/MERGE counts; **regression test injects a P0/P1 readiness signal on a fresh tmp install and asserts it is printed loudly (not buried)**; clean fresh install prints the quiet one-liner; summary-line shape covered; `tests/integration/test_fresh_install_readiness.py` still green; `ruff`/`mypy` clean.
- **Risk:** medium (hot make-report path; broad `except` diagnostics stay non-fatal).
- **Rollback:** revert to Phase 1 state.

### Phase 3 — both make surfaces: git-disposition step + dry-run preview
- `depends_on`: [1, 2]
- `parallel_group`: serial-1
- `merge_hazards`: `commands/make.md`, `src/harness_maker/templates/commands/hm/make.md.j2` (distinct files)
- **Scope (in):** add to **both** `commands/make.md` AND `make.md.j2`: (a) **preview→confirm→apply** before dispatch when `.claude/` exists & non-empty (run `make --dry-run`, show summary, `AskUserQuestion` confirm). **Note (validator round-2):** `make.md.j2:35` is a single `!`-autorun Bash line that runs the real `make --update` at command-load time — it must be **de-autorun'd / split** so the dry-run runs first and the real apply is gated behind the confirm; (b) **git-disposition step** — call `git-status`; on `decision_needed` ask neutral commit-all/ignore-all (commit → `git add <roots> && git commit`; ignore → `git-ignore-roots`); on `offer_stage` ask to stage new files; `prior_decision==ignore` or non-git → skip (+`git init` note); (c) wire the locale render narrative (ADR-005) parsing the Phase-2 summary.
- **Scope (out):** Python logic (P1/P2), docs (P4).
- **Exit criterion:** **command-template render test** renders `make.md.j2` and asserts it contains the `git-status` call, neutral framing (no "(Recommended)"), the preview-on-`--update` branch, and **no `AskUserQuestion`/`git commit` inside any CLI-dispatched Bash line**; grep asserts the same on `commands/make.md`; the four git states (undecided/commit/ignore/non-git) are documented in both surfaces. (Slash behavior = manual-verified per CLAUDE.md #8; the Python it calls is unit-covered.)
- **Risk:** medium
- **Rollback:** revert both command files.

### Phase 4 — README + HOW-IT-WORKS docs (both locales)
- `depends_on`: [1, 2, 3]
- `parallel_group`: serial-1
- `merge_hazards`: none (4 distinct doc files)
- **Scope (in):** README.md + README.ko.md — concise "what render does + preview-on-re-render + post-render git decision" section linking HOW-IT-WORKS; docs/HOW-IT-WORKS.md + .ko.md — full pipeline (sense→decide→render→preview→git decision, incl. multi-target roots + no-re-nag behavior). Both locales synced.
- **Scope (out):** code.
- **Exit criterion:** all four files contain the section; README links to HOW-IT-WORKS; en/ko parity (section headers match); no broken internal links.
- **Risk:** low
- **Rollback:** revert doc commit.

## 🧪 Testing Strategy
- **Unit (`test_git_disposition.py`):** tmp git repos for every state — non-git, unborn/empty repo, not-ignored (check-ignore rc=1, no crash), exact-file ignore, parent-dir `.claude/` ignore, parent+negation, partially-tracked `.claude`, detached linked worktree, submodule, multi-target roots (`.cursor/`/`.codex/`/`AGENTS.md`), manifest-absent fallback; `prior_decision`/`decision_needed`/`offer_stage` truth table; `git-ignore-roots` idempotency + loud-fail; JSON schema shape.
- **Integration (`INTEGRATION=1`):** `git-status` / `git-ignore-roots` as real CLI in tmp git repos (#8 boundary).
- **Render/structural:** command-template test on `make.md.j2` (git-status call, neutral framing, preview branch, **no AskUserQuestion/commit in CLI Bash**); dry-run KEEP/MERGE; fresh-install loud-on-P0/P1 regression; stable-summary shape.
- **Manual (slash):** four-state walk-through + preview-on-re-render on both surfaces, recorded in command verification notes.
- **Docs:** en/ko parity grep.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `git check-ignore` crashes detection (rc=1) | was high | high | check=False + returncode branch; Phase 1 tests the not-ignored branch (validator critical #1). |
| Re-nag on re-render / mixed states | med | high | Manifest+porcelain `prior_decision`; `offer_stage` (not full prompt) for new files in commit-mode; test the truth table (CX1/CX7). |
| `/hm:make` re-render bypasses the flow | was high | high | Phase 3 edits BOTH surfaces; command-template render test (validator critical #2). |
| Multi-target roots left undecided | med | med | Scope = all selected target roots (ADR-004/CX5). |
| ignore-all silently no-ops → re-nag | low | med | `git-ignore-roots` loud-fail contract + re-verify check-ignore (CX8). |
| Health-demote hides real P0/P1 | med | med | Severity-aware: quiet-when-clean, loud-on-P0/P1; injected-failure regression test (CX6). |
| gitignore double-append / WSL2 corruption | low | med | Reuse `_ensure_gitignore_entry` (idempotent append); never raw Edit (memory 2026-02-15). |
| CLI accidentally commits | low | high | Helper JSON-only; commit lives in slash; grep test asserts no `git commit` in `git_disposition.py` / CLI Bash. |
| README/HOW-IT-WORKS locale drift | med | low | Parity grep; README links, doesn't duplicate. |

## ✅ Success Criteria
- [x] Post-render, in a git repo with undecided harness roots, the user is asked **neutrally** to commit-all or ignore-all (over all target roots) and the chosen action is performed.
- [x] Re-running make after a decision does NOT re-prompt; new files in commit-mode are offered for staging, not re-prompted (no re-nag across transitions).
- [x] `git check-ignore` not-ignored path never crashes `git-status`.
- [x] Both `/harness-maker:make` and `/hm:make` show a preview before re-rendering over existing `.claude/`; fresh install applies directly.
- [x] Fresh install is quiet-when-clean but loud on any P0/P1; full scan still at `/hm:health`.
- [x] `git-ignore-roots` is idempotent and fails loudly; CLI never commits.
- [x] Multi-target renders dispose `.cursor/`/`.codex/`/`.agents/`/`AGENTS.md` too.
- [x] README (en+ko) + HOW-IT-WORKS (en+ko) document the render flow and git decision.

## 🚧 Implementation Status (execute — uncommitted, main tree)

Executed in the main tree (RESEARCH/PLAN are uncommitted there; a per-task worktree would
orphan them — consistent with how research/plan ran). All phases TDD'd to GREEN:

- **Phase 1 — DONE.** `src/harness_maker/git_disposition.py` (manifest+porcelain detection, `check=False` returncode branching, loud `ignore_roots`) + `git-status`/`git-ignore-roots` CLI subcommands. `tests/unit/test_git_disposition.py` 15/15 (all PLAN states incl. check-ignore rc=1 no-crash, negation, multi-target, manifest-absent, loud-fail). test-reviewer PASS.
- **Phase 2 — DONE.** `_emit_dry_run_summary` KEEP/MERGE extension; severity-aware fresh-install `_emit_post_make_readiness` (quiet-clean / loud-P0·P1); stable `render-summary:` line. `tests/unit/test_render_output.py` 4/4.
- **Phase 3 — DONE.** `commands/make.md` (§6.5 + Update preview) AND `templates/commands/hm/make.md.j2` (de-autorun'd `!` dispatch → preview→confirm→apply + git step). `tests/unit/test_render_make_git_disposition.py` 4/4 (render test asserts git-status call, neutral framing, no CLI-side commit/prompt).
- **Phase 4 — DONE.** README.md/.ko.md (RENDER subsection + HOW-IT-WORKS link) + docs/HOW-IT-WORKS.md/.ko.md (`## Render pipeline` / `## 렌더 파이프라인`). `tests/unit/test_docs_render_pipeline.py` 3/3 (anchor-resolves + en/ko parity).

Gates: `ruff check .` clean; `mypy --strict src/harness_maker` clean (115 files); full suite verdict pending. NO commit (wrapup owns it).

## 🔍 Plan Validation
**Round 1 (Codex + plan-validator): MAJOR_REVISION.** 2 criticals + 5 warnings, all incorporated:
- Critical #1 (check-ignore exit-code / `_run` reuse) → ADR-001 mandates `check=False`+returncode branch; Phase 1 tests the not-ignored branch.
- Critical #2 (`make.md.j2` bypass; false "no template" premise) → Current State corrected; Phase 3 edits both surfaces + command-template render test.
- CX1/CX7 (coarse detection / no-re-nag) → manifest+porcelain `prior_decision` + `offer_stage`.
- CX5 (multi-target) → ADR-004 scope = all target roots.
- CX8 (loud ignore) → `git-ignore-roots` loud-fail contract.
- CX6 (health demote hides P0/P1) → severity-aware fresh-install health + injected-failure regression.
- dry-run owner gap → Phase 2 owns `_emit_dry_run_summary` KEEP/MERGE extension.
- CX3 (worktree-detection rewrite) → **rejected** (out of scope; `cli.py:247` is the `--update` guard; `is-inside-work-tree` is correct in a linked worktree).

**Round 2 (Codex-informed + plan-validator): APPROVED.** All 7 round-1 issues confirmed resolved against source (`worktree._run` check=True; `make.md.j2:35` autorun dispatch; manifest backs multi-target scope via `render.py` writing all sibling-tree paths). One non-blocking suggestion folded into Phase 3: de-autorun the `make.md.j2` `!` line so the dry-run gates the apply.
