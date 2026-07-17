---
type: plan
task_slug: memory-retrieve-lexical-recall
status: complete
created: 2026-07-04
tags: [harness-maker, plan, python, memory, retrieval]
interview_rounds: 2
adrs: 3
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Boost memory_retrieve recall via a conservative pure-Python stemmer on normalized tokens; no trigram, no ML dep"
---

# PLAN — `memory_retrieve` lexical recall enhancement (stemming-only, within memory-md ADR-002)

## 🎯 Executive Summary

**What:** Raise the *recall* of `memory_retrieve`'s lexical pre-filter so a failure logged under
one wording surfaces when the current task is described with *different* wording — by applying a
**conservative, deterministic, pure-Python stemmer** to the tokens on **both** sides before the
existing overlap score. No ML dependency, no Anthropic client, no trigram/blend. Stays inside the
existing architecture: pure-Python lexical prefilter → `<memory_candidates>` fence → semantic
rerank by the consuming Claude turn.

**Why:** `score_entry` scores by raw token-overlap (`|topic∩entry| / |topic|`). A similar failure
worded with a different **inflected surface form** (`snapshots` vs `snapshot`, `skips` vs `skip`)
shares **zero** raw tokens on that word, so it may never enter the `pre_k=30` candidate set, and
the Claude turn never sees it to reuse its slug → a new `count:1` entry instead of `count++`
("leak A"). Live evidence: `wrapup-final-verify-skips-ruff-format-check` (c3) and
`ruff-format-not-in-local-verify-pass` (c2) — the same "local verify misses ruff format" family,
split 3+2. **Normalization creates the token overlap** that surfaces the entry; that is the entire
recall mechanism.

> ⚠️ Scope of the win (validator 2nd pass): the conservative rules close **inflectional**
> variants that share a ≥4-char stem after a single suffix strip — `snapshots`↔`snapshot`,
> `skips`↔`skip`. They do **not** close derivational pairs like `regenerated`↔`regenerate`
> (trailing-`e`: `-ed` yields `regenerat` ≠ `regenerate`) — that residue is left to the
> Claude-turn rerank / `consolidate` companion, per ADR-001. Do not motivate a test with a pair
> the rules cannot actually merge.

**Key decisions (ADRs) — this PLAN's local numbering:**
- ADR-001 — **Stay lexical** (reinforce *memory-md-operations ADR-002*): reject embeddings AND
  reject trigram/blend. Recall comes from stemming alone.
- ADR-002 — Recall = a conservative stemmer applied inside the token-producing functions
  (`topic_tokens`, `_entry_token_set`), so `score_entry`'s **signature and single-signal formula
  are unchanged** — it just scores over normalized tokens.
- ADR-003 — The stemmer's **conservatism is the precision guard**: an enumerated forbidden-collapse
  fixture set gates its aggressiveness. Because there is still exactly one signal (normalized
  overlap), a zero-overlap entry scores exactly `0` and is dropped by the existing `s > 0` filter —
  the dominance/precision invariant holds **automatically**, no tiered score needed.

**Estimated impact:** ~30-50 LoC in `memory_retrieve.py` (one `_stem` helper + call it in the two
token producers) + a recall/precision test module. No new dependency, no CLI/schema change, no
`score_entry` signature change, determinism preserved.

## 📚 Prior Work

- `src/harness_maker/memory_retrieve.py` — module docstring is explicit: *"lexical pre-filtering
  only; semantic top-K selection happens prompt-natively in the consuming Claude turn
  (memory-md-operations ADR-002, ADR-005). No anthropic [client]."* This PLAN **reinforces** it.
- `topic_tokens` (line ~106) lowercases + stopword-strips; `_entry_token_set` (line ~165) builds
  the entry's token set; `score_entry` (line ~178) = `matched / len(topic_tokens_set)`;
  `top_candidates` (line ~196) keeps only `s > 0.0` (line ~211) then slices `pre_k`.
- `render_candidates_block` byte-caps the fence at `byte_cap=10240` and asks the turn to surface
  the top-`k`. **Unchanged** — recall work is upstream, in scoring.
- **Direct `score_entry` callers** (test_memory_retrieve.py:168,175,184-185,194) pass because
  their fixture vocabulary (`zulu/yankee`, `boundary`, `detect/drift`, `boundary/parse`) has **no
  stem collisions** — NOT because `score_entry` is isolated. `score_entry` now scores over
  normalized tokens (its callers feed `topic_tokens()` output, and it calls the now-normalized
  `_entry_token_set` internally). A future caller with body `snapshots` + topic `{snapshot}` WOULD
  change behavior. **The existing suite stays green unchanged** — stemming is purely additive on
  these fixtures (validator 2nd pass traced the whole suite; no pinned-order test shifts).
