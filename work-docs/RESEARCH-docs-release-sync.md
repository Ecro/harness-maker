---
type: research
task_slug: docs-release-sync
status: complete
created: 2026-09-22
tags: [harness-maker, research, python, documentation, release, drift-prevention]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://github.com/Ecro/harness-maker/releases/tag/v0.59.0
  - https://pypi.org/project/harness-maker/0.59.0/
related_docs:
  - "[[SPEC-plan-stage-absorption]]"
  - "[[PLAN-plan-stage-absorption]]"
  - "[[REVIEW-plan-stage-absorption-2026-09-20]]"
  - "[[PLAN-harness-diet]]"
  - "[[PLAN-codex-stage-invocation]]"
summary: "Repair living docs and add source-derived CI contracts that block release-time drift"
---

# Research: Release documentation synchronization

## 🎯 Recommended Direction

Adopt a hybrid documentation contract: repair the current living documentation against
the `v0.59.0` release and current source tree, then add source-derived structural tests
and a release-preflight check for facts that can be decided mechanically. Keep historical
ADRs, migration guides, CHANGELOG entries, and work documents outside the living-doc
freshness rule unless they make a current-tense operational claim.

This is preferable to either a prose-only checklist or full documentation generation.
The repository already derives command existence from the live Typer app and rendered
stage enum, but the passing documentation suite does not check stage count, pipeline order,
current validator names, cross-language catalog parity, or freshness markers. Those are the
observed failure classes. Narrative explanations still require maintainer judgment, so the
release process should combine deterministic checks with one explicit semantic review of
the release-facing documents.

## 🔍 Refinement Decisions

- Discovery lens: technical architecture / implementation and risk / release compliance.
- User clarification added prevention to the scope: future code/document divergence must
  fail CI or release preflight, not merely be corrected once.
- The authoritative published baseline is `v0.59.0`: GitHub reports a non-draft,
  non-prerelease release published on 2026-09-21, and PyPI reports `0.59.0`. The checkout's
  five version sources and latest tag also read `0.59.0`, while `HEAD` contains additional
  `[Unreleased]` work. Therefore a gate must distinguish published-release identity from
  development-branch behavior rather than assuming they are always identical.
- Existing project history explains the `plan` retirement and six-stage target in
  [[SPEC-plan-stage-absorption]] and [[PLAN-plan-stage-absorption]]. That task required the
  CHANGELOG and `/hm:help` announcement, but did not make the broader living-doc corpus an
  acceptance boundary.
- Relevant memory: `[fail:design remediation-instructs-refused-action]` shows that runnable
  documentation claims need executable checks; `[wiki:pattern universal-cross-platform-install-prompt]`
  identifies README installation prose as a high-impact contract; `[fail:design
  worktree-finalize-pulls-orphan-wip-into-main]` requires all writes to stay in this task
  worktree and warns against merging unrelated base changes.

### Observed gap inventory

| Surface | Current claim | Authoritative evidence | Gap |
|---|---|---|---|
| `docs/HOW-IT-WORKS.md` | Current as of `0.9.3` | GitHub/PyPI/latest tag and source version are `0.59.0` | Explicit freshness marker is stale |
| `docs/HOW-IT-WORKS.ko.md` | Current as of `0.7.1` | Same `0.59.0` baseline | Explicit freshness marker is stale and differs from English |
| `docs/HOW-IT-WORKS{,.ko}.md` and `docs/ARCHITECTURE.md` | Seven atomic stages, including `plan` | `AtomicStage` has six values; `RETIRED_STAGES={"plan"}`; v0.59.0 CHANGELOG removes `/hm:plan` | Current workflow topology is wrong |
| `README.md` and `README.ko.md` | Recommended order ends `review → wrapup → verify` | Configured/default pipeline ends `review → verify → wrapup`; verify is the pre-wrapup gate | Operational sequence is unsafe and inconsistent with code |
| HOW agent/skill reference | Still titles `plan-validator`; omits several shipped agents/skills, especially in Korean | Template inventories ship `spec-validator`, `code-verifier`, `judgment-reviewer`, `stage-delegate`, `targeted-test-selection`, `intent-layer`, and `project-knowledge` | Reference catalog no longer describes the shipped surface |
| `README.md` / `docs/CONTRIBUTING.md` | 14 mechanisms; four version files | `docs/ARCHITECTURE.md` declares M1–M19; release checklist and source tree use five version files including `.codex-plugin/plugin.json` | Maintainer guidance is internally contradictory |
| Release gates | Command-name and install tests pass | Focused suite passed on all non-skipped checks while every gap above remained | Existing tests do not prevent the observed drift |
| `scripts/release_smoke.py` / release checklist | Build, install, CLI smoke, and five-file version sync | Neither checks living-doc release markers, stage topology/order, or inventories | A release can publish with stale current-tense docs |

## 🛠️ Approaches Found

### Approach A: One-time prose correction

| Field | Content |
|---|---|
| Assumption | Reviewers will remember every documentation surface on later behavior changes. |
| Evidence | Direct edits can close every currently observed gap, but the existing green suite already demonstrates that memory and review alone did not do so. |
| Trade-off | Lowest immediate cost; no recurrence protection. |
| Compatibility | No production-code change and minimal test impact. |
| Risk | High: the next stage, agent, or release change can silently recreate the same class. |

### Approach B: Fully generate reference documentation

