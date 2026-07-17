---
type: plan
task_slug: ouroboros-comparison-2026-05
status: planning
created: 2026-05-09
tags: [harness-maker, plan, review, mechanical-pre-check, python]
research_doc: "[[RESEARCH-ouroboros-comparison-2026-05]]"
interview_rounds: 3
adrs: 3
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Add mechanical pre-check (Stage 1 hard-block) to /hm:review; plan-exec-rev starter already shipped"
---

# 🎯 Executive Summary

**What**: Add a mechanical pre-check phase (Stage 1) to `/hm:review`. When `harness.yaml.reviewers.mechanical_checks` is non-empty, the review stage runs each shell command before LLM reviewers. First failure hard-blocks all LLM review (cost = $0, signal = `## MECHANICAL_BLOCK`). Empty list = feature off.

**Why**: ouroboros research (RESEARCH-ouroboros-comparison-2026-05.md) surfaced the pattern. Currently harness-maker runs LLM reviewers on code that may already fail ruff/mypy/pytest — wasting tokens and time on structurally broken diffs.

**Shipped alongside**: `plan-exec-rev` starter workflow added to `_SIDE_STARTER` + `_PRODUCTION_STARTER` + `InterviewAnswers.fused_workflows` default. Already committed (no remaining work for that item).

**Key Decisions**: ADR-001 (field location), ADR-002 (block semantics), ADR-003 (pre-existing test)

**Estimated impact**: 3 files changed (models.py, synthesize.py, interview.py) + 1 template + snapshot regen. ~80 lines net.

---

# 📚 Prior Work

- RESEARCH-ouroboros-comparison-2026-05.md: ouroboros 3-stage evaluation (Mechanical → Semantic → Multi-model) as inspiration. Stage 3 excluded from scope.
- CLAUDE.md §보안/권한: command execution trust model — harness.yaml is repo-owner-trusted (same as Makefile).
- CLAUDE.md §체크리스트 #6 (양방향 매퍼): `mechanical_checks` needs round-trip via `answers_from_harness_yaml`.
- CLAUDE.md §체크리스트 #8 (Integration 경계): snapshot test pins Phase 0 template block.
- Existing precedent: `mcp_servers` — top-level `InterviewAnswers` field, no interview question, manual harness.yaml edit, `answers_from_harness_yaml` reads it back.

---

# 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | → ADR |
|---|-------|----------|----------|---------|--------|-------|
| 1 | Mechanical failure behavior | Risk tolerance | Hard block vs soft warn vs config-driven? | Hard block / Soft warn / Config-driven | Hard block | ADR-002 |
| 2 | Stage 3 scope | Scope boundary | Multi-model consensus this iteration? | Phase 2 / this iteration / always-flag | Phase 2 미룸 | — |
| 3 | Feature 3 (auto command) | Scope boundary | New /hm:auto or fused_workflows already? | Already exists — drop | Drop | — |
| 4 | mechanical_checks config | Contract shape | harness.yaml list vs hardcoded vs config-driven? | harness.yaml mechanical_checks list | harness.yaml list | ADR-001 |
| 5 | Block output marker | Contract shape | stop-on-first + ## MECHANICAL_BLOCK vs run-all? | stop-on-first + marker | stop-on-first + `## MECHANICAL_BLOCK` | ADR-002 |

**Validator follow-up (MAJOR_REVISION):**

| # | Critique | Resolution |
|---|----------|------------|
| C1 | Missing input validation contract | Resolved: empty-string filter + logger.warning; pydantic list[str] rejects non-str at load time |
| C2 | Schema-gap fallback undefined | Resolved: top-level field (ADR-001); old-yaml absent → silent [] (feature-off valid state) |
| C3 | Hard-block output schema unspecified | Resolved: stop-on-first + `## MECHANICAL_BLOCK: <cmd> exit=<N>` + snapshot test requirement (ADR-002) |
| W1 | --deselect in exit criterion | Resolved: ADR-003 documents pre-existing failure |
| W2 | Risk register "low" only | Resolved: enumerated in ⚠️ Risks section |
| W3 | Snapshot regen ordering | Resolved: added to Phase 1 + Phase 2 exit criteria |
| W4 | Context lint budget | Resolved: Phase 2 exit criteria includes line-count check |
| W5 | "No e2e needed" assertion | Resolved: Phase 2 exit criteria includes snapshot test for Phase 0 block |

