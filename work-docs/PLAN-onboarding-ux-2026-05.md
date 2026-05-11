---
type: plan
task_slug: onboarding-ux-2026-05
status: complete
created: 2026-05-12
tags: [harness-maker, plan, python, ux, onboarding, locale, second-brain]
research_doc: "[[RESEARCH-onboarding-ux-2026-05]]"
interview_rounds: 2
adrs: 7
validator_outcome: APPROVED
summary: "Locale-first onboarding prose, configure guidance, Deep Interview locale contracts, and UX contract tests"
---

# PLAN — onboarding UX 2026-05

## 🎯 Executive Summary

Improve harness-maker onboarding without adding a new runtime receipt generator. The implementation will make `/harness-maker:make` ask locale first, then keep all user-facing setup prose in that selected locale; strengthen slash-command "receipt" prose so users understand installed roots, backups, preserved edits, target leftovers, review trade-offs, and Second Brain boundaries; update `/hm:configure` to guide advanced follow-up settings; and lock the Deep Interview locale contract across stage templates.

Key decisions: [[#ADR-001 Slash-command prose is the receipt source for this iteration]], [[#ADR-002 Explain review cost as trade-offs, not estimates]], [[#ADR-003 Locale-first make and all interactive decision surfaces]], [[#ADR-004 Second Brain starts read-first and points advanced setup to configure]], [[#ADR-005 Configure uses multi-select with per-setting explanations]], [[#ADR-006 Failure criteria combine locale, safety receipt, and Second Brain understanding]], [[#ADR-007 Structural tests plus snapshot regeneration are required]].

Estimated impact: medium user-facing UX improvement, low-to-medium implementation risk. Most changes are template and structural-test changes; no new dependency or public Python API is required.

## 📚 Prior Work

- [[work-docs/RESEARCH-onboarding-ux-2026-05.md]] recommends locale-locked, receipt-first progressive onboarding.
- [[work-docs/RESEARCH-make-ux-gaps-2026-05.md]] identified the earlier make/configure gaps. Many baseline pieces now exist: `/hm:make`, `/hm:configure`, `--dry-run`, uninstall, and Second Brain flags.
- [[work-docs/RESEARCH-deep-interview-llm-delegation.md]] and [[work-docs/PLAN-deep-interview-llm-delegation.md]] define the 3-layer Deep Interview gate now present in research/spec/plan/loop.
- `.claude/memory/wiki.md` records that slash-command interview coverage must match `interview.py`, and that writable Second Brain folders must include `project_id` as a path segment.
- `.claude/memory/failures.md` records the snapshot regeneration hazard: finalize template changes into the main repo before running `tests/snapshot/regenerate.py`.
- Stage-aware Second Brain search failed during planning because `.claude/harness.yaml` currently has a provenance block plus YAML document body that the helper parses as multiple YAML documents. This is not part of this task's implementation scope, but it is recorded as a risk.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Receipt source | Architecture | Where should the Decision Receipt source of truth live? | A Python-generated, B slash-command prose, C hybrid minimal, Other | B | User accepted prose-first scope despite mismatch risk. | ADR-001 |
| 2 | Review cost | Scope / UX | How should review time and cost be explained? | A static labels, B computed estimate, C trade-offs only, Other | C | No numeric or label estimates; explain trade-offs only. | ADR-002 |
| 3 | Locale scope | Contract | Where should locale be enforced? | A all interactive decision surfaces, B Deep Interview only, C template-wide partial, Other | A | Must ask locale first at make startup, even though default is `en`. | ADR-003 |
| 4 | Second Brain depth | Scope | How deep should first-install Second Brain setup go? | A read-first setup, B full read/write upfront, C docs-only writes, Other | A | Must explain after install that `/hm:configure` exposes deeper settings. | ADR-004 |
| 5 | Configure shape | UX | How should `/hm:configure` be structured? | A multi-select plus per-setting explanation, B repeated loop, C advanced sections only, D end interview, Other | A | Balance clarity and slash-command simplicity. | ADR-005 |
| 6 | Failure criteria | Success criteria | What makes the result wrong? | A locale-first failure, B safety receipt failure, C Second Brain understanding failure, D all, Other | D | All three are hard success criteria. | ADR-006 |
| 7 | Test depth | Testing | What verification depth is required? | A structural tests plus snapshot regen, B structural only, C manual only, Other | A | Template contract tests and snapshot regeneration are required. | ADR-007 |

Ambiguity gate result after Round 2: total 0.90, Goals 1.0, Constraints 0.9, Success Criteria 0.8, PASS streak 2/2. No high- or medium-impact ambiguity remains.

## 📐 Architecture Decision Records

### ADR-001: Slash-command prose is the receipt source for this iteration

**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Research recommended a Decision Receipt, but a Python-generated receipt would require deeper CLI/reconcile changes. The user chose the faster prose-first path.
**Decision:** This plan improves `/harness-maker:make` and `/hm:configure` prose as the user-facing receipt. It does not add a new Python receipt generator.
**Consequences:**
- ✅ Faster delivery focused on onboarding language and template behavior.
- ⚠️ Actual reconcile facts can still diverge from slash-command summaries, so wording must avoid claiming file-level certainty beyond existing CLI output.
**Rejected alternatives:**
- Python-generated receipt — Rejected because it expands the task beyond the chosen onboarding-copy scope.
- Hybrid minimal — Rejected because the user chose direct prose-first implementation.
**Source:** Interview #1

### ADR-002: Explain review cost as trade-offs, not estimates

**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Settings such as preset, enabled reviewers, grade threshold, mechanical checks, and auto-fix affect review runtime, but precise estimates would be misleading without telemetry.
**Decision:** Onboarding explains review cost qualitatively: stricter gates and more reviewers increase confidence and possible review time; mechanical checks add deterministic command runtime; auto-fix can reduce manual work while introducing agent edits that need review.
**Consequences:**
- ✅ Avoids false precision.
- ⚠️ Users do not get numeric timing guidance.
**Rejected alternatives:**
- Static labels — Rejected because the user chose trade-off prose only.
- Computed estimates — Rejected because inaccurate numbers would weaken trust.
**Source:** Interview #2

### ADR-003: Locale-first make and all interactive decision surfaces

**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** The project default locale remains `en`, but the user explicitly requires perfect comprehension during onboarding and Deep Interview.
**Decision:** `/harness-maker:make` must ask locale as the first interactive question outside CI mode. All later make/configure prompts, Deep Interview preambles/options, validation prompts, and decision-requiring fallback/error text must follow the chosen/configured locale. PLAN files remain English.
**Consequences:**
- ✅ Prevents mixed-language onboarding.
- ⚠️ Template wording must be duplicated or explicitly parameterized for locale behavior.
**Rejected alternatives:**
- Deep Interview only — Rejected because make/configure still contain critical decisions.
- Template-wide partial for all prose — Rejected for this iteration because it would create broader snapshot churn than needed.
**Source:** Interview #3

### ADR-004: Second Brain starts read-first and points advanced setup to configure

**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Second Brain has meaningful trust boundaries: vault path, folder allowlists, Markdown-only writes, required frontmatter, note types, and `project_id` namespace checks. Asking everything during first install would make onboarding heavy.
**Decision:** First install explains read-first behavior, vault/project identity, and trust boundary. It must also tell users that `/hm:configure` is where they can continue into deeper Second Brain settings after installation.
**Consequences:**
- ✅ First install stays approachable.
- ⚠️ Writable folder setup is delayed and must be clearly discoverable through configure.
**Rejected alternatives:**
- Full read/write setup upfront — Rejected because it overloads first install.
- Documentation-only writes — Rejected because it does not build enough trust.
**Source:** Interview #4

### ADR-005: Configure uses multi-select with per-setting explanations

**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Users need targeted reconfiguration without repeating the entire make interview.
**Decision:** `/hm:configure` starts with a multi-select setting list. Each chosen setting then shows current value, changed value, trade-off, re-render effect, and preservation note before dispatch.
**Consequences:**
- ✅ Supports multiple changes in one pass while keeping explanations local to each decision.
- ⚠️ The command template becomes longer and needs structural tests to prevent future omissions.
**Rejected alternatives:**
- Repeated loop — Rejected because it complicates slash-command state tracking.
- Advanced sections only — Rejected because users would have to leave the flow for core settings.
**Source:** Interview #5

### ADR-006: Failure criteria combine locale, safety receipt, and Second Brain understanding

**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** The user identified three non-negotiable UX failures: locale mismatch, unclear file/backups/preservation, and unclear Second Brain behavior.
**Decision:** Success criteria require all three: locale-first behavior, safety receipt coverage, and Second Brain read-first plus configure follow-up clarity.
**Consequences:**
- ✅ Prevents a partial UX fix from passing.
- ⚠️ Tests need to assert prose contracts, not just rendered file presence.
**Rejected alternatives:**
- Single-axis success criteria — Rejected because each alone would miss an explicit user requirement.
**Source:** Interview #6

### ADR-007: Structural tests plus snapshot regeneration are required

**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** This change modifies generated templates and Codex-rendered skills. Snapshot drift is expected, and prior failures show regeneration order matters.
**Decision:** Add structural tests for the onboarding UX contract and regenerate snapshots from the main repo after template changes land.
**Consequences:**
- ✅ Future template regressions become visible.
- ⚠️ Snapshot regeneration must follow the known safe sequence to avoid worktree-path hash drift.
**Rejected alternatives:**
- Structural tests only — Rejected because generated snapshot hashes would remain stale.
- Manual review only — Rejected because locale and Second Brain prose regressions are easy to miss.
**Source:** Interview #7

## 🏗️ Technical Design

### Current State

- `commands/make.md` is the plugin-level slash command used for first install and reconfiguration. It currently computes defaults before asking locale and has only shallow explanations for file roots, backup, preservation, and Second Brain.
- `src/harness_maker/templates/commands/hm/configure.md.j2` is generated into installed harnesses. It supports targeted changes but lacks per-setting trade-off text and advanced Second Brain follow-up guidance.
- Stage templates already contain locale rules in several areas. The required improvement is to make the configured-locale rule explicit in the Deep Interview gate and final validation surfaces for research/spec/plan/loop.
- `src/harness_maker/cli.py` already has `--dry-run`, `_emit_reconcile_report`, `_emit_install_summary`, and Second Brain override flags. This plan does not replace those with a new receipt generator.
- `src/harness_maker/reconcile.py::backup()` backs up `.claude`, `.cursor`, `.codex`, `.agents`, and `AGENTS.md`, but user-facing slash prose does not consistently explain that scope.
- `SecondBrainConfig` enforces filesystem backend, kebab-case project id, relative folder paths, and project-id path segment for writable folders.

### Affected Components

- `commands/make.md`
- `src/harness_maker/templates/commands/hm/make.md.j2`
- `src/harness_maker/templates/commands/hm/configure.md.j2`
- `src/harness_maker/templates/stages/research.md.j2`
- `src/harness_maker/templates/stages/spec.md.j2`
- `src/harness_maker/templates/stages/plan.md.j2`
- `src/harness_maker/templates/commands/hm/loop.md.j2`
- Structural tests under `tests/unit/`
- Snapshot fixtures under `tests/snapshot/*.expected.yaml`

### Dependencies

No new dependency. Existing `pytest`, snapshot generation, and Jinja rendering helpers are sufficient.

### Architecture

This is a template-contract change. Slash commands continue to orchestrate onboarding; the Python CLI remains the state-changing engine. The plan intentionally avoids a Python-generated receipt service per ADR-001.

### Design Decisions

- ADR-001 constrains receipt implementation to prose-first slash-command changes.
- ADR-002 constrains review cost language to qualitative trade-offs.
- ADR-003 requires `/harness-maker:make` locale-first and applies configured locale to all interactive decisions.
- ADR-004 keeps Second Brain first install read-first and moves advanced guidance to `/hm:configure`.
- ADR-005 defines configure as multi-select plus per-setting explanations.
- ADR-006 defines the hard success criteria.
- ADR-007 defines the test and snapshot bar.

### Data Flow

1. User invokes `/harness-maker:make`.
2. Non-CI flow asks locale first.
3. The selected locale governs subsequent live setup prose and option labels.
4. The slash command gathers choices and dispatches to `python -m harness_maker.cli make` with existing flags.
5. CLI performs backup, reconcile, render, verify, manifest write, and summary as before.
6. The slash command summarizes the result with clarified prose that references existing CLI output and safe recovery points.
7. User can later invoke `/hm:configure` for advanced Second Brain, reviewer, target, mechanical check, and wrapup settings.

### API Changes

No Python API or file-format change is planned. `harness.yaml` schema remains unchanged.

## 📝 Implementation Plan

### Phase 1 — Locale-first `/harness-maker:make` and onboarding receipt prose

**Scope:**
In: `commands/make.md`, possibly `src/harness_maker/templates/commands/hm/make.md.j2` if generated `/hm:make` quick-start wording needs alignment.
Out: Python CLI receipt generator, `harness.yaml` schema, `interview.py`.

Implement:
- Move locale selection to the first interactive decision for non-CI `/harness-maker:make`.
- State that default locale is `en`, but the first user choice controls the live onboarding language.
- For fresh install, update smart-default and preview sections to explain:
  - output roots by target: `.claude`, `.cursor`, `.codex`, `.agents/skills`, `AGENTS.md`
  - backup root pattern `.backup-<timestamp>`
  - preservation mechanisms: `@hm:user:*`, `KEEP`, `MERGE_BLOCK`, generated/system-managed files
  - target removal behavior: previously rendered target files are left in place
  - review setting trade-offs without timing estimates
- Update post-dispatch summary instructions to mention backup path and configure follow-up.

**Exit criterion:**
`rg -n "locale.*first|backup|MERGE_BLOCK|KEEP|\\.cursor|\\.codex|\\.agents|AGENTS.md|Second Brain|/hm:configure|review.*trade|trade-off" commands/make.md src/harness_maker/templates/commands/hm/make.md.j2`

**Risk:** medium

**Rollback point:** Revert Phase 1 edits only; later phases are independent.

### Phase 2 — `/hm:configure` multi-select explanations and Second Brain advanced path

**Scope:**
In: `src/harness_maker/templates/commands/hm/configure.md.j2`.
Out: new configure Python command, Second Brain write-folder schema changes.

Implement:
- Keep multi-select as the entry shape.
- Add per-setting explanation requirements: current value, new value, benefit, trade-off, re-render effect, preservation note.
- Add explicit review trade-off prose for reviewers, grade threshold, mechanical checks, auto-fix/focus where present.
- Add Second Brain read-first explanation and advanced follow-up:
  - vault path and project id identify the Obsidian project memory
  - read behavior searches configured allowlisted folders
  - write-capable folders require project_id namespace and Markdown/frontmatter constraints
  - first install keeps this light; configure can continue deeper setup
- Ensure dispatch text still says unspecified fields are preserved.

**Exit criterion:**
`rg -n "current value|trade-off|re-render|preserve|Second Brain|vault|project_id|write|allowlist|Markdown|frontmatter|reviewers|grade threshold|mechanical" src/harness_maker/templates/commands/hm/configure.md.j2`

**Risk:** low

**Rollback point:** Revert to Phase 1 state by restoring only the configure template.

### Phase 3 — Deep Interview locale contract across stage templates

**Scope:**
In: `src/harness_maker/templates/stages/research.md.j2`, `src/harness_maker/templates/stages/spec.md.j2`, `src/harness_maker/templates/stages/plan.md.j2`, `src/harness_maker/templates/commands/hm/loop.md.j2`.
Out: review/execute/wrapup behavior, non-interactive generated documents.

Implement:
- Add or tighten explicit configured-locale contract for live Deep Interview text:
  - round preamble
  - decisions-so-far block
  - ambiguity explanation
  - question text and option labels
  - validation prompts where user action is required
- Preserve the existing rule that persisted `SPEC`, `PLAN`, and `RESEARCH` docs are written in English.
- For research `--deep`, ensure Phase 0 and Phase 0.5 both state locale behavior.
- For loop, ensure adaptive interview and 3-layer gate follow configured locale.

**Exit criterion:**
`rg -n "config.locale|configured locale|Live.*locale|option labels|validation" src/harness_maker/templates/stages/research.md.j2 src/harness_maker/templates/stages/spec.md.j2 src/harness_maker/templates/stages/plan.md.j2 src/harness_maker/templates/commands/hm/loop.md.j2`

**Risk:** medium

**Rollback point:** Revert Phase 3 stage-template edits; Phases 1-2 still stand.

### Phase 4 — Structural tests and snapshot regeneration

**Scope:**
In: `tests/unit/` structural tests, `tests/snapshot/*.expected.yaml`.
Out: e2e runtime tests against live Claude Code/Codex UIs.

Implement:
- Add structural tests that render/read templates and assert:
  - `/harness-maker:make` requires locale-first onboarding outside CI
  - make prose mentions backup, preservation, target roots, target non-deletion, review trade-offs, and configure follow-up
  - `/hm:configure` mentions multi-select, per-setting trade-offs, re-render impact, preservation, and Second Brain advanced path
  - Deep Interview templates contain configured-locale contracts
  - Second Brain prose covers read-first behavior, allowlist, project_id namespace, Markdown/frontmatter, and configure follow-up
- Regenerate snapshots from the main repo after template changes are present.
- Run targeted tests, then full unit/snapshot validation.

**Exit criterion:**
`uv run pytest tests/unit/test_synthesize.py tests/unit/test_codex_phase7.py tests/unit/test_synthesize_snapshot.py -q`

**Risk:** medium

**Rollback point:** Revert Phase 4 tests/snapshots if structural contract design needs rework; keep template changes for manual inspection.

## 🧪 Testing Strategy

Unit / structural:
- Template contract tests for `commands/make.md` and `configure.md.j2`.
- Stage-template contract tests for research/spec/plan/loop locale wording.
- Existing synthesize tests confirm generated `commands/hm/make.md` and `commands/hm/configure.md` remain in file lists.

Snapshot:
- Run `uv run python tests/snapshot/regenerate.py` from the main repo after template edits are in the main working tree.
- Run `uv run pytest tests/unit/test_synthesize_snapshot.py -q`.

Manual:
- Read rendered make/configure command text for `ko` locale dogfood flow.
- Confirm no prompt asks preset/dev_mode/targets before locale in `/harness-maker:make`.
- Confirm post-install guidance points to `/hm:configure` for deeper Second Brain setup.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Prose receipt diverges from real reconcile behavior | Medium | Phrase as explanation of mechanisms and existing CLI output, not as a computed file-action guarantee. |
| Locale-first prose becomes English-only in some branches | High | Structural tests must cover fresh install, re-render/configure, and Deep Interview templates. |
| Onboarding becomes too verbose | Medium | Use field-level tips and preview/summary sections; avoid turning every question into a manual. |
| Snapshot regeneration from wrong directory causes hash drift | Medium | Follow memory rule: template changes present in main repo first, then regenerate from repo root. |
| Second Brain advanced write setup remains undiscoverable | High | Configure template must explicitly describe advanced path after first install and under Second Brain option. |
| Existing ignored `work-docs/` means PLAN is not tracked by git | Low | This is current project convention; final response must provide path. |

## ✅ Success Criteria

- [x] `/harness-maker:make` non-CI interactive flow asks locale before preset, dev_mode, targets, profile defaults, or setup confirmation.
- [x] Make onboarding explains installed roots, backup root pattern, preservation mechanics, target-specific leftover behavior, and review-setting trade-offs.
- [x] `/hm:configure` uses multi-select plus per-setting explanation requirements.
- [x] First-install Second Brain setup is read-first and points users to `/hm:configure` for deeper settings.
- [x] Deep Interview live prompts across research/spec/plan/loop explicitly follow configured locale.
- [x] No numeric review-time estimate is introduced.
- [x] Structural tests enforce the UX contract.
- [x] Snapshot fixtures are regenerated from the main repo and snapshot tests pass.

## 🔍 Plan Validation

Validator outcome: APPROVED.

The dedicated `plan-validator` subagent was not invoked because current Codex session rules only allow subagents when the user explicitly requests delegation. I performed a local validator pass against the draft instead.

| Check | Result | Notes |
|---|---|---|
| Scope clarity | APPROVED | Template-focused, no schema/API change. |
| ADR coverage | APPROVED | Seven user decisions map to seven ADRs. |
| Phase decomposition | APPROVED | Four phases with independent rollback points. |
| Verification | APPROVED | Structural tests and snapshot regeneration are required. |
| Main residual risk | ACCEPTED | ADR-001 leaves prose/actual-state divergence risk; mitigated by conservative wording. |

## Execution Status

- Phase 1: DONE — `/harness-maker:make` now asks live locale first outside CI, carries that locale through onboarding, and expands the safety receipt.
- Phase 2: DONE — `/hm:configure` now uses a multi-select decision receipt with per-setting benefit/trade-off/re-render/preservation notes and advanced Second Brain guidance.
- Phase 3: DONE — research/spec/plan/loop Deep Interview surfaces now require configured-locale live prompts and option labels.
- Phase 4: DONE — structural tests were added and snapshot expectations were regenerated from the main checkout.

Verification:
- `uv run ruff check tests/unit/test_onboarding_ux_contract.py`
- `uv run pytest tests/unit/test_onboarding_ux_contract.py tests/unit/test_synthesize.py tests/unit/test_codex_phase7.py tests/unit/test_synthesize_snapshot.py -q`
