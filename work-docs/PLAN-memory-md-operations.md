---
type: plan
task_slug: memory-md-operations
status: complete
created: 2026-05-19
tags: [harness-maker, plan, python, memory, retrieval]
research_doc: "[[RESEARCH-memory-md-operations]]"
interview_rounds: 3
adrs: 6
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Replace first-60-lines memory loader with hybrid lexical-prefilter + Claude-rerank in research/plan/spec stages"
---

# PLAN — memory-md-operations

## 🎯 Executive Summary

**TL;DR:** Replace the "skim first 60 lines + grep keywords" memory loader in `/hm:research`, `/hm:plan`, `/hm:spec` with a hybrid retrieval — Python lexical pre-filter top-30, then inline Claude rerank to top-6 — so recent wiki/failure entries (currently invisible to the auto-loader) actually surface during stages.

**What:** New Python module `harness_maker.memory_retrieve` + invocation block in 3 stage templates.

**Why:** RESEARCH-memory-md-operations.md confirmed wiki.md (264 lines / 62KB) and failures.md (134 lines / 38KB) have outgrown the 60-line skim budget. Newer entries get inserted before the `<!-- @hm:/user:entries -->` closing marker, so recency-is-relevance is exactly inverted by the loader: **the more recent an entry, the less likely it loads.** All entries from line 246+ of wiki.md (boundary-parse-test-layer, pipestatus-vs-dollar-question-mark, oss-launch-readiness-three-layer, fresh-install-health-baseline, etc.) never enter the auto-skim today.

**Key decisions:**
- ADR-001 — Scope = retrieval-only; format gate (Approach A) and lifecycle pass (Approach B) deferred as separate PLANs.
- ADR-002 — Hybrid mechanism (Python lexical + Claude inline rerank); NO separate Anthropic API call.
- ADR-003 — Stage applicability = research + plan + spec.
- ADR-004 — Input = wiki.md + failures.md only.
- ADR-005 — Rerank executes in the stage-template-hosting Claude turn (no sub-call).
- ADR-006 — No tier-quota in top-K (unified ranking, not 3+3 wiki/failures split).

**Estimated impact:** 2 phases. ~250 lines new Python + 3 template edits + snapshot regen. Zero new dependencies.

## 🚫 Non-Goals

