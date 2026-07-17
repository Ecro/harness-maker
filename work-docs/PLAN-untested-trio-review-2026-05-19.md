---
type: plan
task_slug: untested-trio-review-2026-05-19
status: planning
created: 2026-05-19
tags: [harness-maker, plan, code-review, second-brain, refdocs, sibling-repos]
interview_rounds: 4
adrs: 10
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Deep solo review of 3 features never live-exercised — second_brain → refdocs → sibling_repo"
---

# PLAN — Deep Code Review of 3 Untested-in-Practice Features

## 🎯 Executive Summary

**TL;DR:** Three features (`second_brain`, `refdocs`, `sibling_repos`) have passing unit tests but were never exercised end-to-end by the user. Mock-heavy coverage is suspected of hiding mock/reality gaps. This PLAN drives a sequential deep review by Claude solo, producing one `REVIEW-{feature}-2026-05-19.md` per feature plus a short cross-cutting summary. Review-only — fixes are scoped to a separate /hm:plan → /hm:execute.

**What changes on disk during /hm:execute:**
- `work-docs/REVIEW-second-brain-2026-05-19.md` (Phase 1)
- `work-docs/REVIEW-refdocs-2026-05-19.md` (Phase 2)
- `work-docs/REVIEW-sibling-repo-2026-05-19.md` (Phase 3)
- `work-docs/REVIEW-untested-trio-summary-2026-05-19.md` (Phase 4)
- Temporary edits to `.claude/harness.yaml` in Phase 0, fully restored in Phase 5
- Temporary fixture artifacts under `~/obsidian-vault/hm-review-fixture-2026-05-19/`, `.claude/observability/refdocs-fixture/`, `.worktrees/phase-review-2026-05-19/` — all cleaned in Phase 5

**Why:** mock-heavy unit tests + zero hands-on usage = high latent risk in: boundary conditions, error paths, integration seams with other `/hm:` stages, filesystem permission posture.

**Key decisions (links to ADRs):**
- Review focus = mock-reality gap + boundary, not generic code-review (ADR-001)
- Solo deep read + self-critique, escalate to consensus when findings thin (ADR-002, amended)
- Per-feature REVIEW docs (ADR-003)
- Order: second_brain → refdocs → sibling_repo (ADR-004)
- Review-only this PLAN; fixes deferred (ADR-005)
- Live exercise mandatory (ADR-006)
- Test gaps recorded as findings; tests written in fix PLAN (ADR-007)
- Live fixtures via temp `harness.yaml` entries with strict provenance preservation (ADR-008)
- Full 6-axis review dimensions (ADR-009)
- Short Phase 4 summary, shared-patterns + fix-PLAN ordering only (ADR-010)

## 📚 Prior Work

- `src/harness_maker/second_brain.py` (473 LOC) + `tests/integration/test_second_brain.py` + `tests/e2e/test_second_brain_e2e.py`
- `src/harness_maker/refdocs_index.py` (252 LOC) + `tests/integration/test_refdocs_index.py` + `.claude/skills/refdocs-search/SKILL.md`
- `sibling_repos` surface spread across `models.py` (Field × 2), `interview.py` (`_ask_sibling_repos`, `answers_from_harness_yaml`), `synthesize.py` (line ~643), `worktree.py` (`_load_sibling_dirs`, `SIBLING_WORKTREE_PATHS` sentinel), `cli.py` (`sibling_repos_override`) + `tests/unit/test_interview_sibling.py` + `tests/unit/test_worktree_multi.py`
- Related plan: `work-docs/PLAN-multi-repo-mgmt-2026-05.md` (sibling_repos origin; Phase 1+2 done Grade A — relevant for Phase 3 scope)
- `.claude/harness.yaml`: `second_brain.enabled=true` with empty `folders`, empty `ref_folders`, empty `sibling_repos` at PLAN write time

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | → ADR |
|---|-------|-------|----------|--------|-------|
| 1 | R1 | What "couldn't test" means | Scope | "Never live-exercised + mocks not trusted" | ADR-001 |
| 2 | R1 | Review methodology | Architecture | Claude solo deep read + self-critique | ADR-002 |
| 3 | R1 | Output format | Architecture | Per-feature REVIEW × 3 | ADR-003 |
| 4 | R1 | Sequence | Phasing | second_brain → refdocs → sibling_repo | ADR-004 |
| 5 | R2 | Fix policy | Scope | Review-only; fixes deferred | ADR-005 |
| 6 | R2 | Live exercise | Risk | Yes — deep, real environment | ADR-006 |
| 7 | R2 | Test additions | Scope | Finding only; tests in fix PLAN | ADR-007 |
| 8 | R2 | Severity rubric | Testing | blocker/critical/major/minor/info | — |
| 9 | R3 | Live fixture lifecycle | Risk | Temp register in harness.yaml → restore | ADR-008 |
| 10 | R3 | Review dimensions | Testing | Full 6-axis | ADR-009 |
| 11 | R3 | Cross-cutting summary | Phasing | Short Phase 4 doc | ADR-010 |
| 12 | R3 | Depth budget | Testing | No cap until findings converge | — |
| 13 | R4 | ADR-002 strengthening (validator W7) | Architecture | Escalation clause — solo first; consensus-arbiter if phase findings < 3 | ADR-002 (amended) |
| 14 | R4 | Obsidian vault sync state (validator W5a) | Risk | No sync — local only; Phase 0 minimal pre-check | risk table |