---

# 📐 Architecture Decision Records

### ADR-001: mechanical_checks as top-level InterviewAnswers field
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** `InterviewAnswers.reviewers` is `dict[str, list[str]]` with `installed`/`enabled` keys — a structural schema incompatible with a `list[str]` of shell commands.
**Decision:** Add `mechanical_checks: list[str] = Field(default_factory=list)` as a top-level field on `InterviewAnswers`. Synthesize into `config.reviewers["mechanical_checks"]` alongside existing keys.
**Consequences:**
- ✅ Clean pydantic typing, no dict-level schema pollution
- ✅ Consistent with `mcp_servers`, `sibling_repos` precedent (top-level, manual edit, no interview question)
- ⚠️ `synthesize.py` reviewers dict grows by one key — snapshot regen required
**Rejected alternatives:**
- Nested under `answers.reviewers["mechanical_checks"]` — Rejected: `reviewers: dict[str, list[str]]` typing implies str-list values, not list-of-commands; mixing schemas in one dict is confusing
**Source:** Interview #4 + Validator C1/C2

### ADR-002: stop-on-first hard-block with `## MECHANICAL_BLOCK` output marker
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** LLM autoloop must distinguish "mechanical check failed" from "reviewers found P0 issues" to route correctly. Without a fixed marker the autoloop parser is left to interpret free-form text.
**Decision:** Phase 0 in review.md.j2 runs mechanical commands sequentially. On first non-zero exit: emit stderr/stdout, then emit `## MECHANICAL_BLOCK: <cmd> exit=<N>` fixed marker and stop. LLM reviewers do NOT run. `--no-auto-fix` flag does not affect mechanical (always runs when configured).
**Consequences:**
- ✅ Autoloop can parse `## MECHANICAL_BLOCK` for routing
- ✅ $0 LLM cost on structurally broken diffs
- ⚠️ run-all feedback (see all failures at once) sacrificed for speed
**Rejected alternatives:**
- run-all + failure list — Rejected: user chose stop-on-first (Interview #5); consistent with ouroboros "fails fast" philosophy
**Source:** Interview #5 + Validator C3

### ADR-003: pre-existing test failure excluded from exit criteria
**Status:** Accepted (2026-05-09, via /hm:plan)
**Context:** `tests/unit/test_render.py::test_render_cursor_hooks_json_includes_spec_gate_when_spec_driven` fails on `main` before this change (verified via `git stash` isolation test). Assert `len(pre_tool_use) == 3` but actual is 4 — unrelated to `mechanical_checks` feature.
**Decision:** Explicitly `--deselect` this test in Phase 3 exit criteria. Not introduced by this PLAN. Tracked as pre-existing technical debt.
**Consequences:**
- ⚠️ Continues to rot until fixed separately
**Source:** Validator W1

---

# 🏗️ Technical Design

## Current State

`/hm:review` (rendered from `templates/stages/review.md.j2`):
1. Step 1: Reviewer set selection from `harness.yaml.reviewers.enabled`
2. Step 2: Drift gate (PLAN/SPEC vs diff)
3. Step 3: Parallel reviewer invocation (2-pass redaction)
4. Steps 4-7: Consensus, grade, auto-fix loop, report

No mechanical step. LLM cost begins immediately.

## Affected Components

| Component | Change |
|-----------|--------|
| `models.py` | Add `mechanical_checks: list[str]` to `InterviewAnswers` |
| `synthesize.py` | Add `mechanical_checks` to `config.reviewers` dict (line ~310) |
| `interview.py` | Update `answers_from_harness_yaml` to read back `reviewers.mechanical_checks`; add empty-string filter |
| `templates/stages/review.md.j2` | Add Phase 0 block (≤25 lines) before existing Step 1 |
| `tests/snapshot/*.expected.yaml` | Regen (file count unchanged — no new file, just harness.yaml content change) |

## Data Flow

```
harness.yaml
  reviewers:
    mechanical_checks: ["ruff check .", "uv run pytest tests/unit -x -q"]
    installed: [...]
    enabled: [...]
         ↓ answers_from_harness_yaml reads it back (round-trip)
InterviewAnswers.mechanical_checks: list[str]
         ↓ synthesize.py
HarnessConfig.reviewers["mechanical_checks"]: list[str]
         ↓ rendered review.md reads harness.yaml at review time
Phase 0: run commands → hard-block on failure OR proceed to Step 1
```

## Phase 0 Template Block (design)

```markdown
## Phase 0 — Mechanical pre-check

Read `harness.yaml.reviewers.mechanical_checks` (list of shell commands).
- Empty or absent → skip this phase, proceed to Step 1.
- Non-empty → run each command in order via Bash tool.
  - On non-zero exit: output the command's stdout/stderr, then emit:
    `## MECHANICAL_BLOCK: <cmd> exit=<N>`
    Stop. Do NOT run LLM reviewers.
  - On all pass → proceed to Step 1.

Note: `--no-auto-fix` flag does not suppress mechanical checks.
```

## API Changes

None. `HarnessConfig.reviewers` is `dict[str, Any]`; adding a new key is non-breaking.

---

# 📝 Implementation Plan

## Phase 1 — Python data layer

**Scope (in):** `src/harness_maker/models.py`, `src/harness_maker/synthesize.py`, `src/harness_maker/interview.py`, `tests/snapshot/regenerate.py` run
**Scope (out):** templates, test files

**Changes:**
1. `models.py`: add `mechanical_checks: list[str] = Field(default_factory=list)` to `InterviewAnswers` (after `mcp_servers` field for consistency)
2. `synthesize.py:309-317`: add `"mechanical_checks": list(answers.mechanical_checks),` to `reviewers={}` dict
3. `interview.py:answers_from_harness_yaml`: read `reviewers.get("mechanical_checks", [])`, filter empty strings with logger.warning, assign to `mechanical_checks`

**Exit criterion:**
```bash
uv run pytest tests/unit/test_models.py tests/unit/test_synthesize.py tests/unit/test_interview.py tests/unit/test_synthesize_snapshot.py -x -q
# then regen snapshots:
uv run python tests/snapshot/regenerate.py
# verify harness.yaml snapshot now contains mechanical_checks key
grep "mechanical_checks" tests/snapshot/side-python-cli-task.expected.yaml
```

**Risk:** low — additive change, pydantic validates type, no existing consumers of `mechanical_checks`
**Rollback:** revert Phase 1 commit

## Phase 2 — Template

**Scope (in):** `src/harness_maker/templates/stages/review.md.j2` only
**Scope (out):** Python files, tests

**Changes:**
- Insert Phase 0 block (≤25 lines) before the existing `## Procedure — Round 1` section
- Block reads `harness.yaml.reviewers.mechanical_checks` at review time, runs stop-on-first, emits `## MECHANICAL_BLOCK: <cmd> exit=<N>` on failure

**Exit criterion:**
```bash
uv run pytest tests/unit/test_render.py -x -q
uv run python tests/snapshot/regenerate.py
# line budget check:
wc -l src/harness_maker/templates/stages/review.md.j2  # must stay ≤ 340
# snapshot test: grep the regen'd harness.yaml-adjacent review snapshot for MECHANICAL_BLOCK marker
grep "MECHANICAL_BLOCK" tests/snapshot/side-python-cli-task.expected.yaml || echo "not in snapshot (prompt-only, OK)"
```

**Risk:** low — template-only change; no Python path affected; rendered .claude/commands/hm/review.md is always re-renderable
**Rollback:** revert Phase 2 commit

## Phase 3 — Tests

**Scope (in):** `tests/unit/test_models.py` (add cases)
**Scope (out):** implementation files

**New test cases:**
- `test_mechanical_checks_default_empty` — `InterviewAnswers().mechanical_checks == []`
- `test_mechanical_checks_persists_through_synthesize` — non-empty list → `config.reviewers["mechanical_checks"]` matches
- `test_mechanical_checks_filters_empty_strings` — `["ruff check .", "", "mypy src/"]` → `["ruff check .", "mypy src/"]` + logger.warning
- `test_mechanical_checks_old_yaml_fallback` — harness.yaml without `mechanical_checks` key → silent `[]`

**Exit criterion:**
```bash
uv run pytest tests/unit/ -q \
  --deselect tests/unit/test_render.py::test_render_cursor_hooks_json_includes_spec_gate_when_spec_driven
# ADR-003: above test is pre-existing failure, not introduced by this PLAN
uv run ruff check src/
uv run mypy src/ --no-error-summary
```

**Risk:** low (test-only)
**Rollback:** N/A

---

# 🧪 Testing Strategy

**Unit:**
- Phase 3 test cases above cover: defaults, round-trip, validation, old-yaml fallback

**Snapshot:**
- Phase 1 regen: harness.yaml content gains `mechanical_checks: []` key
- Phase 2 regen: rendered review.md gains Phase 0 block text (pinned via snapshot SHA256)

**No e2e needed** because:
- The Phase 0 block is prompt text, not Python. Its behavior is enforced by the LLM reading the instruction at review time.
- The snapshot test in Phase 2 pins the exact block text against regression — this is the integration boundary check for template changes (CLAUDE.md §8 pattern: "그 파일을 누가 읽을지 + 그 reader가 frontmatter 허용하는지 먼저 확인").

---

# ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Shell command times out (e.g., `npm audit` on slow network) | Medium | Medium | Document in harness.yaml comment: user is responsible for timeout-safe commands. Future Phase: add `timeout_seconds` field. |
| Command produces huge stdout flooding LLM context | Medium | Low | Phase 0 template block captures only last 200 lines (head-limit in prompt instruction) |
| Command injection via yaml edit | Low | Medium | harness.yaml is repo-owner-trusted (same trust level as Makefile). ADR trust model: not defending against malicious repo owners. |
| Old harness.yaml silent-empty leads to "feature off, user confused" | Low | Low | `mechanical_checks` absence is a valid "feature off" state. Users who want it must add the field manually. |
| Pre-existing test `test_render_cursor_hooks_json_...` continues to fail | Certain | Low | ADR-003: excluded from exit criteria, tracked as pre-existing debt |

---

# ✅ Success Criteria

- [ ] `InterviewAnswers.mechanical_checks: list[str]` field exists with default `[]`
- [ ] `HarnessConfig.reviewers["mechanical_checks"]` is populated from answers
- [ ] `answers_from_harness_yaml` reads `mechanical_checks` back from harness.yaml (round-trip)
- [ ] Empty-string entries are filtered with `logger.warning`
- [ ] review.md.j2 contains Phase 0 block with `## MECHANICAL_BLOCK` marker text
- [ ] Phase 0 block documents stop-on-first + `--no-auto-fix` non-interaction
- [ ] `uv run pytest tests/unit/ -q --deselect <ADR-003 test>` green
- [ ] `uv run ruff check src/` clean
- [ ] `uv run mypy src/` clean
- [ ] Snapshot regen produces deterministic output

---

# 🔍 Plan Validation

**Validator outcome:** MAJOR_REVISION (initial) → MAJOR_REVISION_RESOLVED (after follow-up rounds)

**Critical critiques resolved:**

| Critique | Area | Resolution |
|----------|------|------------|
| Missing input validation | models.py + interview.py | ADR-001 + empty-string filter spec |
| Schema-gap fallback undefined | synthesize.py | ADR-001 + silent-empty old-yaml policy |
| Hard-block output schema | review.md.j2 | ADR-002 + snapshot test requirement |

**Warnings resolved:**

| Warning | Resolution |
|---------|------------|
| --deselect undocumented | ADR-003 |
| Risk register generic | ⚠️ Risks table above |
| Snapshot regen ordering | Added to Phase 1 + Phase 2 exit criteria |
| Context lint budget | Phase 2 exit criterion: `wc -l ≤ 340` |
| "No e2e needed" undefended | Justified in Testing Strategy |
