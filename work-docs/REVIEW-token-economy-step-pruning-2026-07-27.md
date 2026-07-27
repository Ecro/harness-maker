---
type: review
task_slug: token-economy-step-pruning
status: APPROVED
created: 2026-07-27
scope: PLAN Phase 1 only (meter correction) — Phases 2-4 not yet implemented
reviewers_invoked: [code-reviewer, security-reviewer, codex]
rounds: 3
human_review_needed: true
consensus_method: cross-check
voter_pool: 3
consensus_threshold: 2
second_opinion_results:
  - model: codex
    status: invoked
    rounds: 2
  - model: antigravity
    status: skipped
    reason: "exit 1: Error: timeout waiting for response"
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/unit/test_cache_diagnostics_transcript.py
    - tests/unit/test_economics_review_fixes.py
    - tests/unit/test_economics_review_round2.py
    - tests/unit/test_cache_minimums_per_model.py
    - src/harness_maker/templates/skills/ai-readiness-rubric/SKILL.md.j2
  scenario_misses: []
  task_slug: token-economy-step-pruning
  computed_at: 2026-07-27
---

# REVIEW — token-economy-step-pruning, Phase 1

## 🎯 Round 1 Summary

Reviewed the Phase 1 diff (meter correction) after all four Phase D gates —
`ruff check`, `ruff format --check`, `mypy --strict`, full `pytest` — were green.

**Initial grade: B** (0 consensus-passed P0, 2 consensus-passed P1).
`human_review_needed` was raised on three `manual-only` P1 findings.

Eleven distinct defects were found in code that had passed every automated gate.
Five of them were P1. Three of the five were single-source (`manual-only`) and
therefore not auto-fix-eligible; each was independently re-verified against the code
by the stage orchestrator before being fixed, and is recorded as such below rather
than as a consensus result.

**One voter degraded.** `antigravity` returned `status: skipped` on round 1
(`exit 1: Error: timeout waiting for response`) and was not retried. The voter pool
was therefore 3, not 4. Threshold stayed at K=2 (ADR-006), so consensus remained
reachable — but every finding below carries one fewer independent chance of
corroboration than the configuration intends, and the two `[2/3]` clusters would
have been `[2/4]` had it responded.

## 🔍 Drift Findings

**Result: `scope_violation`** — five files outside the PLAN Phase 1 scope list.

| File | Assessment |
|---|---|
| `tests/unit/test_cache_diagnostics_transcript.py` | Regression fallout: it asserted the window-level threshold semantics ADR-012 replaces. Defensible, but the PLAN named only `test_cache_diagnostics.py`. |
| `tests/unit/test_economics_review_fixes.py` | Same — asserted `resolve_model_family("claude-opus-5") == "opus"`, true only while no point-release key existed. |
| `tests/unit/test_economics_review_round2.py` | Same — the haiku output rate. |
| `tests/unit/test_cache_minimums_per_model.py` | New module; PLAN said the AC tests would live in `test_cache_diagnostics.py`. `test_ids` in both SPEC files were repointed to match reality. |
| `templates/skills/ai-readiness-rubric/SKILL.md.j2` | Added during round 2 — the rendered rubric still described the retired classifier. Genuinely outside Phase 1's stated scope; recorded rather than hidden. |

**Incomplete phase (resolved during round 2).** `ai_readiness.py` and `improvement.py`
were in Phase 1's scope-in list and were initially left unchanged, on the orchestrator's
judgment that they only format `primary_failure` into a string. Round 1 review showed
that judgment was wrong in one respect: `improvement.py` hardcodes `priority="P1"`, so
the new `miss_unknown_model` mode raised a P1 user action for a gap in *our* table.
Demoted to P2 in round 2. `ai_readiness.py` still needs no change (it reads only
`cache.score`), verified by reading all three call sites.

## ✅ Consensus Findings

### P1 — haiku family row edited in place `[2/3: codex + code-reviewer]`

