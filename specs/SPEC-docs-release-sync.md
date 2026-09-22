---
type: spec
task_slug: docs-release-sync
status: approved
created: 2026-09-22
tags: [harness-maker, spec, python, documentation, release, drift-prevention]
tier: 1
test_framework: pytest
interview_rounds: 2
intent: WORLD-INTENT-CLOSED-LOOP
research_doc: "[[RESEARCH-docs-release-sync]]"
summary: "Synchronize living docs and block future code, documentation, and release drift"
---

# SPEC: Release documentation synchronization

## 🎯 Intent

The living documentation currently disagrees with the released `v0.59.0` source on workflow
topology, pipeline order, validator names, inventories, and release metadata. Repair those
claims and turn every mechanically decidable claim into a source-derived CI or release
contract so that the same drift cannot ship silently again.

This task is the first real feedback-continuity task linked to
`WORLD-INTENT-CLOSED-LOOP`: the user-added documentation rule led directly to measured gaps,
this SPEC, and authorized execution without requiring the user to reconnect the observation.

## 🌅 Outcomes

- A reader following either README or either HOW-IT-WORKS guide sees the six live atomic
  stages in the correct `research → spec → execute → review → verify → wrapup`
  order and no current-tense instruction to use the retired `plan` stage or `plan-validator`.
- Living English and Korean reference surfaces visibly describe the same complete
  contract-bearing stage, agent, skill, mechanism, and release facts; a detached hidden
  marker cannot satisfy the contract while contradictory prose remains.
- The five release-version sources, declared living-doc release identity, local tag, and
  remote GitHub/PyPI identities are checked at the boundary where each fact is authoritative.
- CI fails when a future edit recreates any observed mechanical mismatch, with a negative
  control proving each scanner rejects a representative defect.
- Historical records remain historical; the freshness gate does not force edits to ADRs,
  migrations, old CHANGELOG sections, or work documents.

## 📋 In-Scope Scenarios

### S1: Living documents match the shipped workflow

**Given** the repository's live `AtomicStage`, canonical autonomy pipeline, complete template
agent and skill inventories, provenance-backed M1–M19 golden catalog, and five version sources
**When** the living documentation contract test runs
**Then** `README.md`, `README.ko.md`, `TECH_SPEC.md`, `docs/ARCHITECTURE.md`,
`docs/HOW-IT-WORKS.md`, `docs/HOW-IT-WORKS.ko.md`, `docs/CONTRIBUTING.md`, and
`docs/release-checklist.md` agree with those sources for every contract they publish
**And** the current known mismatches are corrected rather than hidden by exemptions.

### S2: A recreated documentation drift fails CI

**Given** a clean checkout whose living-documentation contract passes
**When** an isolated test mutation reintroduces each representative defect — seven stages,
`plan` as live, `wrapup` before `verify`, `plan-validator`, missing and extra agent entries,
missing and extra skill entries, an incorrect mechanism id/count, a four-file version policy,
or a stale declared docs release
**Then** the owning contract check fails for the mutated fact
**And** non-vacuity controls prove that the source inventories and mutation corpus are nonempty.

### S3: Development and publication identities are checked at the correct boundaries

**Given** ordinary branch CI may be ahead of the latest public release
**When** normal CI runs
**Then** it validates hermetic source-to-doc and five-file source-version consistency without
requiring GitHub or PyPI to equal `HEAD`
**And Given** a `v*` tag is about to publish
**When** the release quality gate runs before `build` and every publish job
**Then** the tag, all five source versions, and the declared living-doc release identity agree
without contacting GitHub Releases or PyPI
**And Given** PyPI publication and GitHub Release creation have completed
**When** the required post-publication identity job runs after `github-release`
**Then** GitHub and PyPI must both report the same version, and either a mismatch or unavailable
remote evidence fails that job rather than reporting the release workflow complete.

### S4: Historical evidence is not rewritten or gated as current prose

