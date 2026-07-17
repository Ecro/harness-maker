---
type: research
task_slug: failure-memory-recurrence-dedup
status: complete
created: 2026-07-04
tags: [harness-maker, research, memory, dedup, wrapup, recurrence]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: []
summary: "Recurrence dedup is dead: slug is an LLM-chosen key with no read-back, and design-thrash never enters the failure taxonomy"
---

# RESEARCH — Failure/Wiki memory: why recurrence counts are stuck at 1

## 🎯 Recommended Direction

The `count≥3` escalation never fires because failure dedup keys on an **LLM-invented
slug with zero read-back of existing entries**, and the specific recurrences the user
saw (boot-marker/iptables/cron oscillation) are **design-thrash that the failure
taxonomy does not even recognize as a "failure that emerged this work unit"** — so they
are never recorded, let alone deduped. Two independent gaps stack:

- **Gap 1 (dedup):** the same real failure recorded twice gets two different slugs →
  two `count:1` rows. Highest-leverage fix = a **search-before-write** sub-step in
  `wrapup` Step 5.2 that reuses the existing `memory_retrieve` helper to find a
  semantically-matching prior slug and pass *that exact slug* so the CLI's `count++`
  path actually fires.
- **Gap 2 (non-recording):** oscillation ("we flipped the boot-marker strategy 5×") is
  a git-churn signal, not a discrete symptom, so it never enters `failures.md`. Fix =
  a **git-churn oscillation detector** + broadening the failure taxonomy to include
  "design thrash".

Gap 1 alone will NOT fix the user's reported case — that class of recurrence never
reaches the log to be deduped. Both are needed. This is informational; `/hm:plan` makes
the binding call.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (memory subsystem code
path) + **Risk** (silent-dead feature). `--deep` not set — the topic was already
sharply scoped by the user's own diagnosis.

## Evidence — the mechanism is confirmed dead in `~/edge_testfarm_os`

| Signal | Observed |
|--------|----------|
| `failures.md` entries | 19, **every one `count:1`** (`grep -oE "count:[0-9]+"` → `19 count:1`) |
| `pending-proposals.md` (the `count≥3` output) | **does not exist** — escalation has never fired in the project's entire history |
| git recurrence: **iptables** recovery strategy | ≥6 commits (`iptables flush 강화`, `iptables disable blocking gate`, `preflight iptables+reboot`, `rate-limit 재부팅 후 자동 복원 방지`, `serial iptables fix`, `reboot 후 SSH/iptables 복구 강화`) |
| git recurrence: **boot marker** strategy | 3+ commits (`align boot_smoke spec with single marker`, `simplify boot_smoke marker`, `replace serial app-ready marker with SSH ps + watchdog`) |
| git recurrence: **cron** time | 5+ commits (`12:30 → 15:30`, `remove duplicate 12:15`, two crontab-conflict merges, `15:35 analysis`) |
| **SSH/serial 3-stage escalation** | implemented **twice** (`e4ff570` core + `e85c407` projects) — a reimplementation, i.e. re-derived not recalled |
| `schedule_runner.py` recovery churn | 71 commits touch the file |

Verdict: memory is **accumulating in volume** (wiki.md ~30 rich entries, failures.md 19
entries, 13 session files — all growing each wrapup) but the **recurrence-detection
sub-system is inert**. "쌓이고 있나" = yes. "효과있게" (for recurrence/escalation) = no.

## 🛠️ Approaches Found

### A — Retrieval-augmented slug reuse (search-before-write)

| Field | Content |
|-------|---------|
| Approach | Before `wrapup` Step 5.2 writes, run `memory_retrieve` over existing `failures.md` slugs+bodies; if a match ≥ threshold, pass that **exact** slug so the CLI's `count++` path fires. |
| Assumption | The dedup key (`memory_md._upsert` line 213 `s == slug`) is only reused if the LLM independently reproduces the identical kebab string — which never happens without a lookup. |
| Evidence | `memory_retrieve.py` already exists and is already called by the `research` stage's warm-tier load — reusable infra, no new dependency. `wrapup` Step 5.2 currently says *"for each **new** failure pattern"* — priming for new-slug creation, with **no read-back instruction**. |
| Trade-off | LLM may over-merge (collapse distinct failures) or under-merge (miss a paraphrase). Mitigate with a conservative threshold + surface the candidate to the user. |
| Compatibility | High — pure template change + reuse of existing helper. Fits project ethos ("LLM judgment over rules"). |
| Risk | low–medium |

### B — Stable problem-identity slugs (coarser buckets)

| Field | Content |
|-------|---------|
| Approach | Change the slug convention from symptom-derived (`spec-string-threshold-quote-mismatch`) to a coarse **problem family** (`ssh-recovery-layering`, `boot-marker-strategy`). |
| Assumption | Fewer, stabler buckets dedupe naturally even without perfect search. |
| Evidence | The 19 existing slugs are all hyper-specific single-incident symptoms — structurally un-collidable. |
| Trade-off | Too coarse loses actionable signal; requires taxonomy discipline the LLM won't hold without a rubric. |
| Compatibility | Medium — convention nudge; complements A, weak alone. |
| Risk | medium |

### C — Git-churn oscillation detector (catches the class A can't)

