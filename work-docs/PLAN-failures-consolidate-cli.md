---
type: plan
task_slug: failures-consolidate-cli
status: complete
created: 2026-07-04
tags: [harness-maker, plan, python, memory, cli]
interview_rounds: 1
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Opt-in memory_md consolidate subcommand — merge exact-slug failure dups under lock, close matches>1 crash"
---

# PLAN — `memory_md consolidate` subcommand (exact-slug failure de-duplication)

## 🎯 Executive Summary

**What:** Add an opt-in `python -m harness_maker.memory_md consolidate` subcommand that
merges *exact-slug* duplicate entries in `failures.md` (and, by symmetry, `wiki.md`)
into a single entry, under the existing flock + `@hm:user:entries` marker discipline.

**Why:** The pre-0.37.0 backlog left one true exact-slug duplicate —
`snapshot-regen-inside-worktree` at `count:7` (2026-05-19) **and** `count:4` (2026-05-15).
`memory_md.upsert-failure` fail-closes on `matches > 1`
(`MemoryBlockError: duplicate entry for slug … — cannot pick which to replace`), so the
**next recurrence of this hot (11-occurrence) failure will crash the `/hm:wrapup` memory
step**. This is a latent crash, not a cosmetic split. The subcommand both backfills the
existing dup and closes the structural gap that made a doubled slug unrepairable.

**Key decisions (ADRs):**
- ADR-001 — merged `count` = **sum** of the duplicates' counts (7+4 → 11).
- ADR-002 — canonical body = the **earliest** entry's body; later bodies fold to dated occurrence bullets.
- ADR-003 — keep the `upsert-failure` `matches > 1` **raise** (hot-path fail-closed); consolidation is a **separate opt-in** subcommand, never auto-run by wrapup.

**Estimated impact:** ~30-50 LoC in `memory_md.py` + 1 CLI subparser + ~6-8 unit tests.
One-time run on the live `failures.md` removes the single existing dup. No template/render
change, no schema change.

## 📚 Prior Work

- `src/harness_maker/memory_md.py` — `upsert-failure` / `upsert-wiki` / `append-session`
  already own the flock, slug-dedup, marker placement, and atomic write. Consolidate reuses
  all of it (same lock, same `_entry_headings` / marker-locate helpers, same `atomic_write`).
- `failures.md` header contract: `## [fail:<category>] <slug> | <YYYY-MM-DD> | count:<N>`,
  followed by a body paragraph and `- [<date>] <note>` occurrence bullets.
- **Evidence invariant** (`memory_md.py:171`): "a `count:N` entry never outruns its recorded
  evidence." This is enforced **only on write** (empty occurrence note → raise). There is no
  read-time `count == bullets+1` assertion — which is why ADR-001 (sum) is admissible for a
  legacy backfill where bullets are incomplete.
- Direct-edit ban precedent: the 2026-05-17 regression lost 5 wiki entries to a raw whole-file
  edit that dropped the close marker. Consolidation MUST happen inside the lock via the CLI —
  this is the whole reason we build a subcommand instead of hand-editing.
- Related failure entries: `[fail:test] snapshot-regen-inside-worktree` (the dup being fixed).

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Merged count value | Contract | sum / reconstruct(bullet+1) / max | **sum = 11** | ADR-001 |
| 2 | Canonical body on merge | Contract | earliest+bullet / longer+bullet / concat | **earliest body canonical, later → dated bullet** | ADR-002 |
| 3 | `matches>1` crash handling | Architecture | raise+opt-in consolidate / auto-consolidate in upsert / wrapup auto-heal | **keep raise + separate opt-in consolidate** | ADR-003 |

Assumptions locked without a round (low EIG — do not change ADRs/phase scope):
- Consolidate **scans all slugs** and merges *every* exact-dup group it finds (general
  maintenance tool), not a single `--slug` target. A `--slug` filter is a nice-to-have, deferred.
- `--dry-run` is supported and reports what *would* merge (mirrors the `make --dry-run` house style).
- Applies to both `failures.md` and `wiki.md`, but the **wiki fold is lossy by nature** (W3):
  `upsert-wiki` REPLACES the whole body on the next upsert and has no occurrence-bullet
  convention, so any later-wiki-body folded to bullets would be silently dropped by the next
  `upsert-wiki`. Therefore for wiki, later bodies are **concatenated into the canonical body
  paragraph** (survives replace), not folded to bullets. Wiki currently has **0** exact dups, so
  this path is defensive/covered-by-test only.