## 📐 Architecture Decision Records

### ADR-001: Review focus = mock-reality gap + boundary
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** User explicitly framed the gap as "mock 위주라 신뢰 X" and "never live-exercised". Generic code review would miss the load-bearing concern.
**Decision:** Every REVIEW doc must include a "Boundary & mock-reality gap" section that lists specific unit-test assumptions which may not hold in real environments (real Obsidian vault layout, real ref-folder file mix, real sibling git state).
**Consequences:**
- ✅ Findings stay anchored to the user's stated motivation
- ⚠️ Requires actually exercising each feature (cost paid in Phase 1-3)
**Rejected alternatives:**
- Generic 6-axis code review without mock-gap emphasis — Rejected: would miss the user's stated motivation
**Source:** Interview #1

### ADR-002: Methodology = Claude solo deep read + self-critique; escalate to consensus when findings thin
**Status:** Accepted (2026-05-19, via /hm:plan interview; amended in Round 4)
**Context:** `/hm:review` is designed for diffs, not for end-to-end review of already-merged features. Multi-agent consensus on whole-file scope tends to over-cite minor style issues. However, solo review of >1000 combined LOC across three modules has a known weak point that consensus exists to mitigate — therefore an escalation safety-net is required.
**Decision:** Each Phase 1-3 follows: live exercise → end-to-end code read → finding draft → mandatory self-critique gate (checklist below) → revise body if checklist fails → finalize REVIEW doc. **Escalation:** when any phase finalizes with finding count < 3 (across all 6 dimensions combined), the phase is re-opened: invoke `consensus-arbiter` subagent over that REVIEW doc + relevant source files; merge added findings into the same REVIEW (do not write a separate consensus doc); log the escalation under `Methodology` heading of the REVIEW.
**Consequences:**
- ✅ One reviewer, full context preserved across exercise and read
- ✅ Solo bias bounded by mandatory self-critique + finding-count escalation
- ⚠️ Phases with naturally clean code (few findings) pay extra consensus cost — acceptable
**Rejected alternatives:**
- `/hm:review` 5-agent consensus on every phase — Rejected: noise overhead on whole-file scope outweighs gain; consensus invoked only on escalation
- Hybrid (solo + consensus-arbiter validate every phase) — Rejected: coordination cost without proportional gain across all phases
- Explore agent parallel — Rejected: loses context boundary between mapping and judgment
**Source:** Interview #2 + Interview #13

### ADR-003: Output = per-feature REVIEW docs
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** Three features have independent code surfaces and likely independent finding sets. Future fix-stage PLANs will branch by feature.
**Decision:** Write `work-docs/REVIEW-second-brain-2026-05-19.md`, `REVIEW-refdocs-2026-05-19.md`, `REVIEW-sibling-repo-2026-05-19.md`. Each is standalone; cross-references via `[[wikilinks]]`.
**Consequences:**
- ✅ Each REVIEW is a clean input to its own future fix PLAN
- ⚠️ Some duplication in framing/context sections — acceptable
**Rejected alternatives:**
- Single consolidated `REVIEW-trio.md` — Rejected: muddles fix-time partitioning
**Source:** Interview #3

### ADR-004: Sequence = second_brain → refdocs → sibling_repo
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** Complexity descending; second_brain has the most recent code → highest doc-drift risk.
**Decision:** Phase 1 = second_brain (473 LOC + e2e test + Obsidian I/O + typed-note write semantics). Phase 2 = refdocs (252 LOC + ripgrep + multimodal Read). Phase 3 = sibling_repo (spread across 5 modules; integration tests in `test_worktree_multi`).
**Consequences:**
- ✅ Hardest review while context is freshest
- ⚠️ Late-phase blocker findings may require cross-reference updates in earlier REVIEW docs — acceptable
**Source:** Interview #4