`economics.py`. The `haiku` row carried 0.25/1.25, which is the **published Haiku 3
rate**, not a stale value. Overwriting it with Haiku 4.5's 1/5 repriced every older
Haiku turn 4x — the same class of error this table exists to remove, in the opposite
direction, and in violation of the discipline stated 15 lines above it for `opus`.

**Fixed:** `haiku` restored to 0.25/1.25/0.025/0.3/0.5; `haiku-4-5` added at 1/5.
Two tests that had been "corrected" in the wrong direction during Phase 1 were
reverted — their failure had been a *symptom* of this defect, and the orchestrator had
adjusted the expectations to match the defect rather than investigating.

`test_pre_4_5_haiku_still_prices_at_the_legacy_rate` was added, asserting the family
row directly. The pre-existing `price_for("claude-haiku-4-5").input == 1.0` assertion
could not catch this: in the broken world that id resolves to the overwritten family
row and still reads 1.0.

### P1 — the price table and the threshold table disagreed on which models exist `[2/3: security-reviewer + code-reviewer]`

`PRICE_TABLE` priced `opus-4-5`; `_MIN_CACHEABLE_PREFIX` did not carry it, nor
`sonnet-4-5`. A project on either model resolved to `None` on every turn,
`miss_unknown_model` became its primary failure, and `improvement.py` raised a **P1
action item instructing the user to edit a private symbol inside an installed
package**.

**Fixed in two stages, the first of which was wrong.** Round 2 added both ids at 1024
and a gate asserting every priced point release has a minimum. codex and code-reviewer
independently rejected that: there is no release-specific published minimum for either
id, so 1024 was an inherited guess, and the new gate *structurally required* inventing
it — inverting the module's own contract and violating a SPEC clause written to forbid
exactly this. The rows were removed and the gate replaced by its inverse
(`test_a_priced_model_with_no_published_minimum_refuses_to_guess`). The remediation
prose was reworded to be user-actionable, and the action item demoted to P2.

Recorded in code: *a wrong rate yields an approximate dollar figure; a wrong minimum
yields a confident verdict and a remediation the user cannot act on.* The two tables
are allowed to disagree about which models they can speak to.

### P2 — transcript-derived model ids interpolated into user-facing prose `[2/3: codex + code-reviewer]`

Bounded by `_render_model_list` (5 ids x 64 chars, `(+N more)`, backticks neutralised).

**Partially refuted by a third voter.** `security-reviewer` traced every sink and found
`economics_source._clip` already strips non-printables and caps ids at 64 chars at
ingestion, and that no shipped renderer emits the field as markdown. Its explicit
verdict was **no security finding** — the trust boundary is unchanged in substance,
since `TurnRecord.model` already reaches an LLM's context on every `/hm:metrics`. The
fix is defence in depth, not a closed hole.

## 📝 Manual-Only Findings

Single-source, therefore not auto-fix-eligible. Each was re-verified against the code
by the orchestrator before being acted on.