- Companion PLAN `PLAN-failures-consolidate-cli.md` fixes the *exact-slug* backlog; this PLAN
  reduces future *semantic* leaks. Independent.
- Constraints: Python-only, `uv`, minimal deps, 100% local, deterministic tests, `mypy --strict`.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Recall direction | Architecture | lexical-enhance / TF-IDF-numpy / local-embeddings | **pure-Python lexical enhance** | ADR-001 |
| 2 | Score form (post-validator) | Architecture | stemming-only drop trigram / tiered+gated trigram | **stemming-only, drop trigram** | ADR-002, ADR-003 |

Assumptions locked without a round (low EIG — implementation detail):
- **Stemmer rule set (conservative, validator-tightened):** plural `-s`/`-es`, gerund `-ing`, past
  `-ed`, each behind a **minimum-stem-length guard** (do not strip if the remaining stem is < 4
  chars). **Dropped as landmines:** `-er` (would collapse user→us, server→serv) and `-tion`→`-t`
  (action→act, function→funct). Vendored inline; not `nltk`/`snowball`.
- `pre_k`/`k`/`byte_cap` defaults unchanged (recall is in scoring, not budget).

## 📐 Architecture Decision Records

### ADR-001: Stay lexical — reject embeddings and reject trigram/blend
**Status:** Accepted (2026-07-04, via /hm:plan interview)
**Context:** Leak A is a recall problem. Embeddings are the obvious "semantic" fix but
*memory-md-operations ADR-002* deliberately kept `memory_retrieve` lexical-only, no ML dep, no
Anthropic client. A first draft proposed a token-overlap + stemming + char-trigram **blend**; the
plan-validator proved that a flat weighted sum cannot honor the dominance invariant, and that
trigram's only recall contribution lives in the exact zero-token-overlap case the invariant
forbids promoting — i.e. trigram is near-useless for leak A.
**Decision:** No embeddings, no trigram, no blend. Recall comes **solely** from a conservative
stemmer that turns wording variants into shared normalized tokens. The module stays pure-Python;
the Claude turn stays the semantic reranker.
**Consequences:**
- ✅ No heavy dep, no model download, no network, no cold-start; determinism trivially preserved.
- ✅ No self-contradiction between recall lever and precision invariant (single signal).
- ⚠️ Genuinely different vocabulary sharing no stem still misses. Accepted: the Claude-turn rerank
  + the `consolidate` companion cover the residue; embeddings/TF-IDF remain the documented next
  step if leaks persist.
**Rejected alternatives:**
- Local embedding model — Rejected: heavy dep + determinism/offline burden, overrides ADR-002.
- TF-IDF cosine (numpy) — Rejected (deferred): vectorization dep + corpus-state for marginal gain.
- Char-trigram blend — Rejected: validator-proven to add ~0 recall without breaking dominance.
**Source:** Interview #1, #2

### ADR-002: Normalize inside the token producers; score formula & signature unchanged
**Status:** Accepted (2026-07-04, via /hm:plan interview)
**Context:** The recall win must not break `score_entry`'s public signature (four tests call it
directly with 2 args) nor the single-signal `s > 0` filter contract.
**Decision:** Apply the stemmer inside `topic_tokens` and `_entry_token_set` so both emit
**normalized** token sets. `score_entry` keeps its exact 2-arg signature and `matched / |topic|`
formula — it simply operates on normalized tokens. Recall rises because `snapshots` and `snapshot`
now normalize to the same token, creating an overlap that scored 0 raw.
**Consequences:**
- ✅ Recall on plural/tense wording variants; `score_entry` signature untouched → no test-caller break.
- ✅ Single signal preserved → the `s > 0` prune and `test_top_k_filters_zero_scores` contract intact.
- ⚠️ End-to-end ranking snapshots shift → intentional, named re-baseline in Phase 2 (not blind regen).
**Rejected alternatives:**
- Change `score_entry` to take extra args — Rejected: needless signature break across 4 callers.
**Source:** Interview #2