## 🚫 Non-Goals (S1)

- **Only exact-slug matching.** No fuzzy / near-miss / semantic slug matching (that is the
  companion PLAN `memory-retrieve-lexical-recall`). Two differently-spelled slugs are NOT merged.
- **No `--slug` target filter** in v1 (scan-all only); deferred nice-to-have.
- **Never wrapup-auto** (ADR-003) — consolidate is maintainer-invoked only.
- **No read-time `count == bullets+1` backfill** — the evidence invariant stays a write-time
  guard; consolidate does not reconstruct missing bullets (ADR-001).

## 📐 Architecture Decision Records

### ADR-001: Merged count is the arithmetic sum of duplicate counts
**Status:** Accepted (2026-07-04, via /hm:plan interview)
**Context:** Two entries for one slug carry independent counts (7 and 4). The merged entry
needs a single count, and the evidence invariant says `count:N` should be backed by N−1
occurrence bullets — which legacy dups cannot satisfy (they predate the bullet convention).
**Decision:** merged `count` = Σ(duplicate counts) = 11. Emit a synthesized consolidation
occurrence bullet documenting the merge so the provenance is visible.
**Consequences:**
- ✅ Preserves the true recurrence signal (the whole point of `count`), so `count>=3`
  escalation math stays honest.
- ⚠️ The merged entry's `count` may exceed `bullets+1` (the invariant becomes aspirational
  for this one legacy backfill). Accepted: the invariant is a forward-write guard, not a
  read-time constraint, and consolidate never runs on the hot path.
**Rejected alternatives:**
- Reconstruct `count = total_bullets + 1` — Rejected: would *understate* real recurrence.
- `max(counts)` — Rejected: silently discards the other entry's occurrences.
**Source:** Interview #1

### ADR-002: Earliest entry's body is canonical; later bodies fold to dated bullets
**Status:** Accepted (2026-07-04, via /hm:plan interview)
**Context:** Each duplicate has its own main body paragraph; only one can head the merged entry.
**Decision:** Sort the dup group by first-seen date ascending. The earliest entry's body is
canonical (its heading date becomes the merged first-seen date). Each later entry's body text
is appended as a `- [<that-entry's-date>] <body, collapsed to one line>` occurrence bullet.
All pre-existing occurrence bullets from every dup are merged in and sorted chronologically.
**Body/bullet split rule (W2 — explicit):** for each entry, only a **trailing contiguous run**
of lines matching `^- \[\d{4}-\d{2}-\d{2}\]` counts as occurrence bullets; everything between the
heading and that run is the canonical body, kept **verbatim** (never reordered). This prevents a
body that itself contains an ordinary `- ` markdown list line from being misclassified as an
occurrence bullet and chronologically reordered.
**Consequences:**
- ✅ Zero information loss **for failures** — every body and every bullet survives (wiki fold is
  lossy by nature → concatenated into the canonical body instead, see Prior Work / W3).
- ✅ Preserves the original first-seen framing (chronologically correct).
- ⚠️ A long later-body becomes a one-line bullet (collapsed); full text still present, just reflowed.
**Rejected alternatives:**
- Keep the *longer* body — Rejected: can scramble first-seen ordering.
- Concatenate both bodies (failures) — Rejected: leaves duplicated prose in the canonical paragraph.
**Source:** Interview #2

### ADR-003: Keep the upsert `matches>1` raise; consolidation is a separate opt-in command
**Status:** Accepted (2026-07-04, via /hm:plan interview)
**Context:** `upsert-failure` currently raises on a doubled slug. We could make it self-heal
(auto-consolidate then increment) or have wrapup auto-run consolidate every time.
**Decision:** The hot-path `upsert` **keeps** its fail-closed raise. `consolidate` is a
distinct, explicit, maintainer-invoked subcommand. `/hm:wrapup` does **not** call it automatically.
**Consequences:**
- ✅ The hot path stays simple and fail-closed — no merge logic on every wrapup, no per-wrapup
  side effect, no risk of an unexpected auto-merge.
- ✅ Consolidation is a deliberate act (matches the second-brain / manual-promotion philosophy).
- ⚠️ A doubled slug still *crashes* upsert until someone runs `consolidate`. Accepted:
  the crash is loud + actionable, and dups are now rare (the forward dedup works).
