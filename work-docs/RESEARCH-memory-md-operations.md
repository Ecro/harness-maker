---
type: research
task_slug: memory-md-operations
status: complete
created: 2026-05-19
tags: [harness-maker, research, memory, lifecycle, retrieval]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[CLAUDE.md]]"
  - "[[templates/stages/wrapup.md.j2]]"
  - "[[templates/memory/wiki.en.md.j2]]"
  - "[[templates/memory/failures.en.md.j2]]"
  - "[[.claude/memory/pending-proposals.md]]"
summary: "memory/{wiki,failures}.md grow append-only with no promotion / archive / staleness guards — propose 3-layer curation (format gate + lifecycle pass + retrieval rewrite)"
---

# RESEARCH — `memory/{wiki,failures}.md` operations

## 🎯 Recommended Direction

Adopt a **three-layer curation model**: (1) tighten the per-entry **format contract** so future readers can decode an entry without grepping the codebase, (2) introduce a periodic **lifecycle pass** (`/hm:memory-curate` or a new `/hm:health` step) that audits staleness / supersession / promotion candidates, (3) replace the current "first-60-lines + grep" loader with an **LLM-judgment relevance filter** (we already ship the pattern in `relevance-filter` skill for the anti-rot crawler). The single highest-leverage change is (3) — recent entries currently never load into the research stage because they sit at the bottom of files that have outgrown the 60-line skim budget.

## 🔍 Refinement Decisions

- Discovery lens: **Technical architecture / implementation** + **User-workflow / product opportunity**. The question is half "is the format good" (architecture) and half "what does the maintainer experience look like 6 months from now" (workflow).
- No `--deep` interview — the user's prompt already names the three sub-questions (word-level decodability, accumulation behaviour, auto-promotion). Phase 0 would be noise.

## 🛠️ Approaches Found

### Approach A — Format contract hardening (mechanical, cheap)

| Field | Content |
|---|---|
| Approach | Tighten entry frontmatter and body schema; renderer / wrapup validates. |
| Assumption | Decodability problems are mostly about missing metadata, not content quality. |
| Evidence | • Category drift: `[wiki:design]`, `[wiki:milestone]`, `[wiki:research-note]` all violate the documented allowlist `pattern \| convention \| gotcha \| architecture \| tooling \| api \| other` (line-19 of template).<br>• Heading drift: 5 of 61 wiki entries use `### [wiki:...]` instead of `## [wiki:...]` (latest entries from 2026-05-18+).<br>• Duplicate-slug sections: `[fail:test] snapshot-regen-inside-worktree` appears TWICE in failures.md (count:6 on 2026-05-19 line 32, count:4 on 2026-05-15 line 50). The template's "increment count, never duplicate" contract was violated.<br>• Line-number rot: `render.py:180-209`, `render.py:640-643`, `block_merge.py:17-18` are quoted in entries — these become stale within one refactor.<br>• Internal jargon without anchors: `_codex_stage_skills`, `_HARNESS_MAKER_PKG_ROOT`, `_split_template_frontmatter`, `_validated_demote_severity` quoted as if reader knows them. |
| Trade-off | Costs almost nothing per entry but doesn't address the accumulation curve. Format gate without lifecycle = same content, prettier headers. |
| Compatibility | Drop-in: `wrapup.md.j2` Step 5.1 / 5.2 already lists the format; just add a Python-side validator (`harness_maker.memory_lint`) the wrapup stage and `/hm:health` invoke. |
| Risk | low |

Concrete changes:
- **Allowed-category enum** enforced at append time (LLM-side instruction + Python lint that warns on unknown categories in `/hm:health`).
- **Forbid line numbers** in entries. Force qualified import paths (`harness_maker.io_utils.load_harness_yaml`) instead of `io_utils.py:42`.
- **Structured body** (optional, opt-in): three labelled sub-lines — `Symptom:`, `Cause:`, `Fix / Pattern guard:` — preserves search but bounds size. Today's median entry is ~600 chars and the worst is 1280 chars (`snapshot-regen-inside-worktree` count:6).
- **Single-section invariant**: wrapup-time check that grep-counts `^## \[<tier>:<cat>\] <slug> ` and refuses to add if >1 exists.
- **`applies_to` field** (optional): `applies_to: harness_maker >= 0.15.0` so an entry can self-deprecate when its prerequisite refactor lands.

### Approach B — Lifecycle automation (the missing layer)