### ADR-003: Stemmer conservatism is the precision guard (dominance holds automatically)
**Status:** Accepted (2026-07-04, via /hm:plan interview)
**Context:** A too-aggressive stemmer over-collapses distinct tokens (user→us) and pollutes recall
with false matches; that is the only precision risk in a single-signal design.
**Decision:** Bound the stemmer with a **minimum-stem-length guard** and an **enumerated
forbidden-collapse fixture set** (the precision gate). No `-er`, no `-tion`→`-t`. Because normalized
overlap is the sole signal, a zero-overlap entry scores exactly 0 and is filtered — the "no
zero-overlap entry outranks a real match" invariant is automatic, requiring no tiered sort key.
**Consequences:**
- ✅ Dominance/precision invariant is structural, not a weight-tuning target.
- ⚠️ Conservative stemming leaves some variants (heavy derivation) unmatched. Accepted (ADR-001 residue).
**Rejected alternatives:**
- Aggressive stemmer for more recall — Rejected: unbounded over-collapse precision risk.
- Tiered/lexicographic score to police a multi-signal blend — Rejected: unnecessary once trigram is gone.
**Source:** Interview #2

## 🏗️ Technical Design

**Current state:** `topic_tokens(topic) -> frozenset`, `_entry_token_set(entry) -> frozenset`,
`score_entry(entry, topic_tokens_set) -> float = matched/|topic|`, `top_candidates` filters `s>0`
then slices `pre_k`.

**Affected components:**
- `src/harness_maker/memory_retrieve.py` — add `_stem(token: str) -> str` (pure, deterministic,
  min-length-guarded) and a `_normalize(tokens) -> frozenset[str]` wrapper; call it at the end of
  `topic_tokens` and inside `_entry_token_set`. `score_entry` / `top_candidates` / render path
  **unchanged in shape**.
- `tests/unit/test_memory_retrieve.py` (+ possibly a new `test_memory_retrieve_recall.py`).

**Dependencies:** none new. No trigram, no numpy.

**Design:**
1. `_stem(token)` — **first matching suffix wins; no fall-through, no cascade** (pinned semantics,
   validator S1): test the suffixes in order `-es`, `-s`, `-ing`, `-ed`; on the first suffix the
   token ends with, strip it **iff** the remaining stem length ≥ 4 and return; **if that guard
   blocks, return the token unchanged** (do NOT try the next suffix, do NOT re-stem the result).
   No `-er`, no `-tion`. One fixture per branch (matched+stripped / matched+guard-blocked / no-match).
