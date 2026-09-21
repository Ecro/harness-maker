---
type: plan
task_slug: intent-vocabulary-and-owners
status: complete
created: 2026-09-21
tags: [harness-maker, plan, python, intent]
spec: "[[SPEC-intent-owners-role-map]]"
interview_rounds: 0
adrs: 7
validator_outcome: NOT_RUN
summary: "Role-aware advisory approvals followed by compatible intent vocabulary migration"
spec_need_verdict: add
spec_need_target: intent-owners-role-map
---
# Intent vocabulary and owners

## 🎯 Executive Summary
Implement HANDOFF-intent-vocabulary-and-owners.md in order: owners, then vocabulary.
The DRI explicitly authorized using unreleased execute Step 0 instead of the stale installed
PLAN prerequisite. This PLAN is authored by execute, not a separate stage. SPECs record the
handoff contracts; approval is not fabricated and landing is outside this execute request.

## 📚 Prior Work
Handoff at base 75239ea7; io_utils.migrate_dev_mode establishes translate-before-strip.
Memory: assertion-invariant-over-named-dimension requires contrasting cases;
fix-introduced-defect-passes-all-gates requires absent/legacy windows;
targeted-phase-d-subset-missed-the-snapshot-test requires full-suite verification;
snapshot-regen-inside-worktree requires worktree regeneration;
dri-spec-approval-content-hash-land-hold leaves new SPECs unstamped until acceptance.

## 📐 Architecture Decision Records
### ADR-001 — Normalize owners
Accept maps of optional owner/dri/team strings and legacy string lists. Join a legacy list
with comma-space into team; empty list/absent becomes {}. Trim only for role comparison;
case is significant, blank roles ignored. At least two distinct nonempty identities triggers
an advisory at approval; no identity comparison can authenticate the git approver.
### ADR-002 — Preserve meaning
An intent remains a 1:N task grouping. Purpose retains statement and vision, metrics retain
measure shape. Record hypothesis becomes statement, outcome_id becomes metric_id.
### ADR-003 — Compatibility before cutover
Load legacy data without writing on reads. Explicit migration preflights all destinations,
rejects conflicting old/new values, writes atomically, and only then removes legacy sources.
Approval payload key strings remain frozen. Schema major remains 1 while both formats load.
### ADR-004 — One question store
Open questions preserve claims, evidence/history and revisit conditions. Legacy unknowns
become open questions; known -> confirmed, assumed/unknown -> open, conflict -> wrong.
### ADR-005 — Serial ownership
Both phases touch intent.py/world.py and shared templates. No parallel implementation;
read-only analysis and the required test-reviewer gate may run independently.

### ADR-007 — Canonical persistence
Canonical open_questions records live in .claude/intent.yaml (one authoritative store).
Measurements live in .claude/intent/metrics.yaml; records in intent/<ID>.md. Legacy Python
world APIs may retain adapters for one release, but canonical CLI emits canonical names.

### ADR-006 — Legacy spellings are compatibility evidence
The handoff's literal zero-token inventory conflicts with retaining a deprecated CLI and
reading historical data. Canonical surfaces adopt new names; conversion code, legacy API
adapters, frozen fixtures, hash/event payloads and historical SPEC IDs are documented exceptions.
Do not rename unrelated uses of hypothesis (the test library), outcomes or objectives.

## 🏗️ Technical Design
Schemas in intent.py, state and verbs in world.py, CLI registry and templates consume them.
Two SPECs separate behavior from rename: SPEC-intent-owners-role-map and
SPEC-intent-vocabulary-rename. Preserve body bytes and frozen hashes during migration.

## 📝 Implementation Plan
### Phase 1 — Owners (done)
- depends_on: []
- parallel_group: none
- merge_hazards: shared schema, CLI, templates
- Scope: intent.py, world.py, owners tests, skeleton expectations, intent-layer template,
  generated snapshots/baselines when needed, SPEC and this PLAN.
- Out: vocabulary migration until Phase 2.
- Evidence: A.4/B 19 failed, 2 justified negative passes; A.5 round 1 FAIL (legacy invalid
  input coverage), round 2 PASS after restoration. Focused 82 passed; selected regression
  2530 passed, 27 skipped, 2 xfailed. mypy passed both source files. D.5 skipped: new feature.
  Full suite and generated fixtures verified at final stage exit after Phase 2.