| Field | Content |
|---|---|
| Approach | Add a curation pass that reads memory + decides supersede / archive / promote. |
| Assumption | The append-only growth pattern is the dominant problem. LLM judgment can shrink it on schedule. |
| Evidence | • **No promotion path exists.** The only existing automation is "if `count >= 3` write to `pending-proposals.md`" — verified in `wrapup.md.j2:158-168`. No code reads `pending-proposals.md`; no skill surfaces it; no SessionStart hook nags about it. It is a dead-letter queue.<br>• **Pending-proposals failure on record**: `snapshot-regen-order-guard` proposal landed 2026-05-10 (count:3), follow-up `post-finalize-snapshot-regen-hook` 2026-05-17 (count:5), and the failure **recurred again as count:6 on 2026-05-19**. The proposal mechanism literally did not prevent the next recurrence — it just accumulated in a file nobody loads.<br>• **No archive policy.** `[wiki:architecture] verifier-pass-1-5-reduce-only` openly says "Pass 1.5 was stripped by ADR-008" but the entry remains as "library surface retained" prose. `[wiki:milestone] personalization-depth-2026-05-shipped` and `0-12-1-patch-shipped` are release-notes content occupying memory budget.<br>• **`[wiki:research-note]` is a different ship.** 4 entries from 2026-05-16 explicitly say "Awareness only — not immediate adoption". These are dormant ideas that should age out or graduate to a PLAN, not sit in operational memory.<br>• **CLAUDE.md graduation gap**: the "필수 체크리스트" section in CLAUDE.md is exactly the kind of content that should be sourced from high-confidence wiki entries — but the path from wiki to CLAUDE.md is manual and unrecorded. |
| Trade-off | Requires real implementation (~1 PLAN scope). Brings real risk: an automated archive that drops a load-bearing entry is worse than the status quo. Mitigation: archive moves entries to `.claude/memory/archive/{YYYY}.md`, never deletes; promotion is a *proposal* that surfaces in `pending-proposals.md`, the human accepts.|
| Compatibility | Need a new Python module `harness_maker.memory_curate` + a slash command `/hm:memory-curate` (or fold into `/hm:health` Step 3). Templates unchanged; the operation is read-mostly. |
| Risk | medium |

Concrete pass design (`/hm:memory-curate`):
1. **Reference rot check** (mechanical): for every cited `PLAN-*.md` / `ADR-NNN` / function path → exists? if not → suggest archive.
2. **Staleness query** (LLM): for entries older than 60 days with no recent confirmation → "is this still applicable to harness-maker current?" → flag for archive or refresh.
3. **Supersession query** (LLM): pairwise scan within a category — does entry B effectively supersede entry A? Suggest merge.
4. **Promotion query** (LLM): for wiki entries cited N times (rg across `.claude/memory/session/*.md`, `work-docs/PLAN-*.md`, `CLAUDE.md`) — propose graduation to CLAUDE.md.
5. **Test-coverage closure**: for `[fail:*]` entries that say "regression guard: test_X" — grep-confirm `test_X` exists; if missing, propose adding it (closes the open `pending-proposals.md` failure mode where the guard was promised but never landed).
6. **Output**: a structured diff written to `pending-proposals.md` with explicit `accept` / `defer` actions the user picks; no destructive writes.

Cadence: weekly (`/hm:health` could host it on day-7 cadence), or count-triggered (`failures.md >150 lines` → nag at session start).

### Approach C — Retrieval rewrite (highest-immediate-leverage)

| Field | Content |
|---|---|
| Approach | Replace the "skim first 60 lines + grep keywords" loader in `/hm:research` Step 1 with semantic relevance scoring + recency-weighted tail. |
| Assumption | The biggest day-to-day problem isn't quality of stored entries — it's that the right entries don't surface. |
| Evidence | • `wiki.md` is now 264 lines / 62KB; `failures.md` is 134 lines / 38KB. The research stage skims **first 60 lines** (template literal in `## Session Context Loading`). Of wiki.md's 264 lines, lines 60+ never auto-load.<br>• **Bottom-of-file bias**: entries are inserted before the `<!-- @hm:/user:entries -->` closing marker (wrapup Step 5.1 procedure). Newer entries → further from line 1 → **less likely to load**. Today's most relevant entries (boundary-parse, pipestatus, OSS readiness, fresh-install health) all sit below line 246 and never enter the auto-skim.<br>• **The pattern already exists in-repo**: `harness_maker.relevance` ships an LLM-judgment scorer used by the anti-rot crawler (`research-crawler` → `relevance-filter` skill) with adaptive threshold. Re-using that pattern for memory retrieval is a small step.<br>• Grep is keyword-bound: a session on "how do I detect drift in rendered TOML output" will not surface `boundary-parse-test-layer` (no "drift" keyword), even though that wiki entry directly answers the question. |
| Trade-off | Costs a model call per session start (or per `/hm:research` invocation). With caching and ≤8k context budget this is cheap, but it's not free. Worst case: model surfaces irrelevant entries, displacing actually-relevant CLAUDE.md content. |
| Compatibility | Needs change in research / spec / plan stage templates (Phase 1 Step 1 wording) + a helper `harness_maker.memory_retrieve(topic, k=N)` that returns top-N entries by combined `LLM relevance × recency × citation count`. |
| Risk | low-medium |

Concrete loader replacement (in research/plan/spec stages):
```
# OLD
Skim `.claude/memory/wiki.md` (first 60 lines); search relevant: `rg -F "[wiki:" .claude/memory/wiki.md`

# NEW
Surface top-K memory entries relevant to topic via:
!uv run python -m harness_maker.memory_retrieve --topic "<topic>" --k 6 --tier wiki,failures
```

