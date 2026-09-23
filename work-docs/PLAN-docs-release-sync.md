---
type: plan
task_slug: docs-release-sync
status: complete
created: 2026-09-22
tags: [harness-maker, plan, python, documentation, release, drift-prevention]
spec: "[[SPEC-docs-release-sync]]"
research_doc: "[[RESEARCH-docs-release-sync]]"
interview_rounds: 0
adrs: 4
validator_outcome: NOT_RUN
summary: "Repair living docs and enforce local plus published release documentation contracts"
intent: WORLD-INTENT-CLOSED-LOOP
spec_need_verdict: add
spec_need_target: docs-release-sync
---

# PLAN: Release documentation synchronization

## 🎯 Executive Summary

Repair the v0.59.0 living documentation against the live six-stage workflow and add an
executable contract that prevents the same drift from recurring. The implementation separates
hermetic source-to-document checks from post-publication GitHub/PyPI checks, validates visible
contract-bearing prose rather than detached markers, and preserves historical records.

The user authorized both current repair and future prevention. The approved SPEC owns the
observable contract; this PLAN selects the reversible implementation shape and phase order.

## 📚 Prior Work

- [[SPEC-plan-stage-absorption]] removed `/hm:plan`, retained the PLAN document, and established
  the six-stage pipeline; its acceptance boundary covered CHANGELOG and help but not all living
  docs.
- [[PLAN-harness-diet]] and `tests/structural/test_documented_commands_exist.py` establish the
  pattern of deriving runnable command claims from live source while explicitly excluding
  historical records.
- [[RESEARCH-docs-release-sync]] found stale version banners, a seven-stage topology, wrong
  `review → wrapup → verify` ordering, old validator/catalog names, and inconsistent
  mechanism/version counts despite a green documentation suite.
- `[wiki:pattern verify-owns-full-suite-before-wrapup]` is the independent source for the
  canonical `review → verify → wrapup` order.
- `[wiki:architecture pypi-trusted-publishing-via-uv-publish]` fixes the existing release
  dependency chain and five-file version contract.
- `[fail:test assertion-invariant-over-named-dimension]` requires mutation controls tied to the
  exact contract each scanner owns, not whole-document keyword assertions.

## 📐 Architecture Decision Records

### ADR-001: One hermetic documentation-contract module owns mechanical claims

Create a small internal Python module that extracts visible contract data and reports keyed
errors. Structural tests and the release preflight call the same functions; documents do not
receive detached truth markers that can coexist with contradictory prose. This is reversible
and internal, so it is not an irreversible SPEC decision.

Rejected: independent regex tests per document. They recreate multiple normative sites and
repeat the exact scanner drift found in the research.

### ADR-002: Release identity is a two-boundary protocol

The tag-time quality gate compares the tag, five local version files, and visible documentation
identity without network access. A required job after `github-release` compares GitHub and PyPI
with the already validated tag and fails on mismatch or unavailable evidence.

Rejected: one combined check before publication, which cannot find a release that does not yet
exist; and advisory post-publication checks, which cannot uphold an "always synchronized" rule.

### ADR-003: Core living docs are fixed; broader current docs use explicit historical exclusions

The eight SPEC-named core docs are mandatory. Additional `docs/**/*.md` files are scanned for
retired current-tense claims except the exact directory/file exclusions in S4. CHANGELOG uses
the same `[Unreleased]` plus first-release boundary as the existing command contract.

Rejected: a marker-only opt-in, because a newly stale document could evade the gate by omitting
the marker; and scanning history indiscriminately, because it rewrites evidence.

### ADR-004: Mechanism identity uses an explicit provenance-backed golden

There is no runtime M1–M19 registry. Store the approved catalog as test oracle data, compare it
with Architecture headings and README summaries, and require a mechanism mutation control.
The fixture names its v0.59.0 provenance so a future mechanism change updates oracle and docs
in one reviewed diff rather than pretending the value is code-derived.

Rejected: using `docs/ARCHITECTURE.md` as both subject and oracle, which is circular.

## 🏗️ Technical Design

### Current state

- `AtomicStage` contains six live stages; Side's Jinja fallback still names retired `plan`.
- README recommends `wrapup` before `verify`.
- HOW-IT-WORKS banners are `0.9.3` and `0.7.1`, and both guides retain stale topology/catalog
  content.
- Existing documentation tests validate command existence but not stage topology/order,
  complete inventories, version freshness, or publication identity.
- `release.yml` publishes TestPyPI → PyPI → GitHub Release and has no required remote
  parity job.

