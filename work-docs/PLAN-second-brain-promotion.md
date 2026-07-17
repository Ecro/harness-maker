---
type: plan
task_slug: second-brain-promotion
status: complete
created: 2026-05-28
tags: [harness-maker, plan, second-brain, obsidian, wrapup, promotion-pipeline]
spec: "[[SPEC-second-brain]]"
interview_rounds: 4
adrs: 6
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Wire a wrapup promotion Step so local memory escalates to Obsidian Second Brain (fixes empty vault)"
---

## 🎯 Executive Summary

**TL;DR:** The Second Brain vault is empty not because the module or config is broken (both were fixed in PLAN-second-brain-fix, 2026-05-27), but because **no concrete trigger ever writes to it**. The only write path is an *advisory floating preamble* in the wrapup stage, deliberately locked as "Advisory" by ADR-006 of PLAN-second-brain-write-failure. The LLM running wrapup completes the concrete numbered Step 5 (local `.claude/memory/`) and silently drops the floating advisory every time. This PLAN adds a **promotion Step** to wrapup that escalates qualifying local-memory entries into the Obsidian Second Brain, reversing ADR-006.

**What:** Add `second_brain promote` (Python idempotency safety rail) + a numbered wrapup **Step 5.6** that evaluates the just-written local-memory entries, LLM-judges which are *cross-project durable*, and promotes those to Obsidian notes. Re-render `.claude/`, document the model, bump version.

**Why:** Local `.claude/memory/` (wiki/failures/session) and Obsidian Second Brain are two parallel memory systems. Only the local one is wired as a concrete step, so only it fills. The vault has received **zero** notes despite being enabled for weeks.

**Key Decisions:**
- ADR-001: Reverse ADR-006 — wrapup Second-Brain write becomes a **must-evaluate numbered Step**, not advisory.
- ADR-002: **Promotion-pipeline** role model — local = project working memory; Obsidian = curated cross-project durable knowledge.
- ADR-003: Promotion filter is **LLM-judged "cross-project durable"**, not a deterministic count threshold.
- ADR-004: `second_brain promote` CLI is the **idempotency / path safety rail** — Python owns deterministic filename + link-back + dedup; LLM owns content + judgment.
- ADR-005: Promotion fires **only at wrapup** (no hook, no standalone command); the "wrapup rarely run" gap is an accepted, documented limitation.
- ADR-006: Step 5.6 emits a **promotion receipt** (`promotion evaluated: N candidates, M promoted`) so silent under-promotion (R1×R3) is observable and structurally assertable.

**Estimated impact:** ~2 source files (`second_brain.py`, `cli.py`), 1 template (`wrapup.md.j2`), full `.claude/` re-render, CLAUDE.md + CHANGELOG, ~2 test files, 5-file version bump.

## 📚 Prior Work