**Rejected alternatives:**
- Auto-consolidate inside `upsert` — Rejected: couples merge logic to the hot path.
- wrapup calls consolidate every run — Rejected: per-wrapup side effect + churn.
**Source:** Interview #3

## 🏗️ Technical Design

**Current state:** `memory_md._upsert` (the shared insert/replace engine) locates the marker
block, extracts headings via `_entry_headings`, and on `len(matches) > 1` raises
`MemoryBlockError`. No merge path exists.

**Affected components:**
- `src/harness_maker/memory_md.py` — new `consolidate(root, *, target_file, dry_run) -> ConsolidateReport`
  function + a `consolidate` subparser in `main()`.
- `tests/unit/test_memory_md*.py` — new test module or additions.

**Dependencies:** none new. Reuses `atomic_write`, the per-file flock helper, `_HEADING_RE`,
`_FAILURE_META_RE`, `_collapse_note`, and the marker constants. **Does NOT reuse**
`_entry_headings` for parsing (it discards the `cat` group and returns only `(idx, slug)` — W4)
nor `_parse_failure_meta` alone (it RAISES on wiki headings that have no `count:` — W4); a small
consolidate-local parser handles both file types.

> **Phase-1 refactor prerequisite (W1):** `fail_heading` / `wiki_heading` and the entry-boundary
> logic (`later = sorted(...); end = later[0] if later else close_idx`) are currently **closures
> inside `_upsert`** (`memory_md.py:212-216, 264-265`), not reusable. Phase 1 first **hoists them
> to module scope** as the single source of truth, then both `_upsert` and `consolidate` call
> them — so a consolidated heading can never drift from `_FAILURE_META_RE` (the drift that would
> break the next `upsert-failure` on the merged slug).

**Design:**
1. **Per-file loop.** For each requested file (`--file failures|wiki|both` → the per-file list),
   acquire **that file's** flock (`.failures.lock` / `.wiki.lock`, `memory_md.py:78-83`) — NOT a
   single shared lock — then process it, then release. (W4)
2. Read file; locate `@hm:user:entries` block (reuse the marker-locate helper; if absent → no-op + warn).
3. Parse entries within the block into `(heading_idx, category, slug, date, count|None, body_lines, bullets)`
   using the module-level `fail_heading`/`wiki_heading` inverse + `_HEADING_RE.group('cat')` for
   category; `count` is `None` for wiki. Body/bullet split per ADR-002's trailing-run rule.
4. Group by slug. For each group with >1 member:
   - Sort by date asc.
   - `merged_date` = earliest date; canonical body = earliest body.
   - **Failures:** `merged_count` = Σ counts; occurrence bullets = all members' pre-existing
     bullets + one synthesized `- [<date>] <collapsed later-body>` per non-canonical member (via
     the hoisted `_collapse_note`) + one `- [<today>] consolidated N duplicate entries` note;
     sort bullets chronologically (stable).
   - **Wiki:** no `count`, no bullets — concatenate later bodies into the canonical body paragraph (W3).
   - Category: if members disagree, keep canonical's + add a note bullet (failures) / parenthetical (wiki) flagging the mismatch.