| Sev | Source | Finding | Disposition |
|---|---|---|---|
| P1 | code-reviewer | `miss_unknown_model` early-**returned** from the threshold branch, ahead of the first-turn / TTL / invalidation branches — so an unknown minimum silently disabled three tests that do not depend on it, and `_detect_ttl_regression` (which counts only `miss_ttl`) could never fire for such a window | Confirmed; branch moved to the elimination slot |
| P1 | codex | Window truncation (`entries[-window_turns:]`) ran **before** the TTL tier lookup, so a 1h write just outside the window was invisible and the tier silently fell back to 5m — fabricating `miss_ttl` for turns inside their actual TTL | Confirmed; window is now a start index, not a slice |
| P1 | code-reviewer | `thresholds_applied` / `unknown_models` / the prefix average accumulated over **every** entry before classification, so the remediation number was computed from turns that did not fail | Confirmed; all now accumulate inside the classification dispatch |
| P1 | code-reviewer (round 2) | The round-1 fix above traded a total swallow for a **gap-length-dependent** one: an unknown-model turn whose gap exceeded the *assumed* 5m tier was reported as a confident `miss_ttl` with "keep sessions tighter" — although nothing had ever been cached in that session, so nothing could expire | Confirmed; `unknown_threshold_turns` now tracks the fact independently of the classification and appends an incompleteness caveat to **any** primary |
| P1 | code-reviewer (round 2) | The gate written for the fix above was **invariant over the ordering it claimed to pin** — both fixture turns carried cache-write tokens, so the creation-gated unknown branch could not fire in any variant | Confirmed; `w5m=1` dropped from the second turn |
| P1 | code-reviewer (round 2) | A comment added by the fix asserted that `report.unknown_models` / `fallback_priced_turns` surface family-fallback pricing. They do not: a future `claude-opus-6` matches `"opus"`, so `used_fallback` stays False and the turn is priced at 15/75 with **no diagnostic trace** — bit for bit the recurrence path of the bug being fixed | Confirmed; claim corrected rather than implemented (fallback policy is ADR-002 R8, explicitly out of scope) |
| P2 | codex | `hit_rate >= 80` early return reported "Cache healthy / No action needed" while unknown-minimum turns were present | Confirmed; guarded |
| P2 | security-reviewer | Empty `session_id` fail-open — the producer collapses a missing sessionId to `""`, so all such turns compared EQUAL and borrowed each other's TTL tier | Confirmed; fails closed to 5m |
| P2 | codex (round 2) | The round-1 complexity refutation no longer held after the window fix: the tier scan now walked the **full history** per window entry, O(window x history), and O(N^2) in the uncapped mode over transcripts with no turn-count bound | Confirmed; replaced by a single forward pass, O(N) |
| P2 | code-reviewer (round 2) | The window's first turn was reported `miss_first` even though its predecessor was now retained — the tier lookup crossed the boundary but the gap arithmetic did not | Confirmed; `prev` seeded from `entries[window_start - 1]` |
| P2 | code-reviewer (round 2) | The rendered `ai-readiness-rubric` SKILL.md still described the retired classifier (no `unknown_model`, hard-coded ">5min") — the text the L2 judge reads | Confirmed; updated |
| P3 | codex | `>= 1` where the contract specifies an exact count | Pinned to `== 2` + `miss_first == 1` |
| P3 | codex, code-reviewer (P2) | Version/date assertions were one-shot `!=` relations satisfied by `PRICE_TABLE_VERSION = "banana"` | Pinned to values + `date.fromisoformat` |

## 🤝 Disagreements

| Location | Positions | Resolution |
|---|---|---|
| `_ttl_for_entry` complexity | codex round 1: P2 quadratic. code-reviewer round 1: **refuted** — bounded by `window_turns=50`, ~5000 lookups | code-reviewer was right *at the time*; the orchestrator's own window fix then invalidated the refutation, and codex round 2 caught that. Fixed. |
| Model ids in prose | codex + code-reviewer: P2. security-reviewer: **no finding**, with a full sink trace | Both retained. Fixed as defence in depth, with the refutation recorded so the fix is not read as closing an exploitable hole. |
| haiku severity | codex P1, security-reviewer P2, code-reviewer P1 | Not bridged across tiers (Step 4c). The P1 pair reached consensus; the P2 is recorded independently. |
| `thresholds_applied` population | code-reviewer P1, codex P2 | Not bridged. Treated as the P1. |

## 🔍 Round 3

One voter (`code-reviewer`). Sixteen fixes had been applied since anyone last looked,
including a `ValueError` crash the fixes themselves introduced and a control-flow
rewrite. All four gates were green throughout — as they had been before rounds 1 and 2.

**Verified clean** (the reviewer did the derivations, not just an opinion): the
`_ttl_tiers` forward pass is equivalent to the backward scan it replaced, hand-checked
across six cases including "a turn's own write is not visible to itself"; no other
guard/`max()` emptiness disagreement exists; `hit_rate`/`sample_size`/`score` are
unaffected by the `prev` seeding.