Where the helper returns 6 entries (3 wiki + 3 failures, blended by score), inlined directly into the prompt. No skim-by-fixed-window.

## ⚠️ Pitfalls

1. **Don't make archive destructive.** Moving an entry to `archive/` is fine; deleting risks losing institutional knowledge that the LLM was about to need. Mirror the pattern from `block_merge.merge()` — never silently drop user content (regression learning from `wrapup-eof-append-outside-marker`, `failures.md:104`).
2. **Don't lint-block wrapup.** If memory-format validation runs as a wrapup gate, a bad LLM-written entry stops the commit. Surface warnings only; the commit must always be able to complete. Pattern: same as `/hm:health` advisory probes — non-blocking is the contract.
3. **Don't promote based on count alone.** `count >= 3` already triggers `pending-proposals.md`, and that mechanism failed to prevent the count:6 case. Promotion must require human acknowledgement (proposal surfaced + accepted), not be fully automatic.
4. **Don't move "operational" tagging into category enum.** Wiki today carries `pattern / convention / gotcha / architecture / tooling / api / other` (template line 19). Adding `milestone`, `research-note`, `design` to the enum to "fix the drift" enshrines categories that don't belong in operational memory. Better: those entries belong in CHANGELOG, RESEARCH-*.md, or wiki-design subset that ages out.
5. **Don't let internal jargon entries hide behind "code is self-documenting".** When an entry says `_codex_stage_skills()` it must either (a) cite a stable public path or (b) describe the behaviour abstractly. Many current entries fail this — surface and require restatement at curation time.
6. **Pending-proposals.md cannot stay write-only.** Without a load-on-session-start hook OR a `/hm:proposal-review` flow, every new proposal entry adds noise without surfacing value. Either build the flow or stop writing to that file.
7. **First-60-lines bias inverts learning.** The newer the entry, the less likely it is to load — directly inverse to "recency = relevance" intuition. Fix the loader before fixing the content; otherwise content fixes have no observable effect.

## ❓ Open Questions for `/hm:plan`

1. **Scope of memory-curate**: bundled into `/hm:health` Step 3, or its own `/hm:memory-curate` slash command? Trade-off — `/hm:health` is already long; new command is one more thing to remember.
2. **Retrieval-replacement timing**: ship retrieval rewrite (Approach C) standalone first, or bundle with lifecycle pass (Approach B)? C is cheaper and unblocks the rest of the value (recent entries become visible again).
3. **Archive format**: monthly `archive/YYYY-MM.md`, or single growing `archive.md`, or per-tier (`wiki-archive.md` + `failures-archive.md`)? Affects retrieval semantics.
4. **Promotion target**: when a wiki entry should "graduate", does it go to CLAUDE.md (project-level, committed) or to a separate `.claude/conventions.md` (more searchable, no CLAUDE.md bloat)?
5. **Backwards-compatibility**: today's 61 wiki + 36 fail entries are unstructured. Migration is one-shot LLM rewrite into the new structured-body schema? Or new schema applies only to entries created after the cutover?
6. **Test-coverage closure depth**: should `/hm:memory-curate` actually grep for the named test and propose adding it if missing, or just surface the gap? Auto-proposal might create test-name churn.
7. **Word-level format**: enforce structured body (Symptom/Cause/Fix), or leave free-form with only length caps? Structured body helps decodability but loses some narrative.

## 📚 Sources

(All evidence is from internal files — this research did not require external citations.)

- `.claude/memory/wiki.md` (264 lines, snapshot 2026-05-19)
- `.claude/memory/failures.md` (134 lines, snapshot 2026-05-19)
- `.claude/memory/pending-proposals.md` (3 entries since 2026-05-10)
- `.claude/memory/pending-drift.md` (2 entries)
- `src/harness_maker/templates/stages/wrapup.md.j2` (full read — sections 5.1/5.2/5.3 own append behaviour)
- `src/harness_maker/templates/memory/{wiki,failures}.en.md.j2` (format spec)
- `src/harness_maker/readiness.py:685-751` (memory-continuity dimension scoring)
- `src/harness_maker/synthesize.py:402-404` (memory file rendering wiring)
- `src/harness_maker/relevance.py` (existing LLM-judgment scorer pattern that retrieval rewrite would reuse)

## 🔗 Related Internal Docs

- `[[CLAUDE.md]]` — §"무언가를 고치거나 개선하기 전에 — 필수 체크리스트" is the natural promotion target for stable wiki patterns
- `[[work-docs/PLAN-health-consolidation.md]]` — Memory health metrics live in `_dim_memory_continuity`; this PLAN's follow-up could host the curate step
- `[[wiki:wrapup-marker-discipline-silent-loss]]` — historical regression that motivated stricter marker discipline in wrapup; relevant to "don't make archive destructive" pitfall
- `[[fail:snapshot-regen-inside-worktree]]` — count:6 entry; demonstrates the pending-proposals dead-letter failure case