| Field | Content |
|-------|---------|
| Approach | A detector that mines `git log` for oscillation — same file/region reverted repeatedly, same config value (cron time, iptables rule, marker string) flipped back and forth — and surfaces "design thrash" **independent of the failure log**. |
| Assumption | The user's own diagnosis: the recurrence is visible in git history, not in discrete failure symptoms. |
| Evidence | Confirmed above: iptables 6×, cron 5×, boot-marker 3×, escalation reimplemented — **none of which is a "failure that emerged this work unit"** per Step 5.2's qualifier list, so none was ever recorded. |
| Trade-off | New Python detector + heuristics for "oscillation"; git-history mining is noisy. |
| Compatibility | Medium — new module, but orthogonal to A/B. This is the **only** approach that catches Gap 2. |
| Risk | medium |

### D — CLI-side fuzzy dedup (deterministic merge)

| Field | Content |
|-------|---------|
| Approach | Make `upsert_failure` itself compare the new body vs existing entries (similarity/LLM call) and auto-merge above a threshold. Moves dedup from LLM discipline into the write path. |
| Assumption | Dedup is too important to leave to per-session LLM memory. |
| Evidence | `_upsert` today is exact-match only (`s == slug`); the Python layer currently owns "type contract + storage + safety rails" only (CLAUDE.md), not judgment. |
| Trade-off | False merges are hard to reverse (body is REPLACED on match — line 228 — so a wrong merge destroys the other entry's context). Pushes judgment into the Python layer, against project ethos unless it dispatches to an LLM/codex call. |
| Compatibility | Low–medium — heaviest option; keep as fallback if A proves too unreliable. |
| Risk | medium–high |

**Synthesis:** A (primary — directly repairs dedup, reuses existing infra) + C (covers
the design-thrash class that never reaches the log). B is a convention nudge that raises
A's hit-rate. D is the heavyweight fallback. Main impact is **internal maintainer value**
(the recurrence→escalation→proposal pipeline is the harness's self-improvement loop; it
is currently a no-op for every consumer project, not just edge_testfarm_os).

## ⚠️ Pitfalls

- **This is the canonical "absent-case = feature black hole"** (user global learning
  2026-06-08, failures count:8). The `count++` feature ACTIVATES only on exact-slug-match;
  the absent case (no prior identical slug) silently creates a fresh `count:1` with **no
  attempt to find the prior**. The feature never fires for the very inputs it exists for.
- **The lock guarantees write-safety, not semantic dedup.** `memory_md` runs every write
  under `exclusive_lock` (H1 fix) so concurrent sessions don't clobber — but two sessions
  recording the same problem under different slugs BOTH succeed → two `count:1` rows. Do
  not mistake the lock for dedup.
- **On a real match, the body is REPLACED, not merged** (`_upsert` line 228). Even when
  count++ fires, prior-occurrence context is overwritten; only the integer survives. Any
  fix that raises the match-rate should also decide what to do with accumulated bodies.
- **`count:2` in the wrapup template is a hardcoded joke, not data** (`ruff-format-not-in-
  local-verify-pass count:2`). Do not read it as evidence the mechanism ever worked.
- **Design oscillation is invisible to the Step 5.2 rubric.** "We keep changing our mind
  about X" is not in the qualifier list ("incorrect API usage, wrong syntax, build
  failures, tool mistakes, workflow violations"). Broadening the taxonomy is part of Gap 2.

## ❓ Open Questions (for `/hm:plan`)

1. **Match threshold + arbiter:** who decides "same failure"? LLM rerank in wrapup (A), a
   codex second-opinion, or deterministic similarity (D)? What confidence gate avoids
   false merges?
2. **Body-on-match policy:** replace (current), append-occurrence-log, or keep-first?
   Should count++ also bump the date or preserve first-seen (current behavior)?
3. **Oscillation heuristic (C):** what defines "thrash" — N reverts of the same file
   region within a window? A config value flipping back to a prior value? Needs a concrete,
   testable predicate (the global learning demands an absent-case test).
4. **Where does escalation surface** now that `pending-proposals.md` is proven to never be
   created — should `/hm:health` assert the recurrence pipeline is live (positive
   smoke-test), the way it does for other silent-degradation classes?
5. **Retroactive backfill:** should a one-shot pass re-slug the 19 existing edge_testfarm_os
   entries into families, or is the fix forward-only?
6. **Scope:** fix lives in harness-maker templates/code (ships to all consumers), not in
   edge_testfarm_os. Confirm this is a harness-maker work unit.

## 📚 Sources

- Internal code: `src/harness_maker/memory_md.py` (`_upsert` lines 151–234, slug-exact
  dedup at 213, count++ at 224, body-replace at 228).
- Internal template: `src/harness_maker/templates/stages/wrapup.md.j2` Step 5.2 (349–369,
  no read-back), Step 5.3 escalation (371–382).
- Internal infra: `src/harness_maker/memory_retrieve.py` (existing lexical+rerank helper).
- Live data: `~/edge_testfarm_os/.claude/memory/failures.md` (19× count:1), absent
  `pending-proposals.md`, `git log` oscillation evidence (iptables/boot-marker/cron).

## 🔗 Related Internal Docs

- Global learning `[fail] absent-case = feature black hole` (2026-06-08, count:8) — this
  research is a textbook instance.
- `[[project_review_grade_gate]]`, CLAUDE.md "무언가를 고치기 전에 필수 체크리스트" item 6
  (양방향 매퍼) and item 1 (사용자 상태 보존 계약).