| Field | Content |
|---|---|
| Assumption | All useful narrative can be represented in source metadata and templates without making the source harder to maintain. |
| Evidence | Commands, stages, agents, skills, and version identities are enumerable, so some tables can be generated. Long rationale, examples, translations, and historical context are not equivalent to inventory data. |
| Trade-off | Strong parity for generated sections, but large migration and template-maintenance cost; generated prose is harder to curate. |
| Compatibility | Conflicts with the repository's intentionally hand-authored long-form guide and localization. |
| Risk | Medium-high: either over-generation degrades documentation quality or hand-written surrounding prose still drifts. |

### Approach C: Hybrid source-derived contracts plus semantic release review

| Field | Content |
|---|---|
| Assumption | Stable mechanical claims can be separated from narrative claims. |
| Evidence | The repository already uses this pattern for documented Typer and `/hm:` command existence. Extending the normative test site to stage count/order, shipped inventories, five-file version identity, and declared living-doc freshness directly covers the observed misses. |
| Trade-off | Adds a small manifest/marker contract and test maintenance; semantic claims still need a human release check. |
| Compatibility | Fits existing structural pytest gates, release workflow, `wrapup_docs`, and source-derived inventory conventions. |
| Risk | Low-medium: a poorly scoped text scanner can create false positives, so tests should parse explicit markers/sections or source data rather than scan arbitrary prose. |

## ⚠️ Pitfalls

- **Equating `main` with the latest published release.** This checkout is already ahead of
  `v0.59.0` and has an `[Unreleased]` section. A network comparison on every ordinary CI run
  would reject legitimate development. Enforce source/doc parity in CI and source/tag/PyPI
  parity at the release boundary.
- **Rewriting history.** Version numbers in ADRs, migration guides, old CHANGELOG sections,
  and incident write-ups are evidence, not stale current documentation. Discovery-based
  tests must have an explicit living-doc scope and historical exclusions, following the
  precedent in `tests/structural/test_documented_commands_exist.py`.
- **Testing prose by loose substring.** Existing history records multiple scanners that
  passed vacuously or missed spelling/case variants. New checks need non-vacuity and negative
  controls and should bind to explicit headings, markers, or parsed source inventories.
- **Treating a version-stamp bump as semantic synchronization.** Updating `0.9.3` to `0.59.0`
  without correcting the seven-stage topology would make the document more misleading.
- **Duplicating a normative rule.** Stage order should come from the configured/default
  pipeline, stage names from `AtomicStage`, and release identity from the five version
  sources/tag. Documentation tests should defer to those sources rather than maintain a
  second hard-coded list.
- **Ignoring localization.** English already has newer intent and skill sections that Korean
  lacks. A release marker shared by both files is insufficient unless contract-bearing
  inventories are checked in both languages.
- **Relying only on external availability.** GitHub and PyPI are the published authorities
  ([GitHub v0.59.0](https://github.com/Ecro/harness-maker/releases/tag/v0.59.0),
  [PyPI 0.59.0](https://pypi.org/project/harness-maker/0.59.0/)), but normal unit tests should
  remain hermetic. Network publication checks belong in the tag/release workflow or a
  maintainer-invoked post-release check.

## ❓ Open Questions

1. Should explicit version banners in long-lived guides be source-derived and updated on
   every release, or removed in favor of a neutral "tracks the current source tree" marker?
   Recommendation: retain one machine-readable `docs_version` marker so release freshness is
   decidable, and state clearly that `main` may include unreleased behavior.
2. Which files are normative living docs? Recommendation: `README.md`, `README.ko.md`,
   `TECH_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/HOW-IT-WORKS.md`,
   `docs/HOW-IT-WORKS.ko.md`, `docs/CONTRIBUTING.md`, and `docs/release-checklist.md`; exclude
   `docs/adr/**`, `docs/migration/**`, `work-docs/**`, and historical CHANGELOG sections.
3. How much inventory should be generated? Recommendation: keep prose hand-authored, but
   make tests derive and compare contract-bearing stage/order, agent/skill names, command
   names, mechanism count, and five-file version membership.
4. Should publication verification block after PyPI/GitHub publish? Recommendation: block
   the tag before publish on local source/doc contracts, then make post-release remote parity
   a required verification job. A post-publish mismatch cannot be repaired in place.

## 📚 Sources

- [GitHub release v0.59.0](https://github.com/Ecro/harness-maker/releases/tag/v0.59.0) —
  published release identity and timestamp.
- [PyPI harness-maker 0.59.0](https://pypi.org/project/harness-maker/0.59.0/) — published
  package identity.
- `src/harness_maker/models.py` — live six-stage `AtomicStage` enum and retired `plan` entry.
- `.claude/harness.yaml` and `src/harness_maker/templates/harness-yaml/*.yaml.j2` — active
  pipeline order and one remaining stale Side fallback.
- `CHANGELOG.md` — v0.59.0 stage-retirement contract and current unreleased delta.
- `tests/structural/test_documented_commands_exist.py` — existing source-derived command
  checks and historical-document exclusions.
- `scripts/release_smoke.py` and `docs/release-checklist.md` — current release boundary.

## 🔗 Related Internal Docs

- [[SPEC-plan-stage-absorption]] — approved outcome and acceptance boundary for retiring
  `/hm:plan`.
- [[PLAN-plan-stage-absorption]] — implementation decisions and six-stage migration.
- [[REVIEW-plan-stage-absorption-2026-09-20]] — review evidence for the stage retirement.
- [[PLAN-harness-diet]] — prior command-surface reduction and source-derived surface lessons.
- [[PLAN-codex-stage-invocation]] — current six-stage Codex invocation guidance.