### ADR-005: Review-only PLAN; fixes deferred
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** Scope discipline — review and fix in one PLAN risks both staying shallow.
**Decision:** This PLAN produces REVIEW docs and stops. Fixes are a separate `/hm:plan` run sourced from REVIEW docs.
**Consequences:**
- ✅ Clean exit boundary; review quality protected
- ⚠️ Blocker findings require starting a new plan immediately — acceptable
**Rejected alternatives:**
- Review + critical-only fix — Rejected: scope creep risk
- Review + full fix — Rejected: PLAN becomes unwieldy, ADR/severity re-shuffling required
**Source:** Interview #5

### ADR-006: Live exercise mandatory per feature
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** "Mocks not trusted" is the explicit gap. Reading mocked tests confirms mocks are internally consistent — not that the real system behaves the same.
**Decision:** Each Phase 1-3 starts with a real-environment exercise of the feature's primary use case (second_brain: write_note + search to/from a fixture vault subfolder; refdocs: build + search over a fixture folder; sibling_repo: worktree creation across two real git repos). The reviewer observes actual outputs, then reads code with that ground truth in hand.
**Consequences:**
- ✅ Findings rooted in observed behavior, not hypothesis
- ⚠️ Requires fixture setup (ADR-008) and clean rollback
**Source:** Interview #6

### ADR-007: Test gaps recorded as findings; tests written in a separate PLAN
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** "Add tests" mid-review derails the review.
**Decision:** Each REVIEW doc has a "Test gaps" section listing missing coverage with concrete proposals. Test code is written in the fix-stage PLAN.
**Consequences:**
- ✅ Scope held tight
- ⚠️ Some gaps may be lost if fix PLAN doesn't reference REVIEW carefully — mitigated by `[[..]]` backlinks
**Source:** Interview #7

### ADR-008: Live fixtures via temp `harness.yaml` entries with provenance preservation
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** `ref_folders` and `sibling_repos` are currently empty; live exercise requires at least one entry each. `second_brain.folders` is also empty and must be populated. `.claude/harness.yaml` is a multi-document YAML stream with a provenance frontmatter document (`generated_by`, `content_hash`, `source_template`, `harness_maker_version`) — naive `yaml.safe_dump(merged_dict)` collapses the stream and strips provenance, breaking reconcile/regenerate hash checks for the duration of the PLAN.
**Decision:**
1. Read via `harness_maker.io_utils.load_harness_yaml` (returns the data document).
2. Pre-edit, snapshot `pre_edit_doc_count = len(list(yaml.safe_load_all(path.read_text())))` and the provenance document text verbatim.
3. Merge in: one fixture `ref_folders` entry pointing at `docs/`; one fixture `sibling_repos` entry (target confirmed at Phase 0 start, default `../claude-code-discord`); one fixture `second_brain.folders` entry pointing at `~/obsidian-vault/hm-review-fixture-2026-05-19/`.
4. Write via `harness_maker.io_utils.atomic_write`, prepending the verbatim provenance document + `---\n` separator + dumped data document so the multi-doc stream count is preserved.
5. Phase 5 restores via `git checkout -- .claude/harness.yaml` and asserts a clean `git diff`.
**Consequences:**
- ✅ Real config exercised, real I/O paths hit
- ✅ Provenance survives — no false reconcile/regenerate signals during Phases 1-4
- ⚠️ If the user has uncommitted `harness.yaml` changes at Phase 0, abort immediately and surface to user
**Rejected alternatives:**
- In-place `sed`/regex edit — Rejected: fragile, easy to corrupt provenance
- `yaml.safe_dump(merged_dict)` single-doc write — Rejected: collapses multi-doc stream
**Source:** Interview #9 + validator W2 resolution

### ADR-009: Full 6-axis review dimensions per feature
**Status:** Accepted (2026-05-19, via /hm:plan interview)
**Context:** User opted for completeness over speed.
**Decision:** Every REVIEW doc has six dedicated sections in this order: `Correctness`, `Boundary & mock-reality gap`, `Security & permission posture`, `Integration boundary` (other `/hm:` stages), `UX & observability`, `Docs drift` (CLAUDE.md / README / docs/).
**Consequences:**
- ✅ Uniform structure across the three REVIEW docs — easy comparison + summary
- ⚠️ Empty sections allowed but must explicitly state "no findings — {one-sentence justification}"
**Source:** Interview #10

### ADR-010: Cross-cutting summary as short Phase 4 — shared patterns + fix-PLAN ordering only
**Status:** Accepted (2026-05-19, via /hm:plan interview; scope tightened per validator W8)
**Context:** Future fix-stage PLANs need a single entry point. However, a merged severity-sorted finding table goes stale on arrival (the moment any Phase 1-3 REVIEW is edited).
**Decision:** `REVIEW-untested-trio-summary-2026-05-19.md` contains only: (a) shared anti-patterns / common findings across features, (b) recommended fix-PLAN ordering (which feature first, why, blocker count summary), (c) wikilinks to per-feature REVIEW finding tables. **No merged finding table.**
**Consequences:**
- ✅ One file to read before opening the fix PLAN
- ✅ No stale-on-arrival surface — finding tables stay sourced from per-feature REVIEWs
**Rejected alternatives:**
- Include merged severity-sorted finding table — Rejected: stale-on-arrival cost > value
**Source:** Interview #11 + validator W8 resolution