2. `_normalize(tokens)` maps `_stem` over the set.
3. `topic_tokens` and `_entry_token_set` return normalized sets (both sides — symmetry is required
   or the overlap won't match).
4. `score_entry`, `top_candidates`, `render_candidates_block`, `byte_cap` — untouched.

**Data flow:** unchanged externally (CLI in, `<memory_candidates>` fence out). Only the token sets
feeding the existing overlap score change.

**API changes:** none (no new flags, no `score_entry` signature change). Internal token-producer
output changes; the existing suite stays green **unchanged** (stemming is additive on its
fixtures — validator 2nd pass confirmed no pinned-order test shifts), so there is **no
re-baseline** — Phase 2 adds NEW recall fixtures instead.

## 🚦 Execution Status (2026-07-04, /hm:execute)

- **Phase 1 — DONE.** `_stem` + `_normalize` added to `memory_retrieve.py`; called in
  `topic_tokens` and `_entry_token_set`. Suffix order `-es, -s, -ing, -ed`, first-match-wins,
  `_MIN_STEM_LEN=4` guard, no `-er`/`-tion`. Forbidden-collapse + `_stem`-branch fixtures GREEN.
  - **REVIEW refinement (2026-07-04, owner-approved):** the pinned `-es`-before-`-s` assumption was
    relaxed to **sibilant-aware `-es`** — `-es` strips only when the pre-`es` stem ends in
    `_ES_SIBILANTS = ("s","x","z","ch","sh")`, else it falls through to `-s`. Codex + code-reviewer
    independently found the original order foreclosed common `<stem>e`+`s` bridges
    (`files`→`file`, `updates`→`update`, `nodes`→`node`, `codes`→`code`) — the exact "≥4-char stem
    after a single suffix strip" class this PLAN claims to win. The refinement is ADR-001/002/003
    compatible (still lexical, single-signal, no `-er`/`-tion`, min-len guard intact; strictly *more*
    precise) and left every pre-existing fixture green. Accepted residue narrowed accordingly.
- **Phase 2 — DONE.** `tests/unit/test_memory_retrieve_recall.py` (18 tests): stem-is-sole-bridge
  recall (raw baseline 1→2), Phase-1 exit fixture (regenerating snapshots → singular entry),
  precision/filter, determinism. Existing `test_memory_retrieve.py` unchanged (additive, 52 total GREEN).
- **Phase D verify:** `ruff check` / `ruff format --check` / `mypy --strict` clean; full unit suite exit 0.
- **T1 mutation gate:** N-A (no `specs/SPEC-*.machine.yaml` — machine-SPEC path only).
- **⚠️ Orthogonal finding (NOT fixed — out of scope):** the CLI integration demo on the real
  `.claude/memory/failures.md` surfaced ZERO `ruff-format` entries — not a recall miss but a
  **heading-parse gap**: both entries carry a `| previous_count:N` field that `_HEADING_RE` rejects
  (`(?:… count:\d+)?\s*$`), so they never enter the candidate pool at all. Rebuilding the equivalent
  entries with parseable headings surfaces BOTH via the new stemmer (recall mechanism verified).
  This `previous_count` regex gap is a separate concern (heading parsing, not recall scoring) —
  candidate for its own PLAN.

## 📝 Implementation Plan

### Phase 1 — Conservative stemmer + apply on both sides + precision gate
- `depends_on`: []
- `parallel_group`: serial-B
- `merge_hazards`: `src/harness_maker/memory_retrieve.py` (single-file, serial with Phase 2)
- **Scope (in):** `_stem` + `_normalize`; call in `topic_tokens` and `_entry_token_set`;
  **enumerated forbidden-collapse precision fixtures** (the stemmer's exit gate): assert `_stem`
  does NOT merge `user`≠`use`, `server`≠`serv`, `cover`≠`cove`, `action`≠`act`, `function`≠`funct`
  (i.e. `-er`/`-tion` are not stripped) and honors the min-stem-length guard.
- **Scope (out):** trigram (explicitly none), embeddings, weight tuning.
- **Exit criterion:** a recall unit test where topic `"regenerating snapshots"` surfaces entry slug
  `snapshot-regen-inside-worktree` where raw-token scored 0 — **the match is carried by the plural
  normalization `snapshots`→`snapshot` alone** (NOT by `regenerating`→`regen`, which the conservative
  rule set intentionally does NOT produce: `-ing` strip yields `regenerat`, and `regen` is not a goal);
  AND every forbidden-collapse fixture passes.
- **Risk:** medium (over-stemming = precision loss; bounded by the enumerated gate).
- **Rollback point:** revert Phase 1.

### Phase 2 — New recall/precision fixtures + determinism (existing suite unchanged)
- `depends_on`: [1]
- `parallel_group`: serial-B
- `merge_hazards`: none (additive tests; no existing snapshot shifts — validator 2nd pass verified)
- **Scope (in):**
  - **Recall fixture — stem-is-the-SOLE-bridge (validator W3):** a controlled fixture where the
    topic reaches the second entry ONLY through a stem, with a **raw baseline assertion**: entry A
    slug shares a raw token with the topic; entry B slug shares a token only after stemming (e.g.
    topic contains `snapshots`; entry B slug contains `snapshot`). Assert **exactly one** entry
    surfaces with stemming OFF and **both** surface with stemming ON. Do NOT use the two real
    `ruff-format` slugs as the unit fixture — they share `ruff/format/verify` as RAW tokens, so
    both surface without stemming and the test would pass for the wrong reason (they remain the
    real-world *motivation* + the Phase-2 integration manual check, not the unit proof).
  - **Precision guard fixtures:** enumerated forbidden collapses (`user`≠`use`, `server`≠`serv`,
    `cover`≠`cove`, `action`≠`act`, `function`≠`funct`) + min-stem-length guard; an unrelated /
    zero-normalized-overlap entry stays out of `pre_k` (the `s > 0` filter, assert it holds).
  - **`_stem` branch fixtures:** matched+stripped, matched+guard-blocked (returns unchanged),
    no-match (per the pinned first-match-wins semantics).
  - **Determinism:** identical input → identical candidate order across two runs.
- **Existing suite:** stays **green, unchanged** — no re-baseline. Stemming is additive on the
  current fixtures (`boundary/parse/apple/banana/zulu/yankee` do not stem); the prior draft's
  "four shifted snapshots" was wrong (validator 2nd pass traced the suite). If ANY existing test
  unexpectedly shifts during execute, treat it as a real regression, not an intended re-baseline.
- **Scope (out):** embeddings / TF-IDF (deferred per ADR-001).
- **Exit criterion:** `uv run pytest tests/unit/test_memory_retrieve* -q` green **with zero edits
  to existing assertions**; `mypy --strict` clean; the stem-sole-bridge recall fixture shows 1→2
  surfacing; precision + `_stem`-branch fixtures pass.
- **Risk:** low (additive; the raw-baseline assertion guarantees the recall test proves stemming).
- **Rollback point:** Phase 1.

## 🧪 Testing Strategy
- **Unit — recall (stem is the sole bridge):** raw baseline shows 1 entry surfaces; stemming ON →
  both surface. Guarantees the test proves stemming, not incidental raw overlap.
- **Unit — precision gate (ADR-003):** enumerated forbidden collapses (user≠use, server≠serv,
  cover≠cove, action≠act, function≠funct) + min-stem-length guard.
- **Unit — `_stem` branches:** matched+stripped / matched+guard-blocked / no-match.
- **Unit — filter intact:** zero-normalized-overlap → score 0 → excluded from `pre_k`.
- **Unit — determinism:** identical inputs → identical order twice.
- **Regression:** full `memory_retrieve` suite green **with no edits to existing assertions**
  (stemming is additive — no re-baseline); an unexpected shift = real regression.
- **Integration:** CLI on the real `.claude/memory/failures.md` with a `ruff-format`-family topic →
  both members appear in the fence (manual boundary check; motivation, not the unit proof).

## ⚠️ Risks & Mitigation
| Risk | Severity | Mitigation |
|------|----------|-----------|
| Over-stemming collapses distinct tokens (precision loss) | medium | conservative rules (no -er/-tion) + min-stem-length guard + enumerated forbidden-collapse gate |
| Existing test unexpectedly shifts during execute | low | stemming is additive (validator-traced); no re-baseline planned → any shift is a real regression to investigate, not to bless |
| Stemmer symmetry bug (only one side normalized) | medium | normalize in BOTH token producers; recall test would fail if asymmetric |
| Scope creep toward embeddings/trigram | low | ADR-001 explicitly rejects both; TF-IDF documented as the *next* step, not this one |

## ✅ Success Criteria
- [x] No new dependency; `memory_retrieve` still pure-Python, no Anthropic client, no trigram.
- [x] `score_entry` signature unchanged; the 4 direct-caller tests still pass without edits.
- [x] The `ruff-format` family fixture: both differently-worded members surface in `pre_k` for a
      shared-meaning topic (they did not before).
- [x] Precision gate: enumerated forbidden collapses never merge; zero-overlap entries filtered.
- [x] Recall fixture proves stemming via a raw baseline (1 surfaces raw → 2 surface stemmed).
- [x] Existing suite green with **zero edits to existing assertions** (stemming additive, no re-baseline).
- [x] Deterministic; `mypy --strict` clean; full retrieve suite green.

## 🔍 Plan Validation

**plan-validator (opus), 2 passes: MAJOR_REVISION → NEEDS_REVISION → RESOLVED.**

*Pass 1 (MAJOR_REVISION)* — genuine critical: a flat weighted sum cannot express the dominance
invariant, and char-trigram's only recall value lives in the invariant-forbidden zero-overlap case.
Resolved by **Interview #2 → dropping trigram/blend entirely** (stemming-only, single signal →
dominance holds structurally).

*Pass 2 (NEEDS_REVISION — critical CONFIRMED closed)* — the re-validation verified the dominance
invariant now holds automatically (zero normalized-overlap → score 0 → dropped by `s>0`), the 4
direct `score_entry` callers still pass, and the corrected Phase-1 exit criterion is accurate. It
then caught residual imprecision in my *first* revision, now folded in:
- **Phantom re-baseline** — the 3 tests I named as "will shift" (`:218/:236/:286`) use
  `boundary/parse/apple/banana` fixtures that the conservative rules do NOT stem → they do NOT
  shift. Corrected: stemming is **additive**, existing suite stays green unchanged, **no
  re-baseline**; Phase 2 adds NEW recall fixtures instead.
- **`regenerated`↔`regenerate` false example** migrated into the Exec Summary → struck; scope of
  the win pinned to inflectional pairs (`snapshots↔snapshot`, `skips↔skip`); derivational residue
  explicitly deferred to ADR-001.
- **Fragile recall fixture** (real `ruff-format` slugs share raw tokens) → replaced with a
  stem-is-the-sole-bridge fixture + raw baseline (1 raw → 2 stemmed).
- `_stem` semantics pinned (first-match-wins, guard-block → unchanged, no cascade) + per-branch fixtures.
- Prior-Work caller claim reworded (they pass by no-stem-collision vocab, not isolation).

Codex second opinion: **skipped** (manual two-plan scoping pass — `codex exec` not dispatched).
For a formal Codex vote, re-run `/hm:plan memory-retrieve-lexical-recall` standalone.