### Components and data flow

1. Source readers obtain live stages, canonical pipeline, agent/skill template basenames, five
   source versions, and the provenance-backed mechanism golden.
2. Visible-section parsers normalize contract data from the core docs and return per-file,
   per-key errors.
3. Structural pytest tests exercise the real tree plus isolated mutations of every observed
   defect class.
4. The local release command reuses version readers and accepts the tag as input; it performs
   no network request.
5. The remote command fetches fixed GitHub/PyPI endpoints with timeouts/retries, classifies
   match/mismatch/unavailable, and returns nonzero for the latter two.
6. GitHub Actions invokes local identity before build/publish and remote identity after the
   GitHub Release exists.

## 📝 Implementation Plan

### Phase 1: Documentation contract and RED controls

- `depends_on`: none
- `parallel_group`: serial
- `merge_hazards`: The parser, fixtures, and tests share one contract vocabulary; split work
  would create competing normative lists.
- Scope in: `src/harness_maker/documentation_contract.py`,
  `tests/structural/test_documentation_contract.py`, contract oracle fixture under
  `tests/fixtures/`, and `src/harness_maker/templates/harness-yaml/{Side,Production}.yaml.j2`.
- Scope out: release networking/workflow and prose repair except minimal fixtures.
- Work: write source-derived readers, visible contract extractors, exact historical exclusions,
  preset fallback comparison, and negative controls for all SPEC mutation classes; prove RED
  against the current tree before implementation.
- Exit criterion: `uv run pytest -q tests/structural/test_documentation_contract.py`
- `risk`: high
- Rollback point: remove the new module/test/fixture and restore the single Side fallback edit.

**Status: BLOCKED at Phase A.5 after two test-reviewer rounds.** Round 1 found seven
discrimination/coverage defects; all were repaired before round 2. Round 2 retained four:

1. the five version-source paths are not asserted independently of the production reader;
2. mutation assertions bind the error key but not the mutated document path;
3. deleting each mandatory core document has no path-specific negative control; and
4. CHANGELOG extraction is not connected to repository validation for `[Unreleased]`, the
   first real release, and the second historical release.

No production implementation has been written. The RED state remains one collection error
(`ModuleNotFoundError: harness_maker.documentation_contract`) with zero tests executed.
`[boundaries] comparison not performed — blocked exit`.

**Resume disposition (2026-09-22):** the user approved stuck Path A. Production remains
untouched while the four terminal findings are repaired in RED tests: exact five-version-path
oracle, path-sensitive mutation errors, one missing-core-doc negative per fixed path, and
repository-level CHANGELOG inclusion-boundary controls. Phase A.5 restarts with a new review
budget after these changes.

**Status: DONE (combined serial barrier with Phase 2).** Phase A.5 passed on the second round of
the fresh user-approved budget. The source-derived validator, exact preset fallback repair, and
all path-sensitive negative controls are GREEN. The original per-phase boundary could not turn
GREEN before the real-tree drift was repaired because `test_ac_001_living_docs_match_source_contracts`
intentionally validates the checkout; Phases 1 and 2 therefore ran as one serial barrier without
changing scope.

**Newly-reachable window:** future changes to live stages, agent/skill inventories, release
version sources, required document presence, and current-versus-historical discovery now reach a
keyed documentation verdict. `test_ac_001_living_docs_match_source_contracts`,
`test_ac_002_doc_contract_rejects_representative_mutations`,
`test_ac_005_each_core_document_is_mandatory`,
`test_ac_005_changelog_boundary_is_enforced_by_repository_validation`,
`test_ac_006_each_locale_must_match_the_complete_source_inventory`, and
`test_ac_007_preset_fallbacks_use_the_canonical_six_stage_pipeline` enter that window in this
same change. The absent case is deletion of any mandatory core document and is covered explicitly.

### Phase 2: Living documentation repair

- `depends_on`: Phase 1
- `parallel_group`: serial
- `merge_hazards`: Every document must satisfy the Phase 1 parser and bilingual completeness
  contract; concurrent prose edits can invalidate the same catalog.
- Scope in: `README.md`, `README.ko.md`, `TECH_SPEC.md`, `docs/ARCHITECTURE.md`,
  `docs/HOW-IT-WORKS.md`, `docs/HOW-IT-WORKS.ko.md`, `docs/CONTRIBUTING.md`, and
  `docs/release-checklist.md`.
- Scope out: historical directories, old CHANGELOG sections, `work-docs/` other than this task,
  and narrative generation.