- **`work-docs/PLAN-second-brain-write-failure.md` (2026-05-17)** — fixed the loader crash, smart vault check, folder enforcement, graceful degrade. **ADR-006 of that PLAN explicitly locked wrapup write as "Advisory"** and rejected Strong/Mandatory gates (synthetic-note fear). This PLAN's ADR-001 supersedes it.
- **`work-docs/PLAN-second-brain-fix.md` (2026-05-27)** — fixed config (`vault_path`, `folders`), removed dead `trusted_allowlist`, wired `required_frontmatter`, added search scoring + warn-loud UX. Made the module **work** but never wired an **automatic trigger** — its success criteria only verified the CLI `write` works *manually*.
- **Evidence gathered this session:**
  - `99_HM/harness-maker/` vault folder exists, is valid Obsidian, and is **empty** (0 files).
  - Local `.claude/memory/` is heavily used — `failures.md`/`wiki.md` updated 2026-05-28; daily session logs through 2026-05-28.
  - The **only** `second_brain write/append` reference in the entire rendered `.claude/` is the wrapup advisory preamble (`wrapup.md:55-56`, mirrored into `exec-rev-wrap*.md`). No hook writes. plan/research/review only `search`.
  - Only 3 of the last 40 commits are wrapup/autoloop commits — `/hm:wrapup` is rarely run (most work is manual/quick commits). Compounds the empty vault (root cause #4).
- **Existing precedent to mirror:** wrapup **Step 5.3** (failure `count >= 3` → `pending-proposals.md`) is the established "threshold-triggered escalation" pattern. The promotion Step is its sibling, escalating to the vault instead of a local proposal file.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | 1 | Role relationship | Architecture | local `.claude/memory/` vs Obsidian Second Brain role | **승급 파이프라인 (promotion pipeline)** | local = working memory; Obsidian = curated cross-project durable; wrapup promotes qualifying entries | ADR-002 |
| 2 | 1 | Write trigger | Contract | how to make writes actually fire (ADR-006 revision) | **wrapup 구체적 번호 Step** | floating advisory → numbered must-evaluate step; write only if content qualifies | ADR-001 |
| 3 | 2 | Promotion mapping | Contract | which local source → which note_type | **전체 매핑 (full mapping)** | failures→failure, ADR→decision, prefs→preference, session decisions→decision; journal/project/reference optional | ADR-002 |
| 4 | 2 | Promotion filter | Failure handling / Risk | when does a local entry qualify | **LLM 판단 'cross-project durable'** | wrapup LLM judges per-candidate "valuable to other projects/future?"; dedup via link-back invariant | ADR-003 |
| 5 | 2 | Folder structure | Architecture | single project-namespaced folder vs shared/tagged | **현행 99_HM/harness-maker/ 유지** | project-namespaced; cross-project search via Obsidian directly; validator-compliant | (status quo) |
| 6 | 3 | Fire-point gap | Risk tolerance | promotion only at wrapup but wrapup rarely run | **wrapup-only 수용 + 한계 문서화** | no hook, no standalone command; document limitation; user adapts habit | ADR-005 |
| 7 | 4 (validator W6) | Promotion visibility | Observability | R1×R3 → vault may stay empty with no automated proof | **승급 receipt 추가** | Step 5.6 emits `promotion evaluated: N candidates, M promoted`; structural test asserts receipt format | ADR-006 |

**Defensible defaults locked as assumptions (not asked — trivial / LLM-원칙):**
- Idempotency: deterministic note filename `<type>-<slug>.md` + `hm_source` link-back frontmatter → re-promotion hits the same path → `write_note` preserves `created`, bumps `updated`, updates body (no duplicates). User accepted "link-back 불변조건" in Round 2.
- Failure mode: vault/folder unavailable → warn-and-proceed, **never block wrapup** (consistent with PLAN-second-brain-write-failure ADR-008 graceful degrade + CLAUDE.md warn-and-proceed policy).
- Division of labour: Python (`promote_note`) owns path/dedup/validation/scope-tag (safety rail); the wrapup prompt owns *what qualifies*, note_type, title, body, links (CLAUDE.md "LLM 활용 원칙").

## 📐 Architecture Decision Records

### ADR-001: Wrapup Second-Brain write becomes a must-evaluate numbered Step (supersedes PLAN-second-brain-write-failure ADR-006)
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** ADR-006 of PLAN-second-brain-write-failure locked the wrapup Obsidian write as "Advisory" floating preamble, rejecting Strong/Mandatory because a count-gate risks synthetic notes. Empirically the advisory is dropped 100% of the time — the LLM completes the concrete numbered Step 5 (local memory) and skips the unnumbered advisory. The vault is empty after weeks.
**Decision:** Promote the write from a floating preamble to a **numbered wrapup Step (5.6)**. The Step is a **MUST-evaluate** step: the LLM is required to *evaluate* every wrapup, but only *writes* a note when content qualifies (ADR-003 filter). This threads the needle ADR-006 missed — it removes the silent-skip without forcing a count gate that would fabricate notes.
**Consequences:**
- ✅ The write stops being silently droppable — it is now a checklist item with the same weight as local-memory append (Step 5.1-5.5).
- ✅ No mandatory count gate → no synthetic-note pressure (ADR-006's original concern is honored).
- ⚠️ LLM judgment can still under-promote (residual R3). Structural test guards the Step's *presence*, not the LLM's per-run judgment.
**Rejected alternatives:**
- Keep Advisory — Rejected: it is the proven root cause of the empty vault.
- Mandatory gate (fail/warn on zero notes) — Rejected again per ADR-006's synthetic-note reasoning; the user reaffirmed this in Round 1 by choosing "must-evaluate step" over a gate.
**Source:** Interview #2
**Supersedes:** PLAN-second-brain-write-failure ADR-006.

### ADR-002: Promotion-pipeline role model (local = working memory; Obsidian = curated cross-project durable)
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** Two parallel memory systems exist with overlapping conceptual roles. Without a defined relationship, the LLM treats them as redundant and satisfies only the one wired as a concrete step (local). The user must decide which is which.
**Decision:** Local `.claude/memory/` is the **project working memory** (fast, high-churn, project-scoped: wiki/failures/session/proposals). Obsidian Second Brain is the **curated cross-project durable layer**. wrapup Step 5.6 **promotes** qualifying local entries upward — it does not duplicate wholesale. Mapping (Q3 "full mapping"):

| Local source | → Obsidian note_type |
|---|---|
| `failures.md` entry (qualifying) | `failure` |
| PLAN ADR (durable architecture decision) | `decision` |
| `session/<date>.md` `[decision:...]` entry | `decision` |
| confirmed user/project preference | `preference` |
| (optional) project context, external pointer, session summary | `project` / `reference` / `journal` |

**Consequences:**
- ✅ Clear non-overlapping responsibility: local = "what happened in this repo", Obsidian = "what I'd want in any repo".
- ✅ Promotion (subset) keeps the vault curated, not a mirror dump.
- ⚠️ Some local entries never promote — by design.
**Rejected alternatives:**
- Parallel direct write (both independent) — Rejected: duplicates content, no curation.
- Role split by type only — Rejected: less flexible than judgment-based promotion.
- Disable Second Brain as redundant — Rejected: the user wants the cross-project durable layer.
**Source:** Interviews #1, #3

### ADR-003: Promotion filter is LLM-judged "cross-project durable", not a deterministic threshold
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** A candidate local entry qualifies for promotion only if it has value beyond this repo. The qualification rule can be deterministic (e.g. `failure count >= 3`, all ADRs) or LLM-judged.
**Decision:** The wrapup Step asks the LLM, per candidate, "is this valuable to other projects / my future self, beyond this repo?" Only entries judged yes are promoted. This matches CLAUDE.md's "LLM 활용 원칙" (prefer judgment over rule-matching).
**Consequences:**
- ✅ Most accurate curation; keeps the vault clean.
- ✅ No rigid threshold that misses a valuable one-off decision or promotes noisy repeated failures.
- ⚠️ Non-deterministic — two wrapups could promote slightly different sets. Acceptable; idempotent path (ADR-004) means re-promotion updates rather than duplicates.
**Rejected alternatives:**
- Deterministic threshold (`count>=3` + all ADRs) — Rejected: rigid, misses valuable one-offs (Round 2 note).
- Promote everything (no filter) — Rejected: vault pollution, contradicts the "curated" half of ADR-002.
**Source:** Interview #4

### ADR-004: `second_brain promote` CLI is the idempotency / path safety rail
**Status:** Accepted (2026-05-28, via /hm:plan interview — defensible default on accepted link-back invariant)
**Context:** If the wrapup prompt computed note filenames freely, the LLM could choose different filenames across runs → duplicate notes for the same source. CLAUDE.md mandates "Python 레이어는 타입 계약·저장·안전 레일만 담당."
**Decision:** Add `promote_note(...)` + a `promote` CLI subcommand. Python owns: deterministic relpath `<folder>/<note_type>-<slugify(source_slug)>.md`, `hm_source` link-back frontmatter, **`project_id` (= `cfg.project_id`) injection** so the note satisfies `_project_namespace_warnings` (W1 — that validator recognizes `project_id`/`project`/`projects`, NOT `hm_source`; `hm_source` is link-back only), scope/type tag injection, schema validation, and idempotency (delegates to `write_note`, which preserves `created` + bumps `updated` on re-write). The LLM provides note_type, source_slug, title, body, links via flags. Re-promoting the same `(note_type, source_slug)` updates the existing note in place — never creates a duplicate.
**Consequences:**
- ✅ Deterministic, testable idempotency boundary (unit-testable, unlike pure-prompt logic).
- ✅ Honors CLAUDE.md's CLI-vs-prompt division (item 4) and bidirectional-mapper principle (item 6 — `hm_source` lets a future reader trace a note back to its local origin).
- ⚠️ Slugify collisions across distinct sources mitigated by using the full source slug + type prefix + project namespace.
**Rejected alternatives:**
- Pure-prompt filename (LLM computes path) — Rejected: non-deterministic, untestable, duplicate risk.
- Manifest file tracking promoted slugs — Rejected: extra state file; deterministic path achieves dedup without it.
**Source:** Interview #4 (link-back invariant accepted), CLAUDE.md §구현 패턴

### ADR-005: Promotion fires only at wrapup; the "wrapup rarely run" gap is an accepted documented limitation
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** Promotion is wired into wrapup, but `/hm:wrapup` runs in only ~3/40 recent commits (most work is manual/quick commits). So even with the Step, promotion seldom fires.
**Decision:** Accept wrapup as the **sole** promotion point. Do not add a Stop/commit hook or a standalone `/hm:remember` command. Document the limitation prominently (CLAUDE.md + risk register) so the user can adapt their habit (finish work units with `/hm:wrapup`).
**Consequences:**
- ✅ Zero added surface; single write path is simplest and safest.
- ✅ No low-quality hook-mirrored notes (the hook option's quality concern is avoided).
- ⚠️ **Known limitation:** manual-commit workflows bypass promotion entirely. The vault fills only as fast as wrapup runs. The user accepted this trade-off explicitly.
**Rejected alternatives:**
- Standalone `/hm:remember` command — Rejected this round: added surface; user chose simplest.
- Lightweight hook — Rejected: contradicts Round 1's "wrapup step" and risks low-quality mechanical mirroring.
**Source:** Interview #6

### ADR-006: Step 5.6 emits a promotion receipt (observability for R1×R3)
**Status:** Accepted (2026-05-28, via /hm:plan interview — validator W6 follow-up)
**Context:** The validator flagged the dominant residual risk honestly: R1 (wrapup runs ~3/40 commits) × R3 (LLM judgment is skippable) means the empty-vault symptom may persist after shipping, and the only behavioral proof is a manual Success Criterion. The structural test guards Step *presence*, not per-run behavior.
**Decision:** Step 5.6 emits a single-line receipt to wrapup output: `promotion evaluated: N candidates, M promoted` (and, when M < N, a one-line reason summary). The structural regression test asserts the receipt-line *format* is rendered into the prompt, giving the test something beyond mere step presence; at runtime the receipt makes under-promotion (`N>0, M=0`) and zero-candidate runs visible to the user.
**Consequences:**
- ✅ Silent under-promotion becomes observable without a mandatory-write gate (no synthetic-note pressure — ADR-001/006-of-prior-PLAN reasoning preserved).
- ✅ Gives the Phase 4 structural test a concrete behavioral anchor (receipt format), not just `grep "promote"`.
- ⚠️ The receipt is LLM-emitted prose; it is observability, not a hard guarantee. It does not auto-fail wrapup.
**Rejected alternatives:**
- No receipt, manual verification only — Rejected (W6): leaves the primary success metric untested.
- Mandatory gate on `M==0` — Rejected: reintroduces the synthetic-note pressure ADR-001 avoids.
**Source:** Interview #7 (validator W6)

## 🏗️ Technical Design

### Current State

```
WRITE path to Obsidian Second Brain:
  templates/stages/wrapup.md.j2
    ## Stage-Aware Second Brain   ← floating advisory preamble (lines 38-57)
        "wrapup also writes ... notes"   ← NEVER executed (not a numbered step)
    ### Step 1..8                  ← numbered procedure
        Step 5 — Memory append → .claude/memory/ ONLY (5.1 wiki .. 5.5 session)
        (no second_brain write step anywhere)

second_brain.py CLI: write / append / patch / read / search / validate
        write_note() is idempotent on same path (preserves created, bumps updated)
        — but nothing CALLS it during normal operation.

Result: 99_HM/harness-maker/ = 0 files.
```

### Affected Components

| File | Change |
|---|---|
| `src/harness_maker/second_brain.py` | Add `promote_note(...)` + `_slugify` + `promote` CLI subcommand (idempotent path + link-back + `project_id` + scope tag). |
| `src/harness_maker/cli.py` | **No change** (W-confirmed): the `second_brain` CLI is its own argparse module in `second_brain._cli` (lines 509-578), not the top-level Typer app. `cli.py` only carries `make` flags for vault config, no subcommands. |
| `src/harness_maker/templates/stages/wrapup.md.j2` | Revise "Stage-Aware Second Brain" preamble → point at Step 5.6; add **Step 5.6 — Second Brain promotion** (claude + codex branches) incl. receipt + degrade. |
| `.claude/**` (re-render via `harness-maker make . --update`) | Propagate template change to `stages/wrapup.md`, `commands/hm/wrapup.md`, `commands/hm/exec-rev-wrap.md`, `commands/hm/exec-rev-wrap-ver.md`. |
| `tests/unit/test_second_brain.py` | `promote_note` determinism + idempotent re-promote + frontmatter validity (incl. **zero project-namespace warnings**) + type-folder check. |
| `tests/integration/test_second_brain_e2e.py` (**EXISTS — EXTEND, not Add**; owned by Phase 4) | Add a render → promote → search roundtrip test alongside the existing 5 tests. |
| structural test (live-render grep, Phase 4) | Assert the rendered wrapup **procedure** (`stages/wrapup.md` + fused `exec-rev-wrap*.md`, NOT the thin `commands/hm/wrapup.md` dispatcher) contains a numbered Step calling `second_brain promote` **and** the receipt-line format (regression guard vs advisory-only relapse). |
| `CLAUDE.md` | Document promotion-pipeline model + wrapup-only limitation. |
| `CHANGELOG.md` | Entry under next version. |
| 5 version files | Bump to `0.27.0` (templates/user-facing behavior change). |

### Design Decisions

- **`promote_note` signature** (ADR-004): `promote_note(harness_root, *, note_type: str, source_slug: str, title: str, body: str, links: list[str] | None = None, extra_frontmatter: dict | None = None) -> WriteResult`. Computes relpath from the first writable folder + `f"{note_type}-{_slugify(source_slug)}.md"`; injects `hm_source: source_slug` (link-back), **`project_id: cfg.project_id`** (so `_project_namespace_warnings` is satisfied — W1), `tags: [hm/second-brain, hm/type/<type>, ...]`; delegates to `write_note` (idempotent). `cfg.project_id` comes from the loaded `SecondBrainConfig`, NOT derived from `source_slug`.
- **Step 5.6 placement**: after Step 5.5 (session log) — so it reads the local entries 5.1-5.5 just wrote — and before Step 6 (git add). The vault is a **separate git repo** (`/mnt/c/.../obsidian-vault/.git` + its own daemon); wrapup Step 6/7 add only `.claude/memory/` + PLAN, so promoted vault notes are **not** committed by our wrapup commit — the vault's own tooling handles them. Step 5.6 must state this explicitly.
- **Promotion receipt** (ADR-006): Step 5.6 ends by emitting `promotion evaluated: N candidates, M promoted` (+ a one-line reason when `M < N`). Observability for R1×R3.
- **Graceful degrade** (+ nit1): Step 5.6 wraps each promote call so a `SecondBrainError` — whether folders-empty / vault-missing / disabled **or note_type-disallowed-in-folder** (`_ensure_type_allowed`) — prints a warning, counts the candidate as not-promoted in the receipt, and continues. Never aborts wrapup.

### Data Flow

```
/hm:wrapup
  Step 5.1-5.5  → write local memory (.claude/memory/)
  Step 5.6      → read those entries + recent session deltas
                → for each candidate: LLM judge "cross-project durable?"
                → if yes: second_brain promote --type <t> --source-slug <s> ...
                            → promote_note() → deterministic path → write_note() (idempotent)
                            → lands in /mnt/c/.../99_HM/harness-maker/<type>-<slug>.md
                → on SecondBrainError (incl. type-disallowed): warn + count as not-promoted + continue (never block)
                → emit receipt: "promotion evaluated: N candidates, M promoted"
  Step 6/7      → git add .claude/memory + PLAN; commit  (vault NOT in this commit)
```

## 📝 Implementation Plan

### Phase 1 — `second_brain.promote` (Python idempotency safety rail)
- `depends_on`: []
- `parallel_group`: `serial-second-brain-py`
- `merge_hazards`: `src/harness_maker/second_brain.py` (single file, also touched by no other phase)
- **Scope (in):** `src/harness_maker/second_brain.py`, `tests/unit/test_second_brain.py`
- **Scope (out):** templates, render, docs, version
- **Tasks:**
  1. Add `_slugify(text: str) -> str` (lowercase, kebab, ≤60 chars, alnum+hyphen only).
  2. Add `promote_note(harness_root, *, note_type, source_slug, title, body, links=None, extra_frontmatter=None) -> WriteResult`: derive relpath under first writable folder = `<folder.path>/<note_type>-<_slugify(source_slug)>.md`; build frontmatter (`type`, `title`, `tags=[hm/second-brain, hm/type/<type>, *extra]`, `links`, `hm_source=source_slug`, **`project_id=cfg.project_id`** — W1, satisfies `_project_namespace_warnings`); delegate to `write_note` (idempotent).
  3. Add `promote` CLI subcommand: `--type --source-slug --title --body-file [--link ... repeatable] [--frontmatter-json]`.
  4. Tests: (a) deterministic relpath for same `(type, slug)`; (b) idempotent re-promote — write twice, assert same path + `created` preserved + `updated` bumped + no second file; (c) frontmatter passes `validate_note` with config `required_frontmatter`; (d) **promoted note produces ZERO project-namespace warnings** (W1 — `validate_note` returns warnings rather than raising on namespace, so assert `WriteResult.warnings` contains no namespace warning); (e) note_type not allowed in folder → `SecondBrainError`.
- **Exit criterion:** `uv run pytest tests/unit/test_second_brain.py -v -k "promote"` passes (≥1 test collected); `uv run mypy --strict src/harness_maker/second_brain.py`.
- **Risk:** low
- **Rollback:** revert to `main`.

### Phase 2 — Wrapup template promotion Step
- `depends_on`: [1]
- `parallel_group`: `serial-template`
- `merge_hazards`: `src/harness_maker/templates/stages/wrapup.md.j2` (single file)
- **Scope (in):** `src/harness_maker/templates/stages/wrapup.md.j2`
- **Scope (out):** Python, render output, docs
- **Tasks:**
  1. Revise the "## Stage-Aware Second Brain" preamble: replace "wrapup also writes ... (advisory)" with "promotion is a required evaluation step — see Step 5.6"; keep the untrusted-reference caveat.
  2. Add **### Step 5.6 — Second Brain promotion (cross-project durable knowledge)** after 5.5: (a) MUST evaluate the entries written in 5.1-5.5 + recent session deltas; (b) per-candidate LLM judgment "cross-project durable?" (ADR-003); (c) mapping table (ADR-002); (d) for qualifying entries call `second_brain promote ...` (claude `!` form + codex `Bash(...)` form via `{% if is_codex %}`); (e) graceful degrade — warn + count not-promoted + continue on **any** `SecondBrainError` (folders-empty / vault-missing / disabled / **note_type-disallowed via `_ensure_type_allowed`** — nit1), never block; (f) note that the vault is a separate repo and is NOT part of the wrapup commit; (g) **emit receipt** `promotion evaluated: N candidates, M promoted` (+ reason line when `M < N`) — ADR-006.
  3. Gate behind `{% if config.second_brain and config.second_brain.enabled %}` so harnesses without Second Brain don't render the step.
- **Exit criterion:** template renders without Jinja error (covered by Phase 4 render); manual read confirms Step 5.6 present with both claude/codex branches + receipt line.
- **Risk:** low
- **Rollback:** Phase 1.

### Phase 3 — Version bump to 0.27.0
- `depends_on`: []
- `parallel_group`: `version` (independent of 1/2; must land before Phase 4 render so rendered frontmatter carries 0.27.0)
- `merge_hazards`: 5 version files (single coordinated writer)
- **Scope (in):** `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`
- **Scope (out):** everything else
- **Tasks:** set version `0.26.8 → 0.27.0` in all five files (minor — new user-facing harness behavior).
- **Exit criterion:** `grep -RolE "0\.27\.0" .claude-plugin/plugin.json .cursor-plugin/plugin.json .codex-plugin/plugin.json pyproject.toml src/harness_maker/__init__.py | wc -l` == 5; no remaining `0.26.8` in those 5 files.
- **Risk:** low
- **Rollback:** revert version files.

### Phase 4 — Re-render `.claude/` + structural regression test + e2e roundtrip
- `depends_on`: [2, 3]
- `parallel_group`: `serial-render`
- `merge_hazards`: `.claude/**` (regenerated wholesale by renderer) — must run after Phase 2 (template) AND Phase 3 (version). The render command itself is **blocked inside `.worktrees/`** (W2 — `cli.py:251-269` guard, exit 1 `[fail:snapshot-regen-inside-worktree]`); since `worktree.scope: [execute, plan]`, this phase's render step **MUST run from the repo root**, not inside an execute worktree (or set `HARNESS_MAKER_BYPASS_WORKTREE_GUARD=1` for the regen only).
- **Scope (in):** regenerated files under `.claude/`; new structural test; **extend** `tests/integration/test_second_brain_e2e.py`
- **Scope (out):** source (`second_brain.py`), template (`.j2`), docs
- **Tasks:**
  1. Re-render: **`uv run harness-maker make . --update`** (W2 — the verbatim command; `cli.py:88-97,264`), run from repo root.
  2. Add a structural test (live-render pattern, mirror `test_second_brain_e2e.py` — call `render()` then grep the output, NOT a snapshot pin). It MUST assert against the rendered files that carry the wrapup **procedure body**: `stages/wrapup.md` AND the fused `commands/hm/exec-rev-wrap.md` / `exec-rev-wrap-ver.md` (the project's `default_workflow` is `exec-rev-wrap-ver`). Do **not** pin only `commands/hm/wrapup.md` — that is a thin dispatcher and may not inline the Step-5.6 body (W3). Assert: (a) a numbered Step calls `second_brain promote`; (b) the receipt-line format `promotion evaluated:` is present (ADR-006). Verify which rendered file inlines the body before finalizing the assertion target.
  3. Extend `tests/integration/test_second_brain_e2e.py` (file EXISTS — W5) with a render → promote → search roundtrip alongside the existing tests.
- **Exit criterion:** the named structural test is collected and passes — `uv run pytest tests/integration/test_second_brain_e2e.py::test_wrapup_renders_promote_step -v` reports `1 passed` (fully-qualified node id, NOT a fuzzy `-k` filter that exits 0 on zero match — W4); `git diff --stat .claude/` shows `stages/wrapup.md` + `exec-rev-wrap*.md` updated with the promote Step; rendered `.claude/harness.yaml` frontmatter shows `harness_maker_version: 0.27.0`.
- **Risk:** medium (render touches many files; must not drift unrelated content)
- **Rollback:** Phase 3.

### Phase 5 — Docs + full quality gate
- `depends_on`: [4]
- `parallel_group`: `serial-final`
- `merge_hazards`: none
- **Scope (in):** `CLAUDE.md`, `CHANGELOG.md`, (any doc referencing Second Brain setup)
- **Scope (out):** source, templates
- **Tasks:**
  1. CLAUDE.md: add a short subsection documenting the promotion-pipeline model (ADR-002), the must-evaluate Step (ADR-001), and the **wrapup-only limitation** (ADR-005) so the user knows promotion fires only when `/hm:wrapup` runs.
  2. CHANGELOG.md: entry under `0.27.0` referencing second_brain promotion.
  3. Full gate: `uv run pytest` (background), `uv run ruff check src/ tests/`, `uv run mypy --strict src/`.
- **Exit criterion:** all green; `grep -c "promotion" CLAUDE.md` ≥ 1; CHANGELOG has a `0.27.0` second_brain entry.
- **Risk:** low
- **Rollback:** Phase 4.

## 🚫 Non-Goals

- No hook-based or standalone-command promotion trigger (ADR-005 — wrapup-only).
- No mandatory count gate / wrapup-fails-on-zero-notes (ADR-001 — must-evaluate, not mandatory-write).
- No multi-folder / shared-namespace vault restructure (Q5 — current `99_HM/harness-maker/` kept).
- No changes to local `.claude/memory/` Step 5.1-5.5 behavior — promotion reads from them, doesn't replace them.
- No SPEC refinement (SPEC-second-brain stays skeleton).
- No backfill of historical local memory into the vault (promotion is forward-only from the next wrapup).

## 🧪 Testing Strategy

| Phase | Level | What | Where |
|---|---|---|---|
| 1 | Unit | `promote_note` deterministic relpath | `tests/unit/test_second_brain.py` |
| 1 | Unit | idempotent re-promote (write twice → same path, created preserved, no dup) | `tests/unit/test_second_brain.py` |
| 1 | Unit | promoted frontmatter passes `validate_note` + **zero project-namespace warnings** (W1) | `tests/unit/test_second_brain.py` |
| 1 | Unit | note_type disallowed in folder → `SecondBrainError` | `tests/unit/test_second_brain.py` |
| 4 | Structural | rendered **`stages/wrapup.md` + fused `exec-rev-wrap*.md`** contain numbered Step calling `second_brain promote` **and** receipt-line format (W3; node-id'd per W4) | new test (regression guard) |
| 4 | Integration | render → promote → search roundtrip (**extends** existing file — W5) | `tests/integration/test_second_brain_e2e.py` |
| 5 | Manual | run `/hm:wrapup` on a real work unit → receipt prints + a note lands in `99_HM/harness-maker/` and is searchable | CLI / Obsidian |

## ⚠️ Risks & Mitigation

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R0 | **(Dominant residual — validator W6)** R1 × R3: wrapup-rarely-run × judgment-skippable → the empirical empty-vault symptom may persist after shipping. | High | High | **Partially mitigated by ADR-006 receipt** (under-promotion becomes observable) + manual Success Criterion; fully eliminating it was rejected (would need a mandatory gate → synthetic notes, or a hook → low quality). Accepted explicitly as the dominant residual. |
| R1 | `/hm:wrapup` rarely run → promotion seldom fires (root cause #4) | High | Medium | **Accepted (ADR-005).** Documented in CLAUDE.md + this register; user adapts habit. Out of scope to auto-trigger. |
| R2 | LLM over-promotes → vault pollution | Medium | Low | Cross-project-durable filter (ADR-003) + idempotent dedup path (ADR-004). |
| R3 | LLM still under-promotes (skips judgment) | Medium | Medium | Numbered MUST-evaluate Step (ADR-001) + structural test guards Step presence; per-run judgment can't be machine-forced. |
| R4 | Vault unavailable (WSL mount / folders empty / disabled) | Medium | Low | Graceful degrade — warn + continue, never block wrapup. |
| R5 | Deterministic filename collision across distinct sources | Low | Low | `<type>-<full-slug>` + project namespace; `_slugify` keeps source distinct. |
| R6 | Synthetic notes (ADR-006's original fear) | Low | Medium | Must-evaluate (not mandatory-write) + LLM judgment, no count gate. |
| R7 | Re-render drifts unrelated `.claude/` content | Low | Medium | Phase 4 reviews `git diff --stat`; structural test scoped to wrapup. |

## ✅ Success Criteria

- [x] `uv run python -m harness_maker.second_brain promote --type decision --source-slug test-note --title "Test" --body-file <f>` writes `99_HM/harness-maker/decision-test-note.md`; running it twice does **not** create a second file and preserves `created`.
- [x] Rendered `stages/wrapup.md` + fused `exec-rev-wrap*.md` contain a **numbered** Step (5.6) that calls `second_brain promote` (not just the advisory preamble) and emit the receipt line.
- [x] Structural regression test (node-id'd) fails if the wrapup template reverts to advisory-only or drops the receipt.
- [x] `promote_note` frontmatter validates against config `required_frontmatter`, carries `hm_source` link-back AND `project_id` (zero project-namespace warnings).
- [x] CLAUDE.md documents the promotion-pipeline model + wrapup-only limitation.
- [x] All 5 version files at `0.27.0`; `.claude/` re-rendered to `0.27.0`.
- [x] `uv run pytest` + `uv run ruff check src/ tests/` + `uv run mypy --strict src/` all green.
- [x] Manual: a real `/hm:wrapup` produces a note Obsidian indexes.

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION (0 critical, 6 warnings, 2 nits) → all resolved → **NEEDS_REVISION_RESOLVED**.

| # | Severity | Issue | Resolution | Anchor |
|---|----------|-------|------------|--------|
| W1 | warning | `promote_note` spec names `hm_source` but `_project_namespace_warnings` (second_brain.py:434-450) recognizes only `project_id`/`project`/`projects` → every promote would warn | ADR-004 + Phase 1 task 2 now inject `project_id=cfg.project_id`; Phase 1 task 4(d) asserts ZERO namespace warnings | ADR-004 / Phase 1 |
| W2 | warning | Phase 4 re-render unnamed AND blocked inside worktrees (cli.py:251-269); `worktree.scope` includes execute | Phase 4 names `uv run harness-maker make . --update` + "run from repo root, not worktree (or `HARNESS_MAKER_BYPASS_WORKTREE_GUARD=1`)" | Phase 4 task 1 |
| W3 | warning | Structural test target ambiguous; procedure body lives in `stages/wrapup.md.j2` → fused `exec-rev-wrap*.md`, not the thin `commands/hm/wrapup.md` dispatcher | Phase 4 task 2 targets `stages/wrapup.md` + fused `exec-rev-wrap*.md` via live-render grep; verify inlining first | Phase 4 task 2 |
| W4 | warning | Exit criterion `-k 'wrapup_promotion or render'` passes green on zero match (silent-skip — the very bug class) | Exit criterion uses fully-qualified node id `::test_wrapup_renders_promote_step`, asserts `1 passed` | Phase 4 exit |
| W5 | warning | `test_second_brain_e2e.py` already exists; "Add" risks overwrite; phase ownership split | Relabeled EXTEND; assigned solely to Phase 4 scope | Affected Components / Phase 4 |
| W6 | warning | R1×R3 dominant residual: vault may stay empty post-ship, no automated proof | ADR-006 added — Step 5.6 emits `promotion evaluated: N candidates, M promoted` receipt; structural test asserts receipt format; R0 added to register | ADR-006 / R0 |
| nit1 | nit | Step 5.6 degrade must catch the `_ensure_type_allowed` `SecondBrainError`, not only vault-missing | Phase 2 task 2(e) catches **any** `SecondBrainError` incl. type-disallowed | Phase 2 task 2e |
| nit2 | nit | (positive) record verified-correct claims so execute does not re-litigate | See below | — |

**Verified-correct (validator, against code — do not re-litigate in execute):**
- `cli.py` needs **no** change — the `second_brain` CLI is its own argparse module (`second_brain._cli`, lines 509-578), not the top-level Typer app.
- **Phase 3 (version bump) MUST precede Phase 4 (re-render)** — rendered frontmatter stamps `harness_maker_version` from `__version__` (`cli.py:822`); `depends_on: [2,3]` on Phase 4 is correct.
- **`write_note` idempotency (ADR-004) is sound** — `second_brain.py:184-191` preserves on-disk `created`; `:50-65` bumps `updated`. Re-promote to the same deterministic path updates in place, no duplicate.
- `wiki` is correctly NOT promoted — `SecondBrainNoteType` (models.py:254-262) is decision/preference/failure/project/reference/journal; `wiki.md` stays local-only.

(No re-validation required — NEEDS_REVISION with warnings only is resolved in place per the plan stage spec; MAJOR_REVISION would have re-run the validator.)