## 🏗️ Technical Design

**Current state:** Three features ship with passing unit + (in 2 cases) integration tests. `.claude/harness.yaml` has feature flags but empty fixture lists for two. Production exercise = 0.

**Affected files (read scope during /hm:execute):**
- **second_brain:** `src/harness_maker/second_brain.py`, `src/harness_maker/models.py` (`SecondBrainConfig`/`SecondBrainFolder`/`SecondBrainNoteType`), `tests/integration/test_second_brain.py`, `tests/e2e/test_second_brain_e2e.py`, all template references to `python -m harness_maker.second_brain` under `templates/commands/hm/*.md.j2`
- **refdocs:** `src/harness_maker/refdocs_index.py`, `src/harness_maker/models.py` (`RefFolder`), `tests/integration/test_refdocs_index.py`, `.claude/skills/refdocs-search/SKILL.md`, post-render hook integration
- **sibling_repo:** `src/harness_maker/models.py` (`sibling_repos` Field × 2), `src/harness_maker/interview.py` (`_ask_sibling_repos`, `answers_from_harness_yaml`), `src/harness_maker/synthesize.py` (~L643), `src/harness_maker/worktree.py` (`_load_sibling_dirs`, `SIBLING_WORKTREE_PATHS` sentinel logic), `src/harness_maker/cli.py` (sibling_repos_override flag), `tests/unit/test_interview_sibling.py`, `tests/unit/test_worktree_multi.py`

**Write scope (during /hm:execute):** four `work-docs/REVIEW-*.md` files; temporary edit + restore on `.claude/harness.yaml`; temporary fixture artifacts (vault subfolder, refdocs index, worktree) — all cleaned in Phase 5.

**Live dependencies:** Obsidian vault at `~/obsidian-vault` (confirmed exists; no sync per R4.2), sibling repo target at `../claude-code-discord` (or alternative confirmed at Phase 0), `rg` (ripgrep) on PATH, `git` ≥ 2.5 for worktree, Python 3.12+ project venv.

**Data flow (per review phase):** fixture setup (Phase 0) → live exercise → observation log → end-to-end code read → finding draft → mandatory self-critique checklist (gate) → revise body if checklist fails → finalize REVIEW doc → if finding count < 3, invoke consensus-arbiter and merge findings (ADR-002 amended). **No worktree needed for review-only writes;** Phase 3's worktree fixture is for *exercising* sibling_repo, not for code edits.

**Self-critique checklist (inline per ADR-002 amendment; gates body finalization in Phases 1-3):**
1. Did the live exercise produce at least one observation that contradicted, or refined, a unit-test assumption? If no, explicitly justify why mocks were accurate.
2. Was each of the 6 dimensions (ADR-009) traversed — even if the section ends with "no findings"?
3. For each finding, is the severity assignment defensible against the rubric (blocker/critical/major/minor/info)?
4. For each "no findings" section, is the justification a sentence describing what was checked, not just "looks fine"?
5. Did the read cover all files listed in this PLAN's "Affected files" for this feature?
6. Did the read include test files, not just source? (Mock-reality gap claims require reading the mocks.)
7. Were error paths exercised (or at minimum read end-to-end), not just happy path?

**API/contract changes:** none. This PLAN does not modify source code.

## 📝 Implementation Plan

### Phase 0 — Live-fixture setup + environment pre-checks
- **Scope (in):** `.claude/harness.yaml` (single file; atomic, frontmatter-preserving edit per ADR-008). Pre-flight pre-checks for environment. Create the second_brain fixture subfolder on disk.
- **Scope (out):** Source code, templates, tests, REVIEW docs.
- **Pre-checks (must all pass before edit):**
  - `git status --porcelain .claude/harness.yaml` is empty (no uncommitted changes)
  - `which rg` exits 0 (ripgrep present, used by refdocs in Phase 2)
  - `git --version` reports ≥ 2.5 (worktree support, used by sibling_repo in Phase 3)
  - `~/obsidian-vault` exists (confirmed; no sync state check needed per R4.2)
  - The chosen sibling repo target (default `../claude-code-discord`) exists AND `git -C ../claude-code-discord status --porcelain` is empty (avoids worktree creation against dirty sibling)
- **Fixture creation:**
  - `mkdir -p ~/obsidian-vault/hm-review-fixture-2026-05-19/`
  - Edit `.claude/harness.yaml` via `load_harness_yaml` → merge fixture entries (one `ref_folders`, one `sibling_repos`, one `second_brain.folders`) → `atomic_write` with provenance document preserved verbatim