Future PLANs may revisit these — they are explicitly OUT of this PLAN's scope:
- Format lint / category enum enforcement / duplicate-slug rejection at wrapup time (Approach A from RESEARCH).
- Lifecycle automation — staleness queries, supersession detection, archive directory, automated promotion to CLAUDE.md (Approach B from RESEARCH).
- Pending-proposals.md surfacing / dead-letter resolution flow.
- session/*.md retrieval (entry schema differs; deferred).
- Loop driver memory loading changes.
- harness.yaml config knobs for k / pre-k / byte cap (sane defaults only).
- Telemetry / adaptive-threshold integration.

`/hm:execute` MUST NOT bundle work from this list ("while I'm here…"). Spawn a follow-up PLAN instead.

## 📚 Prior Work

- **RESEARCH-memory-md-operations** — the 3-layer recommendation this PLAN narrows. Critical evidence: line-60+ entries invisible to current loader; `snapshot-regen-inside-worktree` count:6 duplicate-section bug; pending-proposals.md dead-letter.
- **failures.md `ship-without-verifying-target-env-credentials`** (count:1, 2026-05-11) — 0.10.0 shipped verifier code requiring `ANTHROPIC_API_KEY`; target env (Claude Code subscription) lacks it. ADR-002 is the regression guard.
- **failures.md `snapshot-regen-inside-worktree`** (count:6, 2026-05-19) — running snapshot regen from a worktree embeds worktree paths in rendered output. Phase 2 risk register R3 + exit criterion explicitly guard.
- **failures.md `wrapup-final-verify-skips-ruff-format-check`** (count:2, 2026-05-19) — CI runs `ruff format --check .` distinct from `ruff check`; wrapup historically skips the former. Both phases' exit criteria bind both commands.
- **`src/harness_maker/relevance.py`** — established pattern for tokenization (`_WORD_RE`) and lightweight scoring; this PLAN reuses, does not duplicate.
- **`src/harness_maker/llm_judge.py:62-68`** docstring — confirms "prompt-native LLM judgment via the executing Claude agent, results fed back inline" is the canonical pattern for harness-maker LLM use.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|---|---|---|---|---|
| 1 | PLAN scope | Scope | 1-layer / 2-layer / full 3-layer? | Retrieval-only (Approach C) | ADR-001 |
| 2 | retrieval mechanism | Architecture | LLM API call / prompt-native / lexical / hybrid? | Hybrid (lexical pre-filter + Claude rerank) | ADR-002 |
| 3a | Stage applicability | Architecture | Research-only / Research+Plan+Spec / +Loop? | Research+Plan+Spec | ADR-003 |
| 3b | Entry input | Contract | wiki+failures / +session / wiki-only? | wiki.md + failures.md | ADR-004 |

Validator (plan-validator agent, NEEDS_REVISION → resolved inline) promoted 2 implicit decisions:
- Rerank execution surface (stage-template-hosting Claude turn) → ADR-005
- No tier-quota in top-K → ADR-006

## 📐 Architecture Decision Records

### ADR-001: Scope = retrieval-only (single PLAN)
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 1)
**Context:** RESEARCH recommended full 3-layer (format gate + lifecycle pass + retrieval rewrite), with retrieval as highest-leverage entry point. Bundling all three in one PLAN expands review surface and drift risk; splitting into 3 PLANs allows independent acceptance.
**Decision:** This PLAN ships **retrieval rewrite only**. Format gate and lifecycle pass become separate follow-up PLANs.
**Consequences:**
- ✅ Bounded review surface (2 phases vs 6+).
- ✅ Retrieval lands first → recent entries become visible → effectiveness of follow-up A/B becomes measurable.
- ⚠️ Format drift (duplicate slugs, category enum violations) persists until Approach A follow-up.
- ⚠️ pending-proposals.md remains a dead-letter queue until Approach B follow-up.
**Rejected alternatives:** Full 3-layer (rejected: review surface too large for one cycle). Lint-only (rejected: doesn't fix the loading problem).
**Source:** Interview #1.

### ADR-002: Hybrid retrieval mechanism (Python lexical + inline Claude rerank, NO separate API call)
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 2)
**Context:** Target env (Claude Code subscription) lacks `ANTHROPIC_API_KEY`. Per failures.md `ship-without-verifying-target-env-credentials` (2026-05-11), shipping code that imports `anthropic.Anthropic` and calls the SDK is a known failure mode. `llm_judge.py:62-68` docstring records the canonical pattern: prompt-native LLM judgment via the executing Claude agent.
**Decision:** `harness_maker.memory_retrieve` is a **pure Python** module — entry parsing, lexical scoring, top-30 pre-filter. The stage template wraps its stdout in a fence and instructs the running Claude turn to rerank semantically to top-6. No `anthropic` import anywhere in the new module.
**Consequences:**
- ✅ Works in target env with no credential dependency.
- ✅ Token cost ~3-5KB/stage (vs ~25KB whole-file load).
- ✅ Reuses `relevance._WORD_RE` tokenizer; minimal new surface.
- ⚠️ Quality depends on running Claude agent's ability to rerank within an already-loaded conversation; cold-start sessions get slightly worse first-call quality.
**Rejected alternatives:** Pure prompt-native (rejected: 25KB token cost per stage on cold cache). Pure BM25 lexical (rejected: research-flagged semantic-match misses, e.g. topic="drift detection" misses `boundary-parse-test-layer`). Anthropic SDK call (rejected: replays `ship-without-verifying-target-env-credentials`).
**Source:** Interview #2.

### ADR-003: Stage applicability = research + plan + spec
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 3a)
**Context:** Three stages today carry identical "Skim first 60 lines + grep" instructions in their "Session Context Loading" block: research, plan, spec. Other stages (execute, review, wrapup, loop, verify, health) load memory differently or not at all.
**Decision:** Migrate research + plan + spec atomically in Phase 2. Loop / execute / review deferred.
**Consequences:**
- ✅ Symmetric — all three "front-of-flow" stages get the same loader.
- ✅ Single phase boundary (3 template edits + snapshot regen).
- ⚠️ Stage loading pattern is divergent for ~1 release until follow-up PLAN extends to loop.
**Rejected alternatives:** Research-only (rejected: pattern fragmentation). Include loop (rejected: loop driver memory access has different shape — broader scope creep).
**Source:** Interview #3a.

### ADR-004: Input = wiki.md + failures.md only
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 3b)
**Context:** wiki.md and failures.md share the `[<tier>:<category>] <slug> | <date>` anchor format. `.claude/memory/session/*.md` files use a different schema (per-date file, `[decision:slug]` anchor, no count field, no consistent body structure).
**Decision:** Parser consumes wiki.md + failures.md. Session log retrieval deferred.
**Consequences:**
- ✅ Single parser; minimal branching.
- ⚠️ Session-log "decision" anchors won't surface to research/plan/spec via retrieval.
**Rejected alternatives:** Include session/*.md (rejected: schema differs, parser branching overhead, noise risk). Wiki-only (rejected: failures.md `Pattern guard` sentences are the most actionable retrieval target).
**Source:** Interview #3b.

### ADR-005: Rerank executes in the stage-template-hosting Claude turn
**Status:** Accepted (2026-05-19, plan-validator W1)
**Context:** ADR-002 declares "running Claude agent does semantic rerank". The validator flagged ambiguity: who is "the running agent"? Slash-command host model? Sub-agent? `claude -p` non-interactive mode where no agent loop owns the output?
**Decision:** Rerank executes in the **same Claude turn** that invokes the stage template — i.e. the user's primary `/hm:research` / `/hm:plan` / `/hm:spec` conversation. Stage template emits the `!uv run ... memory_retrieve ...` Bash invocation; helper's stdout (the fenced `<memory_candidates>` block) becomes part of that turn's conversation; the same Claude turn reads the fence and surfaces top-6 inline in its reasoning. NO sub-agent dispatch. NO separate API call.
**Consequences:**
- ✅ Works in interactive Claude Code subscription mode (the only supported target env per CLAUDE.md).
- ✅ No cross-process state hand-off; rerank context is the conversation context.
- ⚠️ `claude -p` non-interactive mode behaves identically (the single non-interactive turn does the rerank) — works in CI scripts that pipe a stage prompt.
- ⚠️ If a future stage runs in a hookless context (e.g. invoked from a hook with no LLM loop), the rerank degrades to "show all top-30 candidates without filtering". Acceptable: hookless invocation is not a use case today.
**Rejected alternatives:** Spawn sub-agent for rerank (rejected: extra dispatch cost; no current sub-agent has memory-rerank in scope). Bake top-K into Python with embedding model (rejected: needs external dep + still misses semantic).
**Source:** plan-validator W1.

### ADR-006: No tier-quota in top-K (unified ranking)
**Status:** Accepted (2026-05-19, plan-validator W1)
**Context:** RESEARCH-memory-md-operations §Approach C suggested "6 entries (3 wiki + 3 failures, blended by score)" — a tier quota. Validator flagged this as silently dropped in the draft.
**Decision:** Top-K is **unified** — single ranking across both files. A topic that only matches wiki entries should return up to k wiki entries; same for failures. The tier-quota would cause: e.g. topic "drift detection" with 5 strong wiki hits and 0 failure hits returns 3+3 with weak fillers from failures.
**Consequences:**
- ✅ Quality monotonic — never injects low-score filler to satisfy a quota.
- ⚠️ A topic dominated by one tier may produce unbalanced results (acceptable: tier is metadata, not a user-facing concern).
**Rejected alternatives:** 3+3 quota per RESEARCH (rejected: forces low-score fillers; tier balance is not a quality dimension).
**Source:** plan-validator W1.

## 🏗️ Technical Design

### Current state

In `templates/stages/{research,plan,spec}.md.j2`, "Session Context Loading" instructs:
```
2. Warm tier — Skim `.claude/memory/failures.md` (first 60 lines); search relevant: `rg -F "[fail:" .claude/memory/failures.md`.
3. Warm tier — Skim `.claude/memory/wiki.md` (first 60 lines); search relevant: `rg -F "[wiki:" .claude/memory/wiki.md`.
```

This loads at most ~120 lines (wiki + failures combined first-60-lines), which today represents only the **oldest** ~25% of accumulated entries.

### Affected components

- NEW: `src/harness_maker/memory_retrieve.py` (~200 LoC).
- NEW: `tests/unit/test_memory_retrieve.py` (~150 LoC).
- NEW: `tests/integration/test_memory_retrieve_cli.py` (~50 LoC).
- EDIT: `src/harness_maker/templates/stages/research.md.j2`.
- EDIT: `src/harness_maker/templates/stages/plan.md.j2`.
- EDIT: `src/harness_maker/templates/stages/spec.md.j2`.
- REGEN: `tests/snapshot/*` (3 stage templates' snapshot baselines).

### Module surface

`memory_retrieve.py` public API:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class MemoryEntry:
    tier: str           # "wiki" | "fail"
    category: str       # e.g. "pattern", "design", "test"
    slug: str           # kebab-case
    date: str           # YYYY-MM-DD
    count: int | None   # failures only; None for wiki
    body: str           # entry body verbatim, including trailing whitespace
    source_path: str    # absolute path of source file
    line_offset: int    # 1-indexed line of heading in source file

def parse_entries(text: str, *, tier: str, source_path: str) -> list[MemoryEntry]:
    """Return all entries between @hm:user:entries / @hm:/user:entries markers.

    Duplicate slugs are NOT deduplicated — both surface (with annotation in
    the rendered output below). The wrapup template's "do not duplicate
    sections" rule is enforced upstream by Approach A follow-up PLAN; this
    parser stays permissive so the bug remains visible to readers.
    """

def score_entry(entry: MemoryEntry, topic_tokens: frozenset[str]) -> float:
    """Token-overlap score in [0, 1]. Mirrors relevance._keyword_score."""

def top_candidates(
    entries: Sequence[MemoryEntry],
    topic: str,
    *,
    pre_k: int = 30,
    byte_cap: int = 10240,
) -> list[MemoryEntry]:
    """Lexical pre-filter. Returns up to pre_k entries by score desc.
    Applies byte_cap by dropping lowest-scored entries until total ≤ cap;
    never truncates an individual entry body. If rank-1 alone > cap, that
    single entry is emitted truncated to first 9KB + `[... truncated N bytes]`
    sentinel.
    """

def render_candidates_block(candidates: Sequence[MemoryEntry], topic: str) -> str:
    """Emit the markdown block per §Output Schema below."""

def main(argv: Sequence[str] | None = None) -> int:
    """CLI: --topic X --k N --pre-k M --memory-dir DIR (defaults
    .claude/memory). Always exit 0 (errors → empty block + stderr warning).
    """
```

### Tokenizer / scorer contract (resolves validator W2)

- Import `from harness_maker.relevance import _WORD_RE` (promote to non-private alias `WORD_RE` in `relevance.py` in Phase 1 for use here; original `_WORD_RE` retained as backward-compat alias to keep this PLAN scope tight).
- **Case-folding:** all tokens lowercased before set comparison.
- **Stopwords:** hardcoded conservative English set `{"a", "an", "and", "or", "but", "the", "of", "to", "in", "on", "for", "with", "is", "are", "be", "by", "as", "at", "how", "what", "why", "when", "where", "do", "does", "did", "can", "could", "should", "would", "will", "shall", "this", "that", "these", "those", "it", "we", "you", "i"}` — applied to **topic only** (entry bodies retain all tokens so domain terms like "as" in `as-of-date` still score).
- **Entry body for scoring:** heading line (`## [wiki:X] slug | date`) PLUS body PLUS `count:N` literal if present. Multi-paragraph entries score against the full concatenated body.
- **Tie-breaking** (when score equal): (1) recency desc by date field, (2) slug asc lex. Stable across runs given same input.

### Byte-cap contract (resolves validator W3)

- Cap default = `10240` bytes (10KB) on `render_candidates_block` output.
- Action: drop lowest-scored candidates one-at-a-time until total ≤ cap.
- If rank-1 alone exceeds cap: emit that entry truncated to first 9KB followed by sentinel `\n[... truncated N bytes for byte-cap]\n`. Other candidates skipped.
- **Never** truncate an individual entry mid-body in the multi-candidate case (preserves the `Fix:` / `Pattern guard:` actionable tail).
- Unit tests cover: over-cap by count → drop tail; rank-1 oversized → truncate-with-sentinel; under-cap → no drops.

### Output schema (resolves validator W5)

CLI stdout is the literal block below. The **trailing instruction line is OUTSIDE the closing fence** so the fence body is the data and the line is the directive to the host Claude turn:

```
<memory_candidates topic="<verbatim topic>" k="6" pre_k="30">
## [wiki:pattern] boundary-parse-test-layer | 2026-05-19
<full body verbatim, multi-line OK>

## [fail:design] phantom-key-on-rerender-breaks-idempotency | 2026-05-19 | count:1
<full body verbatim>

## [wiki:gotcha] pipestatus-vs-dollar-question-mark | 2026-05-19 (duplicate of [wiki:pipestatus-vs-dollar-question-mark])
<full body — only present when parse_entries returns >1 entry with same slug>
</memory_candidates>
Surface the top-6 candidates from the above block that are most semantically relevant to the topic. Reference each by its `[<tier>:<slug>]` anchor.
```

Schema invariants:
- Opening tag carries `topic`, `k`, `pre_k` attributes (HTML-attribute syntax; `topic` shell-quoted by CLI). Closing tag bare.
- Each entry begins with `## [<tier>:<category>] <slug> | <date>[ | count:<N>]` heading verbatim from source.
- Duplicate-slug entries get ` (duplicate of [<tier>:<slug>])` annotation appended to heading (preserves visibility of the wrapup duplicate-section bug — see ADR-007 follow-up).
- Per-entry separator: one blank line between heading-body pairs.
- Empty result emits `<memory_candidates topic="X" k="6" pre_k="30">\n(no entries matched)\n</memory_candidates>\n<instruction line>` — exit 0.
- Error result emits same fence with body `(memory_retrieve failed: <reason>; falling back to first-60-lines context)` + stderr warning + exit 0 (never blocks the stage).

### Stage template invocation block

Replaces the existing skim+grep paragraph in each of research/plan/spec stage templates:

```
{% if is_codex %}
Bash("uv run python -m harness_maker.memory_retrieve --topic '<topic>' --k 6 --pre-k 30")
{% else %}
!uv run python -m harness_maker.memory_retrieve --topic "<topic>" --k 6 --pre-k 30
{% endif %}
```

(`<topic>` is replaced with the stage's actual topic variable; codex branch matches the existing `is_codex` Jinja pattern from `[[wiki:codex-is-codex-flag]]`.)

### Data flow

```
stage template ──> !uv run memory_retrieve ──> stdout fence block
                                                   │
                                                   ▼
                                       running Claude turn reads block
                                                   │
                                                   ▼
                              Claude surfaces top-6 by semantic relevance
                                       in its own reasoning text
```

No persistent state. No cache file. Re-parse every invocation (~100KB read is negligible).

## 📝 Implementation Plan

### Phase 1 — `memory_retrieve` module + tests

**Scope (IN):**
- NEW `src/harness_maker/memory_retrieve.py` per §Module surface.
- NEW `tests/unit/test_memory_retrieve.py`:
  - `test_parse_entries_minimal` — single wiki entry roundtrips.
  - `test_parse_entries_with_count` — failures entry preserves count field.
  - `test_parse_entries_duplicate_slug` — two entries same slug both returned (no dedupe) with annotation flag.
  - `test_parse_entries_malformed_heading_skipped` — `## [wiki:` lacking `]` returns 0 entries gracefully.
  - `test_parse_entries_outside_markers_ignored` — content before `@hm:user:entries` or after `@hm:/user:entries` not parsed.
  - `test_score_deterministic_fixed_fixture` — pinned 3-entry fixture, topic="boundary parse", asserts EXACT ordered top-K (`[wiki:pattern] boundary-parse-test-layer`, …). Catches tokenizer / stopword drift.
  - `test_score_case_insensitive` — topic="BOUNDARY" matches entry "boundary".
  - `test_score_stopwords_dropped_from_topic` — topic="how to detect drift" effectively scores against {"detect", "drift"}.
  - `test_score_tie_break_recency_then_slug` — two entries same score → newer date wins; same date → slug asc.
  - `test_render_byte_cap_drops_tail` — fixture of 5 entries totaling 15KB → render returns subset ≤10KB; assertion includes "rank-1 retained".
  - `test_render_byte_cap_single_oversized` — single 12KB entry → truncated to 9KB + sentinel.
  - `test_render_empty_emits_no_entries_matched` — empty `entries` list → fence with body `(no entries matched)`.
  - `test_no_anthropic_import` — `import sys; del sys.modules['anthropic']` (if present); `import harness_maker.memory_retrieve`; assert `'anthropic' not in sys.modules`. Regression guard for failures.md `ship-without-verifying-target-env-credentials`.
- NEW `tests/integration/test_memory_retrieve_cli.py`:
  - `test_cli_roundtrip_via_subprocess` — `subprocess.run([sys.executable, "-m", "harness_maker.memory_retrieve", "--topic", "test", "--k", "3", "--memory-dir", str(fixture_dir)], capture_output=True, text=True, timeout=10, check=True)`; asserts stdout contains `<memory_candidates`, exit 0.
  - `test_cli_missing_memory_dir_graceful` — pass `--memory-dir /nonexistent`; expect exit 0, stdout fence with `(memory_retrieve failed: ...)`, stderr non-empty.
  - `test_cli_real_repo_memory` — run against `/home/noel/harness-maker/.claude/memory` (project's actual memory); topic="boundary parse" → stdout contains `boundary-parse-test-layer` slug (which today's first-60-lines skim never surfaces). This is the **load-bearing acceptance test** — proves the loading problem is fixed.

**Scope (OUT):** No stage template edits. No snapshot regen. No CLAUDE.md updates.

**Risk:** low. Isolated new module; no existing-file mutation.

**Automated exit criterion:**
```bash
uv run pytest tests/unit/test_memory_retrieve.py tests/integration/test_memory_retrieve_cli.py -x
uv run ruff check src/harness_maker/memory_retrieve.py tests/unit/test_memory_retrieve.py tests/integration/test_memory_retrieve_cli.py
uv run ruff format --check src/harness_maker/memory_retrieve.py tests/unit/test_memory_retrieve.py tests/integration/test_memory_retrieve_cli.py
uv run mypy --strict src/harness_maker/memory_retrieve.py
```
All four commands GREEN before Phase 1 is closed.

**Rollback:** `git revert` the single Phase 1 commit. No downstream phase depends until Phase 2 lands.

### Phase 2 — Stage template integration

**Scope (IN):**
- EDIT `src/harness_maker/templates/stages/research.md.j2`:
  - Replace the 3-line "Session Context Loading" block (Hot tier reads + warm-tier first-60-lines skim) — keep the Hot tier (session/<today>) read; replace warm-tier lines 2 + 3 with the single `!uv run python -m harness_maker.memory_retrieve --topic "<topic>" --k 6 --pre-k 30` invocation (with `is_codex` branch).
- EDIT `src/harness_maker/templates/stages/plan.md.j2`: same replacement structure.
- EDIT `src/harness_maker/templates/stages/spec.md.j2`: same replacement structure.
- REGEN `tests/snapshot/*.expected.yaml` baselines for the 3 affected templates **FROM MAIN REPO ROOT** (not from worktree — see failures.md `snapshot-regen-inside-worktree`).
- ADD `tests/integration/test_stage_template_memory_loader.py`:
  - Render each of research/plan/spec templates with a populated memory fixture; assert rendered output contains `uv run python -m harness_maker.memory_retrieve` substring; assert rendered output does NOT contain `first 60 lines` literal.

**Scope (OUT):** No new Python code (the module from Phase 1 is the implementation). No changes to other stage templates (loop / execute / review / wrapup).

**Risk:** medium. Snapshot regen has recurring failure class (`snapshot-regen-inside-worktree` count:6, latest 2026-05-19).

**Automated exit criterion:**
```bash
# From main repo root (NOT from worktree). Order matters per failures.md guidance.
uv run python tests/snapshot/regenerate.py
git diff --stat tests/snapshot/                                  # expect only the 3 stage-template baselines updated
git diff --stat tests/e2e/sandbox*/ tests/e2e/sandbox*/.claude/   # expect ZERO lines — if any sandbox path appears, abort (failures.md snapshot-regen-inside-worktree explicit guard)
uv run pytest -x                                                  # full suite green
uv run ruff check src/ tests/
uv run ruff format --check .                                      # explicit per failures.md wrapup-final-verify-skips-ruff-format-check
uv run mypy --strict src/
```
All commands GREEN AND the `git diff --stat tests/e2e/sandbox*/` shows zero output before Phase 2 is closed.

**Post-merge manual smoke (advisory, NOT a phase-2 gate):**
After Phase 2 lands on main: in a fresh Claude Code session, run `/hm:research "boundary parse test layer"` and verify the assistant's reasoning explicitly references `[wiki:pattern] boundary-parse-test-layer | 2026-05-19` (wiki.md line 258 — invisible to today's first-60-lines loader). If absent, file a follow-up issue; do NOT block.

**Rollback:** `git revert` Phase 2 commit. Phase 1 module remains usable as standalone CLI; stage templates revert to first-60-lines behaviour without losing the helper.

## 🧪 Testing Strategy

- **Unit** — `tests/unit/test_memory_retrieve.py` covers parser correctness, scorer determinism, byte-cap, no-anthropic-import. Mock-free (pure functions over in-memory strings).
- **Integration** — `tests/integration/test_memory_retrieve_cli.py` covers CLI roundtrip via `subprocess.run` from a different cwd (catches the "import works but CLI from different dir fails" class per CLAUDE.md §"Integration 경계 한 줄 테스트"). Real-memory test asserts the load-bearing acceptance (recent entry actually surfaces).
- **Snapshot** — Phase 2 regenerates 3 baselines from main repo. Existing snapshot framework catches drift.
- **E2E** — Phase 2 manual smoke (advisory). Not in pytest because /hm:research requires a live LLM turn.
- **No new external API dependencies** → no `INTEGRATION=1` env gate.

## ⚠️ Risks & Mitigation

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Lexical scorer too weak; pre-filter drops actually-relevant entry before Claude rerank | medium | pre-k=30 (≈ 1/3 of current corpus of 97 entries); fixed-fixture top-K test asserts known-relevant entry in top-30 |
| R2 | Token cost regression from oversized candidate block | medium | Byte cap 10KB with hard contract (§Byte-cap contract); 2 unit tests assert both over-cap-by-count and single-oversized behaviours |
| R3 | Snapshot regen pollutes worktree paths / sandbox fixtures (failures.md snapshot-regen-inside-worktree count:6) | high | Phase 2 exit criterion explicitly: regen FROM MAIN REPO ROOT; `git diff --stat tests/e2e/sandbox*/` must show zero lines; failure aborts phase |
| R4 | Replays `ship-without-verifying-target-env-credentials` if implementer imports anthropic in memory_retrieve.py | high | Unit test `test_no_anthropic_import` asserts the module does not pull anthropic transitively |
| R5 | Stage template divergence — three templates' invocation lines drift | low | All three replacements identical text; integration test renders each and asserts exact-substring match |
| R6 | Wrapup verification skips `ruff format --check .` (failures.md count:2) | medium | Both phase exit criteria include `ruff format --check .` as a separate command, not bundled with `ruff check` |
| R7 | Duplicate-slug entries (real today: `snapshot-regen-inside-worktree` × 2) cause confusion in retrieval output | low | Parser surfaces both with `(duplicate of [<tier>:<slug>])` annotation; preserves visibility for Approach A follow-up; explicit unit test |
| R8 | `claude -p` non-interactive mode behaviour drift if no LLM loop owns rerank | low | ADR-005 documents: single non-interactive turn does the rerank; degrades gracefully to show all top-30 if no LLM context |

## ✅ Success Criteria

- ✅ Phase 1 exit criterion commands all green.
- ✅ Phase 2 exit criterion commands all green, including `git diff --stat tests/e2e/sandbox*/` showing zero lines.
- ✅ `import harness_maker.memory_retrieve` does not bring `anthropic` into `sys.modules` (regression guard).
- ✅ Existing `tests/integration/test_memory_retrieve_cli.py::test_cli_real_repo_memory` returns ≥1 candidate that today's first-60-lines skim does NOT surface (e.g. `boundary-parse-test-layer` at wiki.md:258).
- ✅ Wrapup verification runs **both** `uv run ruff check src/ tests/` AND `uv run ruff format --check .` before commit.
- ✅ Post-merge manual smoke: `/hm:research boundary parse test layer` in a fresh session references the `boundary-parse-test-layer` wiki entry by anchor (advisory; if absent → follow-up issue, not phase-2 block).

## 🔍 Plan Validation

**plan-validator outcome:** `NEEDS_REVISION_RESOLVED`.

Critique resolution:
| Critique | Severity | Resolution |
|---|---|---|
| W1 — Rerank execution surface ambiguity | warning | Added ADR-005 (rerank in stage-template-hosting Claude turn) |
| W1 — Tier-quota silently dropped from RESEARCH | warning | Added ADR-006 (no tier-quota; unified top-K) |
| W2 — Lexical scorer under-specified | warning | §Tokenizer/scorer contract — import `_WORD_RE`, lowercase, stopword list pinned, tie-break = recency → slug asc; fixed-fixture unit test enforces deterministic ordering |
| W3 — Byte-cap mechanism hand-wavy | warning | §Byte-cap contract — drop lowest-scored until ≤10KB; never truncate mid-body; rank-1 oversized → first 9KB + sentinel; 2 dedicated unit tests |
| W4 — Failure-mode integration partially name-dropped | warning | R3 reworded to `git diff --stat tests/e2e/sandbox*/` probe (concrete, runnable); ruff-format-check bound to both phases' exit criteria, not §Success Criteria advisory prose |
| W5 — Output contract / fence schema unspecified | warning | §Output schema — literal example with attribute syntax + instruction line OUTSIDE closing fence + empty-result + error-result schemas |
| W6 — Phase 2 exit mixes manual smoke | warning | Phase 2 split: automated exit (gates phase) vs post-merge manual smoke (advisory, not a gate) |
| S1 — Non-Goals missing | suggestion | §🚫 Non-Goals added with explicit OUT list |
| S2 — Parser duplicate-slug behaviour unspecified | suggestion | ADR-006 / §Module surface — parser does NOT dedupe; both entries surface with `(duplicate of [<tier>:<slug>])` heading annotation; unit test `test_parse_entries_duplicate_slug` |

Validator re-run: not required (NEEDS_REVISION resolved without architectural change; all warnings resolved in PLAN body, no second validator pass per Step 4 procedure).