**Found: 2 P1 + 3 P2, all `manual-only` (single voter).** All confirmed against the
code and fixed:

| Sev | Finding | Disposition |
|---|---|---|
| P1 | The no-primary caveat branch wrote to a field **no consumer reads** — `improvement._extract_layer3_actions` returns `[]` on `primary_failure is None`, which is exactly the branch it was built for. The gate asserted on `diag.remediation`, one layer inside the last reader. Its evidence read literally `"Cache healthy: 0% hit rate over 1 turns."` with `score == 0` | [ADR-019](../work-docs/PLAN-token-economy-step-pruning.md) — apparatus deleted |
| P1 | The `miss_unknown_model` remediation instructed an action the module **refuses to perform** ("report the id so it can be added", while ADR-002's follow-up deliberately removed those rows and will not re-add them). Amplified by two other fixes interacting: the shortcut became permanently unreachable for those users, so every run reported an incomplete diagnosis with no achievable remedy | ADR-019 — remediation states no action is available |
| P2 | `_detect_ttl_regression` never got round-2's `prev` seeding, so the two paths classified the same turn differently and the file's own docstrings contradicted each other. Separately: `ttl_regression` has **no consumer anywhere**, and round 2 added `window_start` plumbing plus a duplicate full `_ttl_tiers` pass to feed it | Seeded; duplicate pass removed |
| P2 | The replacement gate's docstring claimed a property broader than it verifies — substring matching means `claude-opus-5-1` still inherits 512 | Docstring narrowed; limitation recorded in code, with why tightening only this matcher is rejected (shared contract, ADR-002 locked) |
| P2 | The `sonnet-4-6` retention rationale became false in the same change that wrote it | Corrected |

Two ADRs were promoted out of this round: **ADR-018** (R8 gets an observability signal
— the previously-claimed safety net did not exist) and **ADR-019** (the unknown-minimum
case reports a fact and stops there).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 11        | —   |
| 2         | B     | 10            | 0         | 6 (5 introduced by round-1 fixes) |
| 3         | A*    | 6 + 1 (R8)    | 0         | 5 (all introduced by round-2 fixes) |

**Across three rounds, 22 findings. Eleven of them were defects introduced by the
previous round's fixes.** Every one of those repairs was verified green by
`ruff check` + `ruff format --check` + `mypy --strict` + the full `pytest` suite before
the next round found the new hole. That is the load-bearing observation in this report:
on this surface, "fix applied, gates green" carried no information about correctness.

Final grade: **A\***
Iterations used: 3 / 3 (exhausted)
Status: APPROVED
human_review_needed: **true**

> **\* The letter is not evidence of quality.** Grade counts `consensus-passed` P0/P1
> only, and round 3 ran with a **single voter** — nothing it found could reach consensus
> by construction, so every finding landed `manual-only` and none of them lowered the
> letter. An A obtained this way says "no two voices agreed on a severe finding",
> which in a one-voice round is a tautology. Rounds 1 and 2 each produced consensus P1s
> from the same codebase.
>
> Three concrete reasons to treat this as unfinished:
> 1. **Round-3's fixes plus ADR-018's new feature are unreviewed.** Rounds 1 and 2 each
>    found that the previous round's repairs introduced new P1s; there is no basis for
>    assuming round 3 broke the pattern.
> 2. **The review budget is exhausted** (3/3), so the loop cannot self-correct further.
> 3. **`antigravity` was never retried** after its round-1 timeout. The configured pool
>    is 4 voices; rounds 1-2 ran with 3 and round 3 with 1.
>
> Open, deliberately: the substring-matcher limitation (`claude-opus-5-1` inherits 512),
> `sonnet-4-6: 1024` and `sonnet-5: 1024` carry no citation and no direct assertion, and
> `ttl_regression` remains a field with no reader.