**Given** the eight core living documents and any Markdown under `docs/`
**When** the living-documentation gate discovers files
**Then** the eight core files are always checked, and additional `docs/**/*.md` files are
scanned for current operational claims unless their relative path begins with `adr/`,
`migration/`, `observability/`, `followups/`, or `assets/`, or is the explicitly frozen
historical record `reference/pre-change-checklist.md`
**And** `work-docs/**` is outside discovery, while only `[Unreleased]` plus the first real
release section of `CHANGELOG.md` is treated as current, matching the existing command gate.

### S5: English and Korean contract-bearing guidance stays aligned

**Given** the English and Korean README and HOW-IT-WORKS pairs
**When** their visible contract-bearing sections are parsed and compared
**Then** each locale's stage sequence equals the canonical pipeline and each current agent and
skill catalog equals the complete source-derived set, not merely the same subset
**And** markers, when used to delimit a visible section, cannot substitute for validating that
section's reader-visible content
**And** locale-specific prose may differ without forcing byte or heading parity.

### S6: Runtime fallbacks cannot resurrect a retired stage

**Given** a render path uses a preset template fallback rather than an explicit autonomy
pipeline
**When** the fallback is evaluated
**Then** it yields the canonical six-stage pipeline
**And** no preset template names `plan` as a live fallback stage.

## 🚫 Non-Goals

- Generating all narrative documentation from source templates.
- Rewriting historical ADRs, migrations, completed work documents, archived incident notes,
  or old CHANGELOG release sections.
- Requiring network access during ordinary unit or pull-request CI.
- Proving every natural-language claim semantically correct with regexes or keyword counts.
- Changing the six-stage workflow, release version, agent/skill product surface, or intent
  lifecycle beyond correcting the stale Side fallback.
- Treating a version-banner replacement alone as evidence that a long-form guide is current.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Existing structural and release contract suite |
| Ordinary CI | Hermetic, no network | Development `HEAD` may legitimately be ahead of PyPI/GitHub |
| Release verification | Network allowed only at tag/post-release boundary | Remote publication identity is authoritative only there |
| Source of truth | `AtomicStage`, canonical pipeline configuration, complete template inventories, five version files; provenance-backed golden only for M1–M19 because no code registry exists | Avoid circular claims and state the one deliberate golden honestly |
| Living-doc discovery | Eight core files plus recursive nonhistorical `docs/**/*.md`; exact excluded directories/file and CHANGELOG boundary are defined in S4 | Prevent both history rewriting and silent omissions |
| Localization | Contract parity, not byte/heading parity | English and Korean prose have different structure and depth |
| Test quality | Non-vacuity plus representative negative controls | A scanner that finds nothing or accepts the original mutants must fail |
| Compatibility | Python 3.12+, existing GitHub Actions and release workflow | Preserve the published toolchain and release path |
| Security | Remote checks use fixed project endpoints and bounded timeouts; no shell interpolation | Release metadata is external input |

## 🔒 Irreversible Decisions

None. The documentation contract, CI checks, and release-preflight placement are reversible
without a schema migration, public API removal, permission expansion, or new dependency.

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit + manual | `test_living_docs_match_source_contracts`; review the corrected rendered prose |
| S2 | property | `test_doc_contract_rejects_representative_mutations` |
| S3 | unit + integration | `test_branch_check_is_hermetic`; `test_prepublish_identity_is_local_and_blocking`; `test_remote_identity_classifies_match_mismatch_and_unavailable`; release workflow dependency assertions |
| S4 | property | `test_living_doc_discovery_policy_and_changelog_boundary` |
| S5 | property | `test_localized_docs_publish_the_same_contracts` |
| S6 | unit | `test_preset_fallbacks_use_the_canonical_six_stage_pipeline` |

### AC-001: living documentation matches source contracts

The declared living-document corpus agrees with source-derived stage count/order, live and
retired validator identity, complete agent/skill inventory claims, five-file version membership,
and declared release identity. The M1–M19 mechanism catalog is compared with a separate
provenance-backed golden fixture because the code has no mechanism registry; the test also
checks the architecture heading ids and its stated count agree internally. Every validated
record is extracted from visible contract-bearing prose or a visible table, never from a
detached marker. The test reports the file and contract key for each mismatch rather than a
single aggregate false result.