5. Rewrite the block with one entry per slug (dedup groups collapsed, singletons untouched, order
   preserved by canonical/earliest position among the group's members).
6. `--dry-run`: compute the report, print the plan, **do not write**.
7. Else `atomic_write` the rebuilt file; return `ConsolidateReport(groups_merged, entries_collapsed, slugs=[...])`.

> **All-or-nothing semantics (W5):** if a folded later-body collapses to contain a marker string,
> `_collapse_note` raises `MemoryBlockError` and the **entire consolidate run aborts with no
> write** (`atomic_write` guarantees no partial file). This is accepted behavior, tested in Phase 2.

**Dry-run report format (S2):** one line per merge group —
`<slug>: <N> entries -> count:<sum>, first-seen <date>` — plus a summary tail
`consolidate: <G> group(s), <E> entries collapsed` (wiki lines omit `count:`).

**Data flow:** CLI → per-file loop → `consolidate()` under that file's lock → atomic write →
report to stdout (one line per merged group + a summary tail).

**API changes:** new CLI subcommand only. `--root` (default `.`), `--file {failures,wiki,both}`
(default `both`), `--dry-run`, `--today <YYYY-MM-DD>` (deterministic date for the consolidation note).

## 📝 Implementation Plan

### Phase 1 — Hoist shared helpers, then `consolidate()` core + CLI subparser
- **Status: DONE** (2026-07-04) — hoisted `_wiki_heading`/`_fail_heading`/`_entry_span_end` to module scope; `_upsert` repointed (existing suite green = behavior-neutral); `consolidate()` + `consolidate` subparser landed. **Real-data hardening (not in original scope):** a legacy heading `... | count:3 | previous_count:2` in the live `failures.md` fails `_FAILURE_META_RE`; `_parse_entries` now tolerates unparseable meta for **singletons** (copied verbatim) and only a dup-group member must parse cleanly (guarded in `_consolidate_file`).
- `depends_on`: []
- `parallel_group`: serial-A
- `merge_hazards`: `src/harness_maker/memory_md.py` (shared with upsert — same file, serial)
- **Scope (in):**
  1. **Refactor prerequisite (W1):** hoist `fail_heading` / `wiki_heading` and the entry-boundary
     computation out of `_upsert`'s closure scope to module-level functions; repoint `_upsert` at
     them (behavior-preserving — existing `memory_md` tests must stay green as the refactor's proof).
  2. New `consolidate(root, *, target_files, dry_run, today) -> ConsolidateReport` + `consolidate`
     subparser (`--root` / `--file {failures,wiki,both}` / `--dry-run` / `--today`). Per-file lock
     loop (W4); consolidate-local parser using `_HEADING_RE` (category) + the trailing-run
     body/bullet split (ADR-002).
- **Scope (out):** `upsert`/`append-session` behavior unchanged; no template/render change.
- **Exit criterion:** (a) full existing `memory_md` suite green after the hoist (refactor is
  behavior-neutral); (b) `uv run python -m harness_maker.memory_md consolidate --root <tmp> --dry-run`
  on a fixture with a known dup prints `<slug>: <N> entries -> count:<sum>, first-seen <date>`
  and writes nothing.
- **Risk:** medium (edits the shared write engine; marker safety + heading-format parity critical).
- **Rollback point:** revert Phase 1 commit.

### Phase 2 — Unit tests
- **Status: DONE** (2026-07-04) — `tests/unit/test_memory_md_consolidate.py`, 12 tests, all green: count-sum, earliest-canonical, later→bullet, dry-run no-op, byte-identical no-dup, markers-single, body-with-`- `-list-line, 3-member group, singleton-dup-singleton order, category-mismatch note, collapse-note marker abort byte-identical, wiki concatenate, CLI dry-run.
- `depends_on`: [1]
- `parallel_group`: serial-A
- `merge_hazards`: none (test files)
- **Scope (in):** exact-dup merge (count=sum, earliest body canonical, later body→bullet,
  earliest first-seen date preserved); bullets merged chronologically; **no-dup → byte-identical
  no-op**; `--dry-run` writes nothing; marker preserved (open+close intact); category-mismatch
  note path; consolidated entry is subsequently `upsert`-able (post-merge `matches == 1`, count→12).
  **Added per validator (W2/W5/S3):** (a) a failure body that itself contains a `- ` markdown list
  line is kept verbatim in the canonical body, NOT reordered as an occurrence bullet (trailing-run
  split rule); (b) a later-body that fails `_collapse_note` (marker string) → the whole run aborts
  and the file is **byte-identical** (all-or-nothing); (c) a 3+-member dup group; (d) singleton-dup-
  singleton ordering — singletons keep their relative position after the merge; (e) dry-run report
  line field assertions; (f) wiki fold concatenates into the canonical body (survives a later
  `upsert-wiki` replace — W3).
- **Scope (out):** integration/e2e.
- **Exit criterion:** `uv run pytest tests/unit/test_memory_md*consolidat* -q` green; full
  `memory_md` suite still green.
- **Risk:** low.
- **Rollback point:** Phase 1.

### Phase 3 — One-time backfill on the live failures.md
- **Status: VERIFIED (dry-run), LIVE-WRITE DEFERRED** (2026-07-04) — dry-run against the real base `failures.md` with the new code reports exactly one group: `snapshot-regen-inside-worktree: 2 entries -> count:11, first-seen 2026-05-15` (wiki: 0). Exit criterion is proven achievable. The actual write is **deferred out of `/hm:execute`**: `consolidate` resolves to the **base** memory dir (`_base_root`), so writing it now would create base dirt that tangles with finalize's dirty-base stash + the task-land seam. Run it as a deliberate step once the feature is committed: `python -m harness_maker.memory_md consolidate --file failures` then verify `grep -c snapshot-regen-inside-worktree .claude/memory/failures.md` → 1.
- `depends_on`: [1, 2]
- `parallel_group`: serial-A
- `merge_hazards`: `.claude/memory/failures.md` (the live file — run once, verify)
- **Scope (in):** run `consolidate --dry-run` on the real `.claude/memory/failures.md`, confirm
  it reports exactly the `snapshot-regen-inside-worktree` group; then run for real; verify
  `grep -c snapshot-regen-inside-worktree` → 1 heading at `count:11`, first-seen `2026-05-15`.
- **Scope (out):** wiki (0 dups — dry-run should report none).
- **Exit criterion:** `grep -oE "^## \[fail:[a-z]+\] [a-z0-9-]+" .claude/memory/failures.md | sort | uniq -d`
  returns empty.
- **Risk:** low (dry-run gated; atomic write; lock-safe).
- **Rollback point:** git checkout `.claude/memory/failures.md` (it is tracked).

## 🧪 Testing Strategy
- **Unit:** Phase 2 above (fixtures with 2- and 3-member dup groups, singleton, empty block).
- **Integration:** the Phase 3 dry-run on the real file *is* the integration boundary check.
- **Manual:** eyeball the merged `snapshot-regen-inside-worktree` entry reads coherently.

## ⚠️ Risks & Mitigation
| Risk | Severity | Mitigation |
|------|----------|-----------|
| Marker drop during rewrite (2026-05-17 class) | high | reuse the exact locate+atomic-write path upsert uses; test asserts open+close count == 1 |
| Consolidated heading drifts from `_FAILURE_META_RE` → breaks next upsert (W1) | high | Phase-1 hoists `fail_heading` to module scope as single source; test does a post-merge upsert |
| Body with `- ` list line misread as occurrence bullet (W2) | medium | trailing-run split rule; explicit test |
| `_collapse_note` raise aborts run (W5) | low | all-or-nothing by design; test asserts byte-identical on abort |
| wiki fold lost by later `upsert-wiki` replace (W3) | low | wiki concatenates into canonical body, not bullets; 0 live dups |
| Merged count violates evidence invariant | low | ADR-001 accepts it; consolidate never runs on hot path; no read-time check exists |
| Category mismatch across dups | low | keep canonical + note; covered by test |
| Concurrent fleet write during backfill | low | per-file flock serializes it |

## ✅ Success Criteria
- [x] `consolidate` subcommand exists with `--dry-run` / `--file` / `--root` / `--today`.
- [x] Live `failures.md` dup identified — dry-run verified `snapshot-regen-inside-worktree: 2 entries
      -> count:11, first-seen 2026-05-15`. **Live WRITE deferred** (post-commit one-liner
      `python -m harness_maker.memory_md consolidate --file failures`); see Phase 3 status.
- [x] `upsert-failure` on that slug now succeeds (no `matches>1` raise) — `test_merged_entry_is_upsertable_again`.
- [x] Full `memory_md` test suite green (21 consolidate tests + full unit suite); ruff/mypy clean.

## 🔍 Plan Validation

**plan-validator (opus): NEEDS_REVISION → RESOLVED.** No critical; the flagged
evidence-invariant-on-later-upsert interaction was confirmed **clean** (post-merge `matches==1` →
normal count++ path). 5 warnings + 3 suggestions folded in:
- W1 (heading builders are `_upsert` closures) → Phase-1 hoist to module scope, single source vs `_FAILURE_META_RE`.
- W2 (body/bullet split undefined) → explicit trailing-run rule in ADR-002 + test.
- W3 (wiki fold lossy — `upsert-wiki` replaces body) → wiki concatenates into canonical body; zero-loss scoped to failures.
- W4 (`_entry_headings` drops cat; `_parse_failure_meta` raises on wiki; `--file both` needs per-file lock loop) → consolidate-local parser + per-file lock loop.
- W5 (`_collapse_note` raise) → documented all-or-nothing + byte-identical-on-abort test.
- S1 Non-Goals section added; S2 dry-run report fields named; S3 singleton-ordering test added.

Codex second opinion: **skipped** (manual two-plan scoping pass — `codex exec` not dispatched).
For a formal Codex vote, re-run `/hm:plan failures-consolidate-cli` standalone.