- Work: correct version declarations, six-stage count/order, validator names, complete visible
  agent/skill catalogs, mechanism summary/count, and five-file maintainer guidance.
- Exit criterion: `uv run pytest -q tests/structural/test_documentation_contract.py tests/structural/test_documented_commands_exist.py tests/unit/test_doc_truth.py`
- `risk`: medium
- Rollback point: revert only the eight living-doc edits while retaining Phase 1 RED evidence.

**Status: DONE (combined serial barrier with Phase 1).** The eight living docs now publish the
0.59.0 six-stage contract, complete source-derived agent/skill inventories, M1-M19 mechanism
identity, five version sources, and the correct `review → verify → wrapup` order. Focused
documentation, documented-command, lint, and type checks are GREEN.

### Phase 3: Two-boundary release identity enforcement

- `depends_on`: Phase 2
- `parallel_group`: serial
- `merge_hazards`: Workflow dependency order and version readers are shared release contracts.
- Scope in: `src/harness_maker/release_identity.py`, `tests/unit/test_release_identity.py`,
  `.github/workflows/release.yml`, and the release checklist invocation.
- Scope out: OIDC permissions, publish endpoints, environment approval policy, artifact build,
  release-note generation, and public Typer command surface.
- Work: implement local equality and remote classification with fixed endpoints/bounded I/O;
  add prepublish and required postpublication workflow calls plus dependency assertions.
- Exit criterion: `uv run pytest -q tests/unit/test_release_identity.py tests/structural/test_documentation_contract.py`
- `risk`: high
- Rollback point: remove the two workflow steps/job and release-identity module/tests without
  changing existing publish jobs.

**Status: BLOCKED at Phase A.5 after two test-reviewer rounds.** Round 1 findings were repaired
with path-complete local mismatches, S3-bound names, exact remote endpoints, request-failure
controls, and blocking workflow assertions. Round 2 retained two overconstraints:

1. the AC-003 AST oracle rejects network imports anywhere in `release_identity`, including a
   correct postpublication-only function required by AC-008; and
2. the malformed-payload oracle requires a PyPI request after malformed GitHub evidence already
   permits a correct fail-fast `UNAVAILABLE` result.

No `release_identity` production module or workflow step/job has been written. The Phase 3 RED
state remains one collection error (`ModuleNotFoundError: harness_maker.release_identity`) with
zero tests executed. `[boundaries] comparison not performed — blocked exit`.

**Resume disposition (2026-09-22):** the user approved the recommended test-only Path A. The
AC-003 oracle now reloads and executes only the prepublish path under an import guard, allowing
remote-only local imports. The malformed-response oracle retains exact endpoint/timeout checks
while allowing a GitHub-malformed fail-fast before PyPI. Production remains untouched until a
fresh Phase A.5 budget passes.

**Status: DONE.** The fresh Phase A.5 review passed. `release_identity.py` now enforces the
local tag/five-source/visible-doc equality boundary without importing a network client on that
path, and classifies authoritative GitHub/PyPI evidence as match, mismatch, or unavailable with
bounded retries. The release workflow blocks publication dependencies on the local check and
adds a required post-GitHub-release remote identity job without changing OIDC, endpoints,
artifact production, or the existing publish order.

**Newly-reachable window:** a tag that differs from any local version or visible documentation
identity, and a published GitHub/PyPI version that is absent, malformed, timed out, or unequal,
now fail a required release boundary. The same change adds focused tests for each local path,
malformed/request-failure remote evidence, exact endpoints/timeouts, and workflow dependency
order.

### Phase 4: Integrated verification and feedback disposition

- `depends_on`: Phase 3
- `parallel_group`: serial
- `merge_hazards`: Final checks read every prior artifact and update this PLAN.
- Scope in: task SPEC machine bindings, this PLAN status/Feedback, targeted tests, lint, format,
  type checks, and one full test pass.
- Scope out: version bump, tag creation, publication, intent closure, and authoritative trial
  enrollment by a non-collector.
- Work: mark machine AC test bindings, run targeted and full verification, record intent
  observation → decision evidence, and leave real-task enrollment pending for the named collector.