- **Exit criterion (single runnable command):**
  ```bash
  uv run python -c "
  import yaml
  from pathlib import Path
  from harness_maker.io_utils import load_harness_yaml
  p = Path('.claude/harness.yaml')
  docs = list(yaml.safe_load_all(p.read_text()))
  assert len(docs) >= 2, f'multi-doc stream broken: {len(docs)} docs'
  d = load_harness_yaml(p)
  assert d['second_brain']['enabled'], 'second_brain disabled'
  assert any('hm-review-fixture-2026-05-19' in str(f.get('path', '')) for f in d['second_brain']['folders']), 'second_brain fixture missing'
  assert len(d['ref_folders']) >= 1, 'ref_folders fixture missing'
  assert len(d['sibling_repos']) >= 1, 'sibling_repos fixture missing'
  assert Path('~/obsidian-vault/hm-review-fixture-2026-05-19').expanduser().is_dir(), 'vault subfolder missing'
  print('Phase 0 OK')
  " && echo "✓ Phase 0 complete"
  ```
- **Risk:** low (single config file, restorable via git checkout; pre-checks gate destructive operations)
- **Rollback:** `git checkout -- .claude/harness.yaml` + `rm -rf ~/obsidian-vault/hm-review-fixture-2026-05-19/` returns to entry state.

### Phase 1 — REVIEW `second_brain`
- **Scope (in):**
  - Live exercise: `uv run python -m harness_maker.second_brain write --type decision --title "fixture-decision" --body "test note" --folder hm-review-fixture-2026-05-19` and `… write --type preference --title "fixture-preference" --body "test pref"`; then `uv run python -m harness_maker.second_brain search "fixture" --type decision`. Capture stdout / stderr / written-file paths into the REVIEW preamble.
  - Read scope: `second_brain.py` end-to-end, `SecondBrainConfig`/`SecondBrainFolder`/`SecondBrainNoteType` in `models.py`, `tests/integration/test_second_brain.py`, `tests/e2e/test_second_brain_e2e.py`, all template references to `python -m harness_maker.second_brain` under `templates/commands/hm/*.md.j2`.
  - Write: `work-docs/REVIEW-second-brain-2026-05-19.md`.
  - Sequence: draft body → run self-critique checklist (Technical Design §) → revise body where checklist fails → finalize. If final finding count (sum across 6 sections) < 3, invoke `consensus-arbiter` over the REVIEW + read scope, merge added findings, log escalation under `## Methodology` heading.
- **Scope (out):** refdocs, sibling_repos, any source edit, any new test.
- **Exit criterion (single runnable command):**
  ```bash
  uv run python -c "
  from pathlib import Path
  t = Path('work-docs/REVIEW-second-brain-2026-05-19.md').read_text()
  required = ['## Correctness', '## Boundary & mock-reality gap', '## Security & permission posture', '## Integration boundary', '## UX & observability', '## Docs drift', '## Devils-advocate self-critique', '## Test gaps', '## Methodology']
  for h in required:
      assert h in t, f'missing section: {h}'
  sev_count = sum(t.count(f'Severity: {s}') for s in ['blocker','critical','major','minor','info'])
  assert sev_count >= 3 or '<!-- sign-off: reviewed exhaustively, fewer than 3 findings justified -->' in t, f'finding floor not met: {sev_count} severity tags'
  print('Phase 1 OK')
  "
  ```
- **Risk:** medium (Obsidian vault write — must stay inside fixture subfolder; vault is local-only per R4.2 so no sync propagation risk; cross-device contamination = none)
- **Rollback:** `rm -rf ~/obsidian-vault/hm-review-fixture-2026-05-19/*.md` (notes only, keep the folder; folder removal happens in Phase 5). Phase 0 entry state otherwise unchanged.