- Exit: `uv run pytest tests/unit/test_intent_owners.py tests/unit/test_intent_skeleton.py tests/unit/test_world_objectives.py` plus ruff/mypy.
- risk: medium; rollback: restore only this phase's diff, preserve pre-existing work.
### Phase 2 — Vocabulary and migration (done)
- depends_on: [1]
- parallel_group: none
- merge_hazards: shared public schemas and generated surfaces
- Scope: intent/world loaders and migration, CLI registry, direct consumers, intent-related
  templates/docs/tests, old SPEC supersession notes, generated baselines/snapshots, dogfood.
- Out: unrelated workflow behavior, identity enforcement, external services/dependencies.
- Phase SPEC: `specs/SPEC-intent-vocabulary-rename.md` + machine companion (read in full;
  the frontmatter primary SPEC covers Phase 1 only). Both SPECs govern stage exit and review.
- Test evidence: A.4/B 15 failed, zero passed; A.5 round 1 FAIL (lossy/no-op implementations
  were insufficiently distinguished), round 2 PASS after complete value/history/CLI assertions.
- Fixture corrections after implementation exposed them: S3 originally concatenated JSON
  events without newlines; fixed JSONL framing, keeping ten-wrapup oracle unchanged. Shallow
  reason pinned to existing `no_git`, not invented `shallow`; filled_at/quiet/due oracle unchanged.
- Newly reachable compatibility windows reviewed: canonical question nested validation,
  optional/legacy input absence, mixed-key conflicts, old approval stamps, historical git blobs,
  explicit migration before mutation, canonical PLAN links and legacy alias writes.