- Exit criterion: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src tests && uv run pytest -x --tb=short`
- `risk`: medium
- Rollback point: retain implementation evidence, mark the phase blocked, and do not advance.

**Status: DONE.** All eight machine ACs are bound to collected pytest nodes; strict machine-SPEC
validation is `ok` with quality 85 and approval state `clear`. The selector correctly escalated
to the full suite because its own configuration and unmapped task documents changed. Final
verification completed with ruff, format, strict mypy, and `9219 passed, 104 skipped, 3 xfailed`
(`0 failed`). Four live Claude plugin tests skip only on the explicit weekly-limit platform
response; a negative control proves ordinary plugin failures remain failures. The new structural
gate also has a mutation receipt backed by an observed RED deletion.

### Boundary comparison

- `.github/workflows/release.yml` crossed its path boundary only for the approved local identity
  prerequisite and required post-publication identity job. OIDC permissions, publish endpoints,
  environments, artifacts, and TestPyPI → PyPI → GitHub Release order are unchanged.
- `work-docs/PLAN-docs-release-sync.md` and `work-docs/RESEARCH-docs-release-sync.md` are the
  current task's owned records; no other task record was rewritten.
- `docs/adr/`, `docs/migration/`, and `CHANGELOG.md` were not changed.
- No version bump, tag, publication, public CLI verb, commit, or intent closure occurred.

## 🚧 Contract Boundaries

### Do not change

- `.github/workflows/release.yml` — do not alter OIDC permissions, publish endpoints, environment gates, artifact production, or existing publish order beyond adding required identity dependencies
- `docs/adr/` — historical decisions
- `docs/migration/` — historical migration instructions
- `work-docs/` — do not rewrite other task records
- `CHANGELOG.md` — do not rewrite old release sections
- Advisory: no version bump, tag, publication, public CLI verb, or intent closure belongs to this task

## 🧪 Testing Strategy

- Unit tests parse each version source independently and cover remote match, mismatch,
  malformed response, timeout, and unavailable states without network.
- Structural tests compare live enums/templates with visible document sections and the
  provenance-backed mechanism fixture.
- Property-style parameterized tests clone valid document text into temporary files and inject
  each historical defect independently, asserting keyed rejection.
- Workflow tests parse YAML/text structure to prove local checks precede publication and the
  required remote job depends on `github-release` without `continue-on-error`.
- Existing documented-command, doc-truth, README install, release, lint, type, and full pytest
  gates run after focused GREEN.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Loose prose regex produces false confidence | medium | high | Parse bounded visible sections; add original-mutant negative controls and non-vacuity assertions |
| Remote propagation delay fails a valid release | medium | high | Bounded retries with explicit unavailable classification; run only after GitHub Release and PyPI publication |
| Historical evidence is rewritten or gated | low | high | Exact exclusion policy and fixtures for every excluded class/CHANGELOG boundary |
| English/Korean catalogs drift together incompletely | medium | high | Compare each locale independently with the complete source inventory before comparing locales |
| Mechanism oracle is circular | medium | medium | Separate provenance-backed golden fixture plus heading/count consistency |
| Base intent rule is dirty outside the task branch | high | medium | Do not overwrite or land it from this worktree; link it as shared intent evidence and report at wrapup |

## ✅ Success Criteria

- [x] S1 / AC-001: all eight living docs match their declared mechanical contracts and visible
  catalogs.
- [x] S2 / AC-002: every representative mutation, including catalog/mechanism and marker-bypass,
  flips the owning verdict to failure.
- [x] S3 / AC-003/004/008: branch checks are hermetic, prepublish identity blocks locally, and
  remote mismatch/unavailable prevents successful release completion.
- [x] S4 / AC-005: core/current discovery and exact historical exclusions are proven.
- [x] S5 / AC-006: each locale equals complete live inventories while arbitrary surrounding
  prose remains free.
- [x] S6 / AC-007: every preset fallback equals the canonical six-stage pipeline.
- [x] Focused lint, format, strict mypy, targeted pytest, and one full suite pass.
- [x] No commit, tag, publication, or intent closure occurs during execute.

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| User rule and authorization in conversation on 2026-09-22; base `.claude/intent.yaml` living-doc rule | `WORLD-INTENT-CLOSED-LOOP` and project rule | recorded in shared intent; task linkage recorded in SPEC/PLAN | Diagnose current gaps and continue through authorized implementation | agent | user consent + approved SPEC | Execute Phases 1–4, then review/verify |
| [[RESEARCH-docs-release-sync]] gap inventory and latest-release evidence | `WORLD-INTENT-CLOSED-LOOP` | recorded in task artifacts; shared trial update pending | Repair current drift and add recurrence gates | agent | approved task scope | Named trial collector reconciles this task from PLAN evidence |
| User approved stuck Path A in conversation on 2026-09-22 | `WORLD-INTENT-CLOSED-LOOP` / Phase 1 | recorded in task PLAN; no intent mutation required | Preserve the approved SPEC and repair four RED oracle seams before production | user + agent | explicit user approval | Re-run Phase A.4 and a fresh Phase A.5 budget |
| Phase 3 A.5 terminal FAIL on 2026-09-22 | `WORLD-INTENT-CLOSED-LOOP` / S3 | recorded in task PLAN; shared trial update pending | Stop before release implementation because two tests overconstrain valid implementations | agent | execute quality gate | User selects a stuck-agent unblock path |
| User approved the Phase 3 test-only unblock in conversation on 2026-09-22 | `WORLD-INTENT-CLOSED-LOOP` / S3 | recorded in task PLAN; no intent mutation required | Narrow RED oracles to the approved prepublish path and terminal remote classification | user + agent | explicit user approval | Re-run Phase A.4 and a fresh Phase A.5 budget |
| Execute GREEN evidence: all ACs bound, strict SPEC clear, release/documentation gates and full suite pass | `WORLD-INTENT-CLOSED-LOOP` / docs-release-sync | recorded in task PLAN; shared trial update pending | Current release-facing docs are synchronized and recurrence is mechanically blocked | agent | approved SPEC + user authorization | Named trial collector reconciles this terminal task evidence; review is the next workflow stage |
| Review grade A after one repair round and two confirmation passes; all seven lenses complete, full suite green | `WORLD-INTENT-CLOSED-LOOP` / docs-release-sync | recorded in REVIEW and task PLAN; shared trial update pending | Accept implementation quality; retain two single-model P1 observations for human judgment | agent | `$hm-review` consensus and confirmation gates | Human reviews the manual-only items before wrapup; named trial collector reconciles terminal evidence |
| User approved both remaining manual-only P1 repairs; source-derived version and real-prose mutation gates pass focused and full verification | `WORLD-INTENT-CLOSED-LOOP` / docs-release-sync | recorded in REVIEW and task PLAN; shared trial update pending | Close both manual findings and clear the review judgment gate | user + agent | explicit user approval + green verification | Continue to verify; named trial collector reconciles terminal evidence |
| Verify Check 6: `change` operation unsatisfied and no valid waiver; target SPEC is newly added in this task worktree | `WORLD-INTENT-CLOSED-LOOP` / docs-release-sync | recorded in task PLAN; shared trial update pending | Stop verify at the first failing gate without override | agent | `$hm-verify` Check 6 | Correct the SPEC-need operation classification through the spec workflow, then rerun `$hm-verify docs-release-sync` |
| Spec workflow recovery on 2026-09-23: the approved SPEC was added by this task, while PLAN metadata incorrectly recorded `change` and included an extra `SPEC-` target prefix | `WORLD-INTENT-CLOSED-LOOP` / docs-release-sync | PLAN frontmatter corrected to `add` / `docs-release-sync`; shared trial update pending | Use the actual operation and canonical task slug; no waiver or artificial SPEC edit | agent | existing approved SPEC + `spec_need op-check` contract | Rerun `$hm-verify docs-release-sync` and land the bookkeeping correction only after all checks pass |
| Wrapup verification on 2026-09-23: corrected SPEC-need metadata passed all gates; lint, format, strict mypy, and the full suite (`9260 passed, 100 skipped, 3 xfailed`) are green | `WORLD-INTENT-CLOSED-LOOP` / docs-release-sync | recorded in task PLAN; shared trial update pending | Land the bookkeeping correction and stop because the authorized sync/prevention work is complete | agent | user-requested wrapup + green verification + clean REVIEW drift verdict | Named trial collector reconciles terminal evidence; no additional task work remains |
| User-authorized metric measurement on 2026-09-23: lead time `5.5h` and change failure rate `0%` meet targets; post-merge churn `16.9%`, unsourced-step share `45.2%`, and dead-rendered bytes `21.7%` remain above target; the primary `intent_world_closed_loop_cycles` metric remains manual/unmeasured and the wiki-fact window has 25 days left | `WORLD-INTENT-CLOSED-LOOP` and project metrics | five automated values recorded in `.claude/intent/metrics.yaml`; primary intent outcome and wiki-fact metric remain pending | Keep the intent open; do not infer attainment from this task or proxy metrics | user + agent | user-authorized measurement and explicit keep-open decision | Named collector reconciles this task's terminal trial evidence; measure the wiki-fact metric after 2026-10-17 |

Trial enrollment remains pending because the authoritative collector is
`codex-thread-01a0c683-3cde-7f40-9d06-e871e86c6da4`; this session does not claim ownership or
write the base-root trial PLAN.