### Phase 2 — REVIEW `refdocs`
- **Scope (in):**
  - Live exercise: `uv run python -m harness_maker.refdocs_index build` against the `docs/` fixture entry → record index path and entry count; then exercise the `refdocs-search` skill manually (search a known docs heading via `rg` invocation mirroring the skill's pattern). Capture observed vs expected into REVIEW preamble.
  - Read scope: `refdocs_index.py`, `RefFolder` in `models.py`, `tests/integration/test_refdocs_index.py`, `.claude/skills/refdocs-search/SKILL.md`, any post-render hook that triggers `refdocs_index.build`.
  - Write: `work-docs/REVIEW-refdocs-2026-05-19.md`.
  - Sequence + escalation: same shape as Phase 1.
- **Scope (out):** Phase 1 deltas, sibling_repo, source edits.
- **Exit criterion (single runnable command):**
  ```bash
  uv run python -c "
  from pathlib import Path
  t = Path('work-docs/REVIEW-refdocs-2026-05-19.md').read_text()
  required = ['## Correctness', '## Boundary & mock-reality gap', '## Security & permission posture', '## Integration boundary', '## UX & observability', '## Docs drift', '## Devils-advocate self-critique', '## Test gaps', '## Methodology']
  for h in required:
      assert h in t, f'missing section: {h}'
  sev_count = sum(t.count(f'Severity: {s}') for s in ['blocker','critical','major','minor','info'])
  assert sev_count >= 3 or '<!-- sign-off: reviewed exhaustively, fewer than 3 findings justified -->' in t, f'finding floor not met: {sev_count}'
  print('Phase 2 OK')
  "
  ```
- **Risk:** medium (index writes a yaml file — restricted to fixture-only path under `.claude/observability/refdocs-fixture/`)
- **Rollback:** `rm -rf .claude/observability/refdocs-fixture/`. Phase 1 REVIEW doc untouched.

### Phase 3 — REVIEW `sibling_repo`
- **Scope (in):**
  - Live exercise: register sibling fixture (already done in Phase 0); run `uv run hm worktree create phase-review-2026-05-19` to exercise multi-worktree creation (slug uses `phase-*` prefix so `worktree.cleanup_all` matches it per CLAUDE.md §Worktree cleanup); inspect generated `.claude/commands/hm/execute.md` for `SIBLING_WORKTREE_PATHS` sentinel substitution; record observed state.
  - Read scope: `models.py` (both `sibling_repos` `Field` locations), `interview.py` (`_ask_sibling_repos`, `answers_from_harness_yaml`), `synthesize.py` around line 643, `worktree.py` (`_load_sibling_dirs`, sentinel logic), `cli.py` overrides, `tests/unit/test_interview_sibling.py`, `tests/unit/test_worktree_multi.py`.
  - Write: `work-docs/REVIEW-sibling-repo-2026-05-19.md`. Cross-reference `[[PLAN-multi-repo-mgmt-2026-05]]` where overlapping.
  - Sequence + escalation: same shape as Phase 1.
- **Scope (out):** Source edits, other features.
- **Exit criterion (single runnable command):**
  ```bash
  uv run python -c "
  from pathlib import Path
  t = Path('work-docs/REVIEW-sibling-repo-2026-05-19.md').read_text()
  required = ['## Correctness', '## Boundary & mock-reality gap', '## Security & permission posture', '## Integration boundary', '## UX & observability', '## Docs drift', '## Devils-advocate self-critique', '## Test gaps', '## Methodology']
  for h in required:
      assert h in t, f'missing section: {h}'
  sev_count = sum(t.count(f'Severity: {s}') for s in ['blocker','critical','major','minor','info'])
  assert sev_count >= 3 or '<!-- sign-off: reviewed exhaustively, fewer than 3 findings justified -->' in t, f'finding floor not met: {sev_count}'
  print('Phase 3 OK')
  "
  ```
- **Risk:** medium (worktree creation under `.worktrees/phase-review-2026-05-19/` — must clean up; sibling repo cleanliness verified in Phase 0)
- **Rollback:** `uv run python -c "from harness_maker import worktree; worktree.cleanup_all(force=True)"` (slug `phase-review-*` matches the cleanup prefix per CLAUDE.md). If any worktree remains, fall back to `git worktree remove .worktrees/phase-review-2026-05-19 --force`.

### Phase 4 — Cross-cutting summary (short)
- **Scope (in):** Read the three REVIEW docs; produce `work-docs/REVIEW-untested-trio-summary-2026-05-19.md` containing **only** (a) shared anti-patterns / common findings across features, (b) recommended fix-PLAN ordering with rationale, (c) `[[wikilinks]]` to per-feature REVIEW finding tables.
- **Scope (out):** Reopening the three REVIEW docs for new findings; merged severity-sorted master table (per ADR-010, dropped to avoid stale-on-arrival).
- **Exit criterion (single runnable command):**
  ```bash
  uv run python -c "
  from pathlib import Path
  t = Path('work-docs/REVIEW-untested-trio-summary-2026-05-19.md').read_text()
  required = ['## Shared anti-patterns', '## Recommended fix-PLAN ordering', '[[REVIEW-second-brain-2026-05-19]]', '[[REVIEW-refdocs-2026-05-19]]', '[[REVIEW-sibling-repo-2026-05-19]]']
  for h in required:
      assert h in t, f'missing: {h}'
  print('Phase 4 OK')
  "
  ```
- **Risk:** low (writes one new file, reads three existing)
- **Rollback:** `rm work-docs/REVIEW-untested-trio-summary-2026-05-19.md`. Phase 1-3 REVIEW docs unaffected.

### Phase 5 — Fixture rollback + verification
- **Scope (in):** Restore `.claude/harness.yaml`. Verify all fixture artifacts deleted (Obsidian fixture subfolder, refdocs fixture index, sibling worktree). Final clean-state assertion.
- **Scope (out):** REVIEW docs (they stay — the deliverable).
- **Exit criterion (single runnable command):**
  ```bash
  git checkout -- .claude/harness.yaml && \
  rm -rf ~/obsidian-vault/hm-review-fixture-2026-05-19/ && \
  rm -rf .claude/observability/refdocs-fixture/ && \
  uv run python -c "
  import subprocess
  from pathlib import Path
  diff = subprocess.check_output(['git', 'diff', '--', '.claude/harness.yaml']).decode()
  assert diff == '', f'harness.yaml not clean: {diff!r}'
  assert not Path.home().joinpath('obsidian-vault/hm-review-fixture-2026-05-19').exists(), 'vault fixture remains'
  assert not Path('.claude/observability/refdocs-fixture').exists(), 'refdocs fixture remains'
  worktrees = list(Path('.worktrees').glob('phase-review-*')) if Path('.worktrees').exists() else []
  assert not worktrees, f'orphan worktrees: {worktrees}'
  print('Phase 5 OK')
  "
  ```
- **Risk:** low
- **Rollback:** N/A — this IS the rollback phase.

## 🧪 Testing Strategy

- **Unit:** N/A — no source code change in this PLAN.
- **Integration:** Existing test suite untouched. The live exercise step in Phases 1-3 IS the integration check; observations feed Boundary & mock-reality gap findings.
- **Manual:** Each phase exit criterion is a single runnable command (see Phase exit blocks). Phase 5 ends with `git status` showing only the new `work-docs/REVIEW-*.md` files added (no source diffs, no fixture residue).
- **Consensus escalation** (per ADR-002 amended): when any Phase 1-3 finalizes with < 3 findings across all 6 dimensions, the `consensus-arbiter` subagent is invoked once over that REVIEW + relevant read scope; additional findings merge into the same REVIEW, escalation logged under `## Methodology`.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Phase 0 edit drops `harness.yaml` provenance frontmatter | low | high | ADR-008 lock: `load_harness_yaml` + `atomic_write` + verbatim provenance prepend; Phase 0 exit asserts `len(list(safe_load_all)) >= 2` |
| Phase 1 contaminates real Obsidian vault | low | medium | Vault is local-only per R4.2 (no sync to propagate); fixture pinned to dedicated subfolder; all written paths recorded in REVIEW preamble |
| Phase 3 worktree fixture leaks (orphan worktree) | low | low | Slug `phase-review-2026-05-19` matches `worktree.cleanup_all` prefix per CLAUDE.md; Phase 5 verifies `.worktrees/phase-review-*` absent |
| Phase 3 creates worktree against dirty sibling repo | low | medium | Phase 0 pre-check: `git -C ../claude-code-discord status --porcelain` is empty; abort + ask user otherwise |
| Self-critique becomes rubber-stamp | medium | medium | 7-item inline checklist (Technical Design §) gates body finalization, not appended after; finding-count < 3 escalates to consensus-arbiter |
| Ripgrep missing on machine running Phase 2 | low | medium | Phase 0 pre-check `which rg` exits 0; abort + remediation message otherwise |
| User has uncommitted `.claude/harness.yaml` at Phase 0 | low | medium | Phase 0 first pre-check: `git status --porcelain .claude/harness.yaml` empty; abort + surface to user |
| Found blocker requires immediate fix mid-plan | medium | low | ADR-005 defers all fixes — surface in summary; user starts a fix PLAN |
| Solo reviewer misses surface area on 1000+ LOC across 3 features | medium | medium | ADR-002 amended: finding-count < 3 per phase auto-escalates to consensus-arbiter |

## ✅ Success Criteria

- [ ] `work-docs/REVIEW-second-brain-2026-05-19.md` exists; 9 required headings present; `≥3` severity-tagged findings OR explicit sign-off comment
- [ ] `work-docs/REVIEW-refdocs-2026-05-19.md` exists; same structural + finding criteria
- [ ] `work-docs/REVIEW-sibling-repo-2026-05-19.md` exists; same structural + finding criteria; cross-reference to `PLAN-multi-repo-mgmt-2026-05` present
- [ ] `work-docs/REVIEW-untested-trio-summary-2026-05-19.md` exists; shared-patterns + fix-ordering sections present; wikilinks to all 3 REVIEWs present; no merged finding table (per ADR-010)
- [ ] `.claude/harness.yaml` restored — `git diff` empty
- [ ] No orphan fixtures: vault subfolder, refdocs index, worktrees all deleted
- [ ] Every finding tagged `Severity: {blocker|critical|major|minor|info}`
- [ ] Any phase that escalated to consensus-arbiter logs the escalation under `## Methodology`

## 📋 Execute-time amendments (2026-05-19)

The following amendments were applied during /hm:execute Phase 0 pre-checks. Each is traceable to a discovered constraint not visible at PLAN time.

### Amendment A1 — `.claude/harness.yaml` is gitignored, not tracked
**Discovered:** Phase 0 pre-check found `.claude/` is gitignored in this repo (`# Dogfood harness workspace — all generated by harness-maker itself`). The PLAN assumed git-tracked and used `git checkout --` for rollback.
**Fix:** Phase 0 takes a tmp-file backup (`cp .claude/harness.yaml /tmp/harness.yaml.pre-phase0.<timestamp>.bak`) before edit. Phase 5 rollback is `cp /tmp/<bak> .claude/harness.yaml && rm /tmp/<bak>`. The amended exit assertion for Phase 5 hashes pre/post bytes for exact-match verification instead of relying on `git diff`.

### Amendment A2 — Execute worktree discarded
**Discovered:** PROCEDURE Step 0 engaged a worktree at `.worktrees/execute-20260519T1303Z`, but the worktree only contains git-tracked files. `.claude/harness.yaml` is absent there — live-exercise modules read from cwd's `.claude/harness.yaml` which the worktree does not have. PLAN's Technical Design already noted "no worktree needed for review-only writes"; the gitignore discovery confirms it.
**Fix:** Worktree finalized with `fail` mode (preserved for inspection but not used). All Phase 0-5 operations run from main repo cwd `/home/noel/harness-maker/`.

### Amendment A3 — Sibling repo pre-check override (claude-code-discord)
**Discovered:** `../claude-code-discord` has 4 untracked files (`.env.obsidian`, `.obsidian.log`, `.obsidian.pid`, `start-obsidian.sh`). PLAN Phase 0 pre-check required `git status --porcelain` empty.
**Fix (user-approved Round 5):** Override pre-check — `git worktree add` does not block on untracked files in source repo, so this is safe. Phase 3 risk row updated.

### Amendment A4 — second_brain vault_path mismatch
**Discovered:** `harness.yaml.second_brain.vault_path` = `/mnt/c/Users/euncheol.ro/Documents/obsidian-vault/second-brain` (Windows path) does not resolve on this WSL machine. `~/obsidian-vault` exists.
**Fix:** Phase 0 temp-edit also overrides `vault_path` to `/home/noel/obsidian-vault`; restored in Phase 5 alongside other entries.

## 🔍 Plan Validation

- **Initial validator outcome:** `NEEDS_REVISION` (7 warnings, 2 info)
- **Resolution:**
  - **W1** (Phase 0 missing second_brain fixture assertion) → fixed in Phase 0 exit criterion (asserts fixture subfolder presence + mkdir step)
  - **W2** (writer contract for `harness.yaml` provenance unspecified) → ADR-008 expanded with explicit `load_harness_yaml` + `atomic_write` + verbatim provenance preserve; Phase 0 exit asserts `safe_load_all` doc count ≥ 2
  - **W3** (Phase 1-3 exits not runnable) → each phase exit is now a single runnable `uv run python -c "..."` block checking 9 required headings + severity-tag floor `≥ 3` OR sign-off comment
  - **W4** (self-critique as appendix → rubber-stamp risk) → 7-item checklist inlined in Technical Design § with explicit ordering: draft → checklist → revise → finalize (gate, not postscript)
  - **W5** (missing risk rows) → added (a) Obsidian sync — N/A per R4.2 (vault is local-only), (b) sibling repo dirty state — pre-checked in Phase 0, (c) ripgrep PATH — pre-checked in Phase 0; all three reflected in Risks table
  - **W6** (Phase 3 worktree slug `test-slug` outside cleanup prefix) → changed to `phase-review-2026-05-19` (matches `phase-*` cleanup prefix per CLAUDE.md)
  - **W7** (ADR-002 rejected-alternatives thin) → resolved via Interview Round 4: ADR-002 amended with escalation clause (solo first; consensus-arbiter when phase findings < 3)
  - **W8** (Phase 4 stale-on-arrival merged table) → ADR-010 scope tightened; Phase 4 keeps only shared-patterns + fix-PLAN ordering + wikilinks to per-feature REVIEW tables
  - **I1** (Executive Summary missing ADR-001/008/009 references) → added to Key decisions list
  - **I2** (Prior Work missing LOC/last-touched-commit per file) → partially applied: LOC added where load-bearing (second_brain 473, refdocs 252); last-commit dates not added (reviewer can derive at exercise time)
- **Final validator outcome:** `NEEDS_REVISION_RESOLVED` (all warnings addressed in plan body; one re-run not invoked since each fix is mechanical and traceable to a specific warning)