- Exit: migration/hash/history/CLI tests, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy src tests`, `uv run pytest -n 7 --dist loadfile -m 'not advisory'`.
- risk: high; rollback: preserve old source files until validated destination writes; restore
  this phase's changes before any commit if gates cannot pass.

## 🚧 Contract Boundaries
### Do not change
- `.claude/harness.yaml` — pre-existing user change; no workflow configuration edits.
- Advisory: No blocking identity gate, no hash-payload spelling changes, no external dependency.
- Advisory: Preserve terminal states, 1:N cardinality, body bytes and historical withdrawal clock.
- Advisory: Record directory is intent/<ID>.md; state changes never move a record.

## 🧪 Testing Strategy
TDD per phase with measured false-RED and a three-lens test-reviewer. Frozen historical
fixtures are independent migration/hash oracles. Full non-advisory suite once at final exit.

## ⚠️ Risks & Mitigation
| Risk | Mitigation |
|---|---|
| Historical approvals/clock reset | Freeze payload spellings and test old git blobs |
| Data loss on mixed files | Refuse conflicts before writes; migration idempotence tests |
| Render drift | Structural gates and worktree snapshot regeneration |

## ✅ Success Criteria
- [x] Optional/legacy owners and nonblocking role advisory verified.
- [x] Migration, stable approvals/clock, canonical CLI and legacy alias verified.
- [x] Full suite, lint, types and drift check green; no commit.

## Final verification evidence
- Required A.5 gates passed for both phases before production implementation. Further
  compatibility tests cover nested question validation, stable duplicate question IDs,
  legacy reads without writes, refusal before explicit migration, legacy alias writes,
  canonical/absent/missing/conflicting PLAN links, and retry after injected write failure.
- Canonical compatibility suite: 28 passed. Render guidance: 29 passed. Final generated
  surface/snapshot checks: 42 passed. Final owners/render run: 50 passed.
  Full non-advisory suite: 9096 passed, 100 skipped, 3 xfailed, 4 warnings in 630.29s.
  The later injected-write-failure case passed separately and within the 28-case suite.
  Ruff check and format check passed; strict mypy passed all 775 source/test files.
  Live external integration tests remain opt-in and were not enabled.
- SPEC machine checks and cross-validation passed for both SPEC pairs. Both remain draft;
  no DRI approval stamp was fabricated. T2: mutation gate is not required.
- Worktree dogfood migration preserved two records' approval stamps, derived validity,
  terminal/proposed states, body bytes, all 16 measurement rows, eight question claims,
  purpose statement/vision and the withdrawal result (nine quiet wrapups, not due).
  Repeated migration reported no changed/retired paths and preserved exact bytes.
- Template instruction allowlist attributes replaced CLI lines/headings to this task.
  Answer-gate markers remain stable. Autopilot golden re-capture changes only execute,
  help, review, spec and wrapup in all four arms; command sets and autonomy gates unchanged.
  Existing aggregate ratchet was NOT reset: Claude 401697 -> 401649; Codex 340105 -> 340077.
- Migration uses atomic replacement per destination, not a filesystem-wide transaction.
  Legacy sources are retired only after all writes succeed; injected failure/retry is tested.
- Canonical question records allow wrong; revisit status conditions retain the existing
  known/unknown contract (canonical confirmed/open). No new wrong-condition semantics.
- Gate 0: standalone invocation, no current-iteration marker; no receipt required.
- Base HEAD remains 75239ea788b889a6c128d2ecee47a478e965afc1. Base dirty files are unchanged.
  Persistent task worktree is retained for review; no commit or worktree finalize.

### Phase D selection
The selector chose full. Its exact reason:

```
full suite: no test maps to .claude/intent.yaml, .claude/intent/metrics.yaml, .claude/world/assumptions.yaml, .claude/world/outcomes.yaml, .gitignore, intent/LOOP-OPT-IN.md, intent/SOURCE-PLAN-STEPS.md, specs/SPEC-ai-native-sdlc-vs-intent-world.machine.yaml, specs/SPEC-ai-native-sdlc-vs-intent-world.md, specs/SPEC-assumption-entry-and-evidence-locator.machine.yaml, specs/SPEC-assumption-entry-and-evidence-locator.md, specs/SPEC-intent-layer-ops.machine.yaml, specs/SPEC-intent-layer-ops.md, specs/SPEC-intent-miss.machine.yaml, specs/SPEC-intent-miss.md, specs/SPEC-intent-owners-role-map.machine.yaml, specs/SPEC-intent-owners-role-map.md, specs/SPEC-intent-vocabulary-rename.machine.yaml, specs/SPEC-intent-vocabulary-rename.md, specs/SPEC-intent-world-model-objective-layer.machine.yaml, specs/SPEC-intent-world-model-objective-layer.md, specs/SPEC-objective-gap-proposal.machine.yaml, specs/SPEC-objective-gap-proposal.md, specs/SPEC-observed-harness-gaps-salvage.machine.yaml, specs/SPEC-observed-harness-gaps-salvage.md, specs/SPEC-outcome-measure.machine.yaml, specs/SPEC-outcome-measure.md, specs/SPEC-playbook-alignment.machine.yaml, specs/SPEC-playbook-alignment.md, specs/SPEC-withdrawal-criterion-window.machine.yaml, specs/SPEC-withdrawal-criterion-window.md, src/harness_maker/intent_migrate.py, tests/structural/autopilot_gate_golden.json
```

### Stage-exit boundary inventory
66 changed paths (including both sides of moved records and the REVIEW artifact); compared against
`.claude/harness.yaml`: zero crossings. Deleted legacy stores and record paths are the
authorized migration. Exact changed-path set:

- `.claude/intent.yaml`
- `.claude/intent/metrics.yaml`
- `.claude/world/assumptions.yaml`
- `.claude/world/outcomes.yaml`
- `.gitignore`
- `README.md`
- `docs/HOW-IT-WORKS.md`
- `intent/LOOP-OPT-IN.md`
- `intent/SOURCE-PLAN-STEPS.md`
- `specs/SPEC-ai-native-sdlc-vs-intent-world.machine.yaml`
- `specs/SPEC-ai-native-sdlc-vs-intent-world.md`
- `specs/SPEC-assumption-entry-and-evidence-locator.machine.yaml`
- `specs/SPEC-assumption-entry-and-evidence-locator.md`
- `specs/SPEC-intent-layer-ops.machine.yaml`
- `specs/SPEC-intent-layer-ops.md`
- `specs/SPEC-intent-miss.machine.yaml`
- `specs/SPEC-intent-miss.md`
- `specs/SPEC-intent-owners-role-map.machine.yaml`
- `specs/SPEC-intent-owners-role-map.md`
- `specs/SPEC-intent-vocabulary-rename.machine.yaml`
- `specs/SPEC-intent-vocabulary-rename.md`
- `specs/SPEC-intent-world-model-objective-layer.machine.yaml`
- `specs/SPEC-intent-world-model-objective-layer.md`
- `specs/SPEC-objective-gap-proposal.machine.yaml`
- `specs/SPEC-objective-gap-proposal.md`
- `specs/SPEC-observed-harness-gaps-salvage.machine.yaml`
- `specs/SPEC-observed-harness-gaps-salvage.md`
- `specs/SPEC-outcome-measure.machine.yaml`
- `specs/SPEC-outcome-measure.md`
- `specs/SPEC-playbook-alignment.machine.yaml`
- `specs/SPEC-playbook-alignment.md`
- `specs/SPEC-withdrawal-criterion-window.machine.yaml`
- `specs/SPEC-withdrawal-criterion-window.md`
- `src/harness_maker/autopilot_caps.py`
- `src/harness_maker/command_registry.py`
- `src/harness_maker/hm.py`
- `src/harness_maker/intent.py`
- `src/harness_maker/intent_cli.py`
- `src/harness_maker/intent_migrate.py`
- `src/harness_maker/intent_vocabulary.py`
- `src/harness_maker/templates/commands/hm/help.en.md.j2`
- `src/harness_maker/templates/commands/hm/help.ko.md.j2`
- `src/harness_maker/templates/rubrics/objective_scope_drift.yaml.j2`
- `src/harness_maker/templates/skills/intent-layer/SKILL.md.j2`
- `src/harness_maker/templates/stages/execute.md.j2`
- `src/harness_maker/templates/stages/review.md.j2`
- `src/harness_maker/templates/stages/spec.md.j2`
- `src/harness_maker/templates/stages/wrapup.md.j2`
- `src/harness_maker/worktree.py`
- `src/harness_maker/world.py`
- `tests/snapshot/prod-firmware.expected.yaml`
- `tests/snapshot/prod-tauri-app.expected.yaml`
- `tests/snapshot/side-python-cli.expected.yaml`
- `tests/snapshot/side-tauri-app.expected.yaml`
- `tests/structural/autopilot_gate_golden.json`
- `tests/structural/test_autopilot_gate_render.py`
- `tests/structural/test_instruction_preservation.py`
- `tests/unit/test_intent_owners.py`
- `tests/unit/test_intent_skeleton.py`
- `tests/unit/test_intent_vocabulary.py`
- `tests/unit/test_render_intent_layer.py`
- `tests/unit/test_render_intent_layer_assume_add.py`
- `work-docs/INTENT-LOOP-OPT-IN.md`
- `work-docs/INTENT-SOURCE-PLAN-STEPS.md`
- `work-docs/PLAN-intent-vocabulary-and-owners.md`


### Review stage evidence (2026-09-21)
Review run cd8632bc72ba completed: A / APPROVED, all seven lenses on final frozen artifact.
Three P1 repairs in world.py, intent_cli.py and intent_migrate.py; two P2 findings retained.
Final dependency-selected 1,272 tests, Ruff and strict mypy passed. Full suite evidence above
belongs to execute and predates review fixes. REVIEW records the validation limits.
Additional in-scope stage artifact:
- `work-docs/REVIEW-intent-vocabulary-and-owners-2026-09-21.md`
No boundary crossing, commit or landing; task worktree remains ready for the next stage.

### Wrapup verification (2026-09-21)
The exact CI-derived final suite passed on the reviewed source: Ruff lint and format
(779 files), strict mypy (775 files), and pytest with xdist loadfile scheduling:
9,098 passed, 100 skipped, 3 xfailed, 4 warnings in 434.82 seconds. Both governing
SPECs have their 12 mechanical ACs forward-bound to collected passing tests; no
pytest-bindable AC remains pending and there are no judgment ACs. Both unbound
and unjudged gates passed. The REVIEW drift verdict matches this task and is clean.
Managed-document additions cover CHANGELOG.md, TECH_SPEC.md, docs/ARCHITECTURE.md
and interrupted-migration recovery in docs/HOW-IT-WORKS.md. README.md already
describes the canonical feature. These are wrapup documentation changes; source
and tests remain as reviewed. Landing, approval stamps and push belong to the
main stage owner and are not claimed by this verification record.

Wrapup owner checks: PLAN/SPEC scenarios map to the reviewed implementation and tests;
structural gate PASS (no baseline: task checkout has no dashboard; base dashboard has
no populated Structural score); no unresolved high/P0 security findings; merge-safe
index and source/test equality to the confirmed review artifact passed. The intent-layer
context lint passed. The operator explicitly requested wrapup and push to main after
the approved review; both governing SPEC approval stamps were recorded against their
final bound content and approval-status returned land:ok. No new assumptions or metric
measurements were requested. The full-suite marker was written before SPEC binding;
binding/approval metadata changes subsequently invalidate that fingerprint, so no new
full-suite cache claim is made for those metadata bytes. Both binding gates passed.

Memory: wiki intent-vocabulary-and-owners; failures migration-writer-partial-publication
and assertion-invariant-over-named-dimension (count19). Dedup searched3, considered2,
reused1. Escalation scanned28 threshold entries, updated1 existing proposal, retained27.
Promotion evaluated9 candidates and promoted2 failure notes; seven ADRs remain local
(project-specific contracts, with generic migration guidance covered by the failure note).
Memory/promotion receipt reconciliation passed with five checked claims and no mismatch.