### AC-002: representative drift mutations are rejected

For each observed defect class, applying that defect to an isolated valid document set changes
the contract verdict from pass to fail. The required mutation set includes stage count, retired
stage, pipeline order, validator identity, missing and extra agent entries, missing and extra
skill entries, mechanism id/count, release-version file count, docs release identity, and a
correct marker beside contradictory visible prose. The test asserts the mutation and every
source inventory are nonempty and that every mechanically checked contract class owns at least
one rejecting mutation.

### AC-003: ordinary CI remains hermetic

The branch/PR contract check reads repository files and live Python/template inventories only.
Removing network access cannot change its verdict, and no GitHub/PyPI client is imported or
invoked on this path.

### AC-004: pre-publish identity is local and blocking

Before `build`, TestPyPI, PyPI, or GitHub publication, the tag version must equal all five source
version files and the declared release identity extracted from visible living-doc content. A
mismatch exits nonzero and blocks every downstream publish job. This pre-publish path performs
no GitHub Release or PyPI network lookup, because the new remote release does not exist yet.

### AC-005: historical exclusions and living-doc discovery are both effective

The eight core files named in S1 are mandatory. Additional Markdown under `docs/` is discovered
recursively except the exact directory/file exclusions in S4; `work-docs/**` is never scanned.
For CHANGELOG, the current surface is exactly `[Unreleased]` plus the first real release
section. Fixtures prove a current operational claim in an included file fails, the same token
in every excluded class does not, and the second real release section is historical.

### AC-006: localized contract parity survives prose differences

The English/Korean README pair and HOW-IT-WORKS pair yield identical normalized contract data
for stage sequence and complete current agent/skill inventories while accepting unrelated
locale-specific paragraphs and headings. Deleting or adding one catalog entry in either locale,
or leaving contradictory visible prose outside a valid marker, must fail.

### AC-007: every preset fallback uses the canonical six-stage pipeline

Rendering or evaluating each preset without an explicit autonomy pipeline produces exactly
`research, spec, execute, review, verify, wrapup`; no preset template fallback contains the
retired `plan` value.

### AC-008: post-publication remote identity is required

Given fixed GitHub and PyPI metadata fixtures, the remote checker reports match only when both
equal the already validated tagged source version, mismatch when either differs, and unavailable
when a request fails or returns unusable data. Mismatch and unavailable both exit nonzero. The
release workflow runs this required job after `github-release`; it is not `continue-on-error`,
and successful workflow completion depends on it.

## ❓ Open Questions

None. The DRI approved the recommended hybrid approach and authorized execution on
2026-09-22.

## 🔎 Spec Validation

`spec-validator` returned `MAJOR_REVISION` in its single advisory pass. All five critiques were
accepted and repaired without adding an irreversible decision or expanding beyond the approved
scope:

- split local blocking pre-publish identity from required post-publication remote parity;
- bound validation to complete visible catalogs so detached markers cannot hide stale prose;
- replaced the circular mechanism source with a provenance-backed golden and internal heading
  consistency check;
- enumerated the exact living/historical discovery and CHANGELOG boundary; and
- extended negative controls to agent, skill, mechanism, and marker-bypass mutations.

The independent Codex result was `invoked`; all five findings were accepted by the validator.
The validator reported `irreversible-decisions` and `scope-boundary` clean. Per the one-pass
contract, no second critic dispatch is performed.

## 🔍 Refinement Decisions

- Round 1: selected the hybrid repair-plus-contract approach; scoped living documents,
  historical exclusions, hermetic CI, release-only remote checks, and intent linkage.
- Round 2: confirmed source-derived oracles, bilingual contract parity, `pytest`, explicit
  mutation controls, and no irreversible decisions; the DRI approved the SPEC.
