# Changelog

## [Unreleased]

- **README one-prompt rewrites slash-command typing to Bash auto-install** for all three IDEs. The AI now runs `claude plugin marketplace add` + `claude plugin install` (and `git clone` for Cursor, `codex plugin marketplace add` for Codex) via the Bash tool instead of telling the user to type `/plugin install ...` themselves. User-typed slash commands on Claude Code drop from 3 to 1 (`/reload-plugins`). Per-IDE step budget table now shipped at the top of the Quickstart. PLAN-readme-one-prompt-autoinstall; Phase 0 empirical verification deferred — README uses the conservative `manual-enter-required` wording (harmless when reload auto-triggers).

## 0.17.0 — Fresh-install /hm:health zero false-positive P0 (2026-05-19)

PLAN-fresh-install-health-baseline. A freshly-rendered `/hm:make` harness
now passes its own `/hm:health` with zero P0 outside a small, named
allowlist of "intended fresh-install noise" (telemetry × 2, CI workflow,
governance docs requiring user authoring). Bundles 4 fix categories:
template gaps, Side context-lint threshold raise, unknown-stack
auto-degrade, telemetry intended-noise allowlist.

### Highlights

- **Templates ship security + memory baselines**:
  - `harness.yaml` now renders a `memory:` block by default
    (`{enabled: true, dir: .claude/memory, files: [failures.md, wiki.md]}`).
  - `settings.json` `permissions.deny` ships 4 baseline patterns on
    both Side and Production: `["Bash(rm:*)", "Bash(curl * | sh)",
    "Write(/etc/**)", "Write(~/.ssh/**)"]`.
- **Side context-lint thresholds raised** to match shipped content:
  agent ≤ 150 (was 100), skill ≤ 100 (was 50). Production unchanged
  at 200/150. Side identity now differentiates on reviewer count +
  grade threshold + spec_gate, not on prompt size (ADR-001).
- **Unknown-stack auto-degrade**: projects without recognized manifest
  (board YAML, shell-only, etc.) no longer cascade into two P0 signals
  from `_detect_stacks() == set()`. Both `stack_detected` and
  `tests_present` weights drop to 5/10 advisory on unknown stack
  (ADR-004).
- **Telemetry intended-noise allowlist**: `metrics_jsonl_present` hint
  copy clarified ("First Claude Code tool use will create this file
  (PostToolUse hook is installed).") + `INTENDED_P0_SIGNALS` constant
  exposed for the new fresh-install integration test gate (ADR-006).
- **`_merge_permissions` idempotency fix** (`render.py`) — no phantom
  `ask: []` key emitted when neither input had it. Repeated `/hm:make`
  now produces byte-identical output.

### BREAKING — Production `permissions.deny` scope narrowed

Production previously shipped `["Bash(rm:*)", "Bash(curl:*)"]` (broader
`curl:*` blocks ALL curl). New baseline collapses to the 4-pattern
canonical (`Bash(curl * | sh)` only), aligning Side·Production identical
per ADR-003 option A. **Production users relying on blanket curl block
silently lose that protection on re-render**. If your project needs
all-curl blocked, append `Bash(curl:*)` to `permissions.deny` after the
next `/hm:make`; the user addition is preserved via `_merge_permissions`
list-union semantics.

### Migration

No flag. Existing 0.16.x users running `/hm:make` once pick up the
additive baselines automatically via the existing render path
(`_merge_permissions` list-union for `settings.json`,
`_preserve_yaml_user_keys` + template-emit for `harness.yaml.memory:`).

### Quality gate

New integration test `tests/integration/test_fresh_install_readiness.py`
runs in `release.yml` quality-gate with `INTEGRATION=1`. 5 cases: fresh
Side + Production within composite-score floors (66 / 72 measured);
existing-install harness.yaml + settings.json migration via existing
render semantics; byte-identical idempotency on re-render.

### Loop UX

`commands/hm/loop.md.j2` gains a "Non-stopping discipline" section —
codifies that `/hm:loop` iters never halt for verification or status
confirmation. Background-task notifications trigger automatic next-step
transitions, not user reports.

## 0.16.0 — BREAKING: 5-term inequality deep-interview gate replaces 3-layer (2026-05-18)

PLAN-deep-interview-question-criteria. Replaces the 3-layer interview gate
(5-rubric + GCIC + CLARITI + 5 implicit probes + weighted Ambiguity Score
+ 2-round streak) with a single 5-term inequality applied uniformly across
`/hm:research`, `/hm:spec`, `/hm:plan`, and `/hm:loop`:

```
ask(Q) iff EIG(Q) >= ε  ∧  TaskRel·UserAns >= 0.7
        ∧ slot ∉ common_ground  ∧  confidence < τ
        ∧ open_ended_count < cap_locale
```

### BREAKING

- **harness.yaml schema (deep_gate)** — `interview.deep_gate.max_rounds` and
  `interview.deep_gate.streak_target` are deprecated. On read they emit a
  warning and are ignored. Existing 0.15.x users upgrade without manual
  intervention; new defaults ship via `interview_deep_gate_defaults()`.
  New keys (ADR-007 uniform across Side/Production):
  - `eig_epsilon: 0.5`
  - `confidence_tau: 0.7`
  - `open_ended_cap_by_locale: {en: 2, ko: 1, ja: 1, default: 1}`
  - `common_ground.llm_inference_threshold: 0.95`
  - `common_ground.llm_inference_enabled: true` (ADR-012 kill-switch — only
    user-tunable key)
- **work-docs/loop-context/*.yaml** — old `ambiguity_score` weighted-sum
  format is no longer read. Active loops on upgrade abort with a schema
  error; restart via `/hm:loop --spec <slug>` to rebuild context.
- **Stage templates** (`templates/stages/{research,spec,plan}.md.j2` and
  `templates/commands/hm/loop.md.j2`) — Layer 1-3 GCIC/probing/score blocks
  replaced with 5-term checklist rendering (ADR-005).

### Added

- `harness_maker.common_ground` — explicit-evidence + LLM-inference (ADR-003)
  common-ground detector. Atomic JSONL audit at
  `.claude/observability/cg-marks-{slug}.jsonl`. 10-slot false-positive guard.
- `harness_maker.eig` — `score_eig(q, ctx) -> float` mechanism-agnostic
  public interface (ADR-002 rollback path enforced).
- `harness_maker.inequality_gate` — composes the 5-term inequality + ranks
  + enforces locale open-ended cap.
- `harness_maker.observability.intent_miss` — ADR-008 silent-intent-miss
  telemetry. `/hm:health` Layer 1 surfaces the rate.
- `harness_maker.observability.coverage_classifier` — ADR-010 post-hoc
  coverage-kind classifier (telemetry-only labels; ADR-004 deletes gating).

### Changed

- `templates/harness-yaml/{Production,Side}.yaml.j2` render new 5-term schema.
- `templates/stages/review.md.j2` — new Step 2.5 silent-intent-miss hook.
- `templates/commands/hm/health.md.j2` — new Layer 1 sub-check
  `silent_intent_miss_rate` (initial threshold 0.10, narrative-only pending
  telemetry calibration).

### Migration

For users on 0.15.x:
1. `/plugin update` then re-render via `/harness-maker:make`.
2. Old `deep_gate.max_rounds`/`streak_target` in user-edited harness.yaml
   are warn-and-ignored — no manual cleanup required (removing them silences
   the warning).
3. Active loops (`.claude/.hm-loop-active` present + a
   `work-docs/loop-context/<slug>.yaml` exists) must restart — run
   `/hm:loop --spec <slug>` to rebuild loop context. There is no automatic
   migration of the old `ambiguity_score` weighted-sum format.
4. Optional kill-switch: set
   `interview.deep_gate.common_ground.llm_inference_enabled: false` in
   `.claude/harness.yaml` to disable the aggressive LLM-inferred
   common-ground path (ADR-012). Default is `true`; flipping to `false`
   reverts the gate to explicit-evidence-only matching.

## 0.15.3 — fix ruff quality-gate regressions from 0.15.1 + 0.15.2 (2026-05-18)

CI-only patch. No runtime change.

### Fixed

- Removed two unused `import yaml` lines added to `tests/unit/test_render.py`
  in 0.15.2 (`F401`).
- Re-formatted a long-assertion message in `tests/unit/test_install_ref.py`
  added in 0.15.1 to match ruff format's preferred line break.

The release.yml `quality-gate` job now passes (was failing on both
v0.15.1 and v0.15.2 tag pushes at `ruff check .` / `ruff format --check .`).
End users were unaffected (harness-maker isn't on PyPI; distribution goes
through the Claude Code plugin marketplace, which reads the GitHub
release artifact directly).

## 0.15.2 — preserve user edits to settings.json + harness.yaml across re-render (2026-05-18)

Two patches to the renderer's reconcile path. Both address user-edit
durability across `/hm:make` invocations.

### Fixed

- **`settings.json` `permissions.{allow,deny,ask}` now deep-merge as a
  union** (template entries first, then user-added entries appended,
  dedup). Previously the template's `permissions` value won wholesale,
  silently wiping user-added denies (e.g. `Write(/etc/**)`,
  `Write(~/.ssh/**)` added via `/hm:health` Layer 1 acceptance) on every
  re-render. Documented as a "v1 limitation" in 0.3.1; promoted to a
  proper fix in 0.15.2. Other `permissions.*` keys (scalars, unknown
  sub-keys) still follow template-wins.

- **`harness.yaml` preserves user-added top-level keys** that the
  template doesn't emit (e.g. `memory:`, `custom:`, project-specific
  blocks). New keys are appended after a `@hm:user:extensions` marker
  comment. Template-emitted keys still win on overlap — if a future
  template natively adds a key the user previously added, the template's
  value replaces the user's on the next render (consistent with the
  block-merge model elsewhere in the codebase).

### Tests

- `tests/unit/test_render.py`:
  - Updated `test_render_settings_json_shallow_merges_existing` to
    reflect the new union contract.
  - Added `test_render_settings_json_unions_permissions_deny` (regression
    guard for the `/hm:health` audit finding).
  - Added `test_render_settings_json_unions_dedup_no_duplicates`.
  - Added `test_render_harness_yaml_preserves_user_added_top_level_key`,
    `test_render_harness_yaml_user_key_marker_present`, and
    `test_render_harness_yaml_template_key_wins_over_user`.

## 0.15.1 — fix uv archive cache path bug in renderer (2026-05-18)

### Fixed

- **`_compute_install_ref` returned a broken path when invoked from a uv
  archive cache** — when `uv run --with /plugin/cache/<version>` archived
  the package into `~/.cache/uv/archive-v0/<hash>/lib/python3.12/
  site-packages/harness_maker/`, the renderer's
  `Path(__file__).parent.parent.parent` math resolved to
  `<archive>/lib/python3.12` — not a Python project. That value got baked
  into every rendered hook, skill, and slash command as
  `uv run --with <archive>/lib/python3.12 python -m harness_maker.<module>`,
  and every invocation failed with `does not appear to be a Python project`.
  Fixed by reading the `file://` URL path from `direct_url.json` directly
  (the original source path uv was given), bypassing the `__file__`-derived
  guess. Surfaced by `/hm:health` audit 2026-05-18. Regression test:
  `tests/unit/test_install_ref.py::test_url_path_wins_over_uv_archive_pkg_root`.

## 0.15.0 — per-agent model routing + preset-aware defaults (2026-05-18)

Token-cost optimization across Claude Code / Cursor / Codex via declarative
per-agent model pinning. 13 ADRs locked in PLAN-model-routing-multi-ide.md.
8 implementation phases shipped via /hm:loop with per-phase /hm:review.

### Added

- **Per-agent model schema** (ADR-001/002) — new `HarnessConfig.agent_models:
  dict[str, AgentModelSpec]` with nested `{claude, cursor, codex: {model,
  reasoning_effort}}`. `recommended_model: str` renamed to `default_model: str`
  (deprecated read-side property kept for 0.15.x / 0.16.x; removed no earlier
  than 0.17.0 per ADR-012).
- **Preset-aware defaults** (ADR-005) — new `src/harness_maker/presets.py`
  ships `PRESET_AGENT_MODELS` for Production (opus on 3 reasoning agents,
  sonnet on 11 reviewers) and Side (sonnet everywhere with downshifted
  reasoning_effort). 3-tier `resolve_agent_spec()`: explicit override →
  preset map → `_spec_from_default_model` fallback (never KeyErrors on
  user-authored agents).
- **Canonical Cursor ID table** (ADR-003) — `CURSOR_MODEL_IDS` maps aliases
  (`opus`/`sonnet`/`haiku`) to concrete IDs. Users write aliases in
  `agent_models`; renderer normalizes via this table at render boundary
  (single-point upgrade across Claude releases). Templates lint-enforced
  against raw concrete IDs.
- **Codex profiles** (ADR-008) — `.codex/config.toml` now renders
  `[profiles.cheap]` (`reasoning_effort=minimal`) + `[profiles.deep]`
  (`reasoning_effort=high`). Codex agent TOMLs render
  `model_reasoning_effort` per-agent (the dominant cost lever; keep `model =`
  omission per RESEARCH-codex-plan-validator-model-unavailable).
- **/hm:health Layer-1 sub-check** (ADR-010) — new `model_routing` dimension
  with 3 advisory signals: Claude #43869 reliance, Cursor alias-form
  warnings, Codex reasoning_effort coverage. Weight 0 (advisory only;
  doesn't change composite).
- **CLI `--default-model` flag** + back-compat alias `--recommended-model`
  (ADR-012) with DeprecationWarning.
- **`--update` cwd guard** (ADR-013) — rejects snapshot regen invoked from
  inside `.worktrees/<branch>/`, turning the documented footgun
  (`[fail:snapshot-regen-inside-worktree]` count:4) into enforced
  prevention with actionable error message.
- **Silent schema migration** (ADR-004 + ADR-011) — `recommended_model:` in
  v1 harness.yaml migrates silently to `default_model`; INFO log gated on
  `schema_version<2` to avoid noise on fresh v2 renders. Multi-doc YAML
  provenance frontmatter handled via `io_utils.load_harness_yaml()`.
- **HOW-IT-WORKS docs** — new "Agent Models" section with worked example
  covering preset defaults, per-agent override, and the 3-tier resolution chain.

### Changed

- `HarnessConfig.schema_version`: 1 → 2.
- 14 agent `.md.j2` templates: hardcoded `model: opus|sonnet` → `model:
  {{ claude_model }}` (context driven by `resolve_agent_spec`).
- 2 preset YAML templates + 5 foreign-config templates: `recommended_model:`
  → `default_model:` rename.

### Fixed

- Pydantic dual-key handling for AliasChoices + `extra="forbid"` —
  `model_validator(mode="before")` silently drops `recommended_model` when
  `default_model` is also present (avoids `extra_forbidden` on rendered
  output round-trip).
- `agent_models` parse path catches `pydantic.ValidationError` in addition
  to `TypeError`/`ValueError` so a malformed override drops with a WARNING
  log instead of silently nuking the whole `answers_from_harness_yaml`
  return (Phase 2 /hm:review consensus-passed P1 fix).
- Migration log message sanitizes newline + ANSI escape sequences in
  user-provided values (security-reviewer P1 fix).
- Migration log includes the harness.yaml path so multi-repo runs can
  identify which file triggered the advisory (code-reviewer P1 fix).

## 0.14.3 — universal bootstrap prompt restored over the plugin-install paths (2026-05-17)

0.14.2 replaced the universal LLM bootstrap prompt with three per-IDE install
sections. User feedback: the universal prompt has its own value — a single
copy that any AI agent can run regardless of IDE — and should coexist with
the per-IDE manual instructions, not be replaced by them. This patch
restores the universal prompt on top of the manual section, but with the
install commands rewritten around plugin marketplaces (Claude Code,
Codex CLI) and a Cursor local-symlink fallback. The PyPI / `uv tool install`
path is preserved as a separate manual entry inside the same `<details>`
block for CI / headless / no-IDE-plugin contexts.

### Changed

- README Quickstart structure:
  - **Universal Bootstrap Prompt** at the top — IDE-autodetecting, runs
    the right `/plugin marketplace add` (Claude Code) /
    `codex plugin marketplace add` (Codex) / `git clone ~/.cursor/plugins/local/`
    (Cursor) command for the detected IDE, then drives
    `/harness-maker:make` + `/hm:health`.
  - **Manual install** in `<details>` covers four numbered paths:
    Claude Code marketplace · Codex CLI marketplace · Cursor (Team
    marketplace OR local symlink) · PyPI fallback.
- `.claude-plugin/marketplace.json` — removed `plugins[0].version`
  field. Auto-versioning by git commit SHA means future plugin patches
  don't require touching marketplace.json. Reduces the 5-file version
  sync footgun surface.
- Codex `--ref` example bumped to `v0.14.3` (current release pin).
- README.ko.md mirrored.

5-file version sync: 0.14.2 → 0.14.3.

## 0.14.2 — IDE plugin marketplace as primary install path (2026-05-17)

Reframes the install story around **plugin marketplace install**, the dominant
pattern across Claude Code / Codex / Cursor ecosystem peers (superpowers,
ruflo, spec-kit, anthropics/skills, everything-claude-code). PyPI install is
preserved as a CLI-only fallback inside a collapsed `<details>` block.

### Changed

- `.claude-plugin/marketplace.json` — renamed `name` from `harness-maker-local`
  (private-dev leftover) to `harness-maker`, owner from `noel` to `Ecro`,
  added `description` + per-plugin metadata (version, author, homepage,
  repository, license, keywords). Install command is now
  `/plugin install harness-maker@harness-maker`.
- README Quickstart — replaced the single Universal Bootstrap Prompt with
  three explicit per-IDE install sections:
  - **Claude Code**: `/plugin marketplace add Ecro/harness-maker` +
    `/plugin install harness-maker@harness-maker`.
  - **Codex CLI**: `codex plugin marketplace add Ecro/harness-maker`
    (`--ref v0.14.2` for pinned releases). marketplace add IS install for
    Codex; no separate install step.
  - **Cursor**: documents the curated-marketplace gap honestly — Team
    marketplace import path + community `~/.cursor/plugins/local/` symlink
    path.
- "First-time setup" prompt now assumes the plugin is already installed and
  only orchestrates `/harness-maker:make` + `/hm:health`. No more
  PyPI-install / uv-bootstrap steps in the LLM-facing prompt.
- README.ko.md mirrored.

### Preserved

- PyPI install (`uv tool install harness-maker`) survives inside a
  `<details>` fallback block for CI / headless / no-IDE-plugin use cases.

5-file version sync: 0.14.1 → 0.14.2.

## 0.14.1 — PyPI page Korean README link fix (2026-05-17)

Patch release. README marketing rewrite landed in commit `8e894e0` between
0.14.0 tag and now — the new English README ships an `**English** · [한국어](...)`
language switcher at the top. The relative link target was `README.ko.md`,
which resolves on GitHub but **breaks on PyPI** because PyPI's markdown
renderer does not rewrite relative paths to other files in the repository.

Fixes:
- README.md / README.ko.md language switchers now use absolute GitHub URLs
  (`https://github.com/Ecro/harness-maker/blob/main/...`).
- `pyproject.toml [project.urls]` gains a `한국어 README` entry so the
  PyPI Project Links sidebar links directly to the Korean version.

5-file version sync: 0.14.0 → 0.14.1.

## 0.14.0 — first PyPI release + communication-protocol variant family (2026-05-17)

### PyPI publication infrastructure (PLAN-pypi-publish-llm-prompts)

First public PyPI release of `harness-maker`. Install with `uv tool install harness-maker`.

**Added:**
- `.github/workflows/release.yml` — `uv publish --trusted-publishing always` to TestPyPI then PyPI on `v*` tag push. OIDC-based, no long-lived tokens. Third-party actions pinned to commit SHAs (`actions/checkout`, `actions/upload-artifact`, `actions/download-artifact`, `astral-sh/setup-uv`).
- `tests/integration/test_package_artifacts.py` — INTEGRATION=1-gated wheel/sdist regression tests (zipfile/tarfile membership of representative templates; no `__pycache__` leak).
- `scripts/release_smoke.py` — local end-to-end rehearsal (build → venv → install → CLI smoke).
- `docs/release-checklist.md` — maintainer runbook covering Phase 0 prerequisites, exact Trusted Publisher subject strings, tag command, yank procedure.
- Universal cross-platform LLM bootstrap prompt in README — single block, LLM-autonomous OS detection (Linux/macOS/Windows/WSL), works in Claude Code / Cursor / Codex / generic chat.

**Changed:**
- `pyproject.toml` — added PyPI classifiers, keywords, license-files (PEP 639), project.urls (Homepage/Repository/Issues), authors with email.
- `.claude-plugin/`, `.cursor-plugin/`, `.codex-plugin/plugin.json` — homepage/repository URLs corrected to `https://github.com/Ecro/harness-maker`.
- README install section — bootstrap prompt promoted from `<details>` to visible primary path; manual install moved into `<details>`.

**Maintenance:**
- Repo-wide ruff/mypy hygiene pass — 7 mypy --strict errors fixed (cache.py cast, interview.py dict annotation, render.py BaseLoader None guard, agent_quality.py variable shadowing), `ruff format` applied to 35 files. CI lint/type now clean.
- `tests/e2e/sandbox` regenerated to absorb post-0.13.0 schema additions and unblock 23 dogfood e2e tests that depended on `commands/hm/health.md`.

### Communication-protocol variant family (PLAN-antisycophancy-2026-05)

PLAN-antisycophancy-2026-05. Promotes the single `_partials/communication.md.j2`
into a 3-variant family (`_full`, `_reframe`, `_soft`) driven by explicit
`communication_variant` frontmatter on each dispatcher template. Variant
identity rides as an HTML comment marker in the rendered body — output
frontmatter / TOML stays clean so Cursor `.mdc` and Codex TOML strict parsers
are unaffected (ADR-004). `/hm:health` Layer 1 (structural) gains a
`communication_protocol` sub-check that surfaces silent-miss (a new agent
template added without declaring a variant) as a structured
accept/reject/defer item (ADR-006).

### Added
- `_partials/communication_full.md.j2`, `_partials/communication_reframe.md.j2`,
  `_partials/communication_soft.md.j2` — paraphrased from user SYCOPHANCY.md
  ANTISYC-FULL-v1 / REFRAME-v1 / SOFT-v1 (ADR-007). SOFT ships dormant: no
  consumer in current 14 agents.
- `harness_maker.communication_audit` — discovery + frontmatter requirement +
  marker scan + source ↔ output drift detection. Returns `ActionItem` records
  compatible with `/hm:health` Step "Per-item structured question" loop
  (0.13.0 ADR-001 "no auto-apply").
- `harness_maker.render._extract_source_communication_variant` — NEW
  pre-render extractor. Regex-based (survives Jinja expressions like
  `name: {{ name }}` in source frontmatter that break `yaml.safe_load`).
  Injects variant as Jinja context before `template.render()`.
- `_COMMUNICATION_VARIANT` table in `synthesize.py` — Codex render path
  (which bypasses dispatcher source frontmatter and includes `_body.md.j2`
  directly into TOML) gets the variant from this explicit map.
- 5 named unit tests for the variant resolver
  (`test_variant_full/reframe/soft_renders_*`,
  `test_variant_missing_raises_explicit_error` — ADR-002 forbids
  default-to-FULL, `test_variant_invalid_value_raises`).
- `tests/unit/test_communication_audit.py` with 2 acceptance fixtures
  (Fixture A: block removed from output; Fixture B: synthetic dispatcher
  missing frontmatter — silent-miss proof).

### Changed
- 14 dispatcher templates carry `communication_variant: full|reframe|soft`
  source-side frontmatter. FULL=4 (autoloop-coder, executor, stuck,
  trajectory-monitor — JSON-output, REFRAME inapplicable). REFRAME=10 (10
  reviewer-shaped agents). SOFT=0 (no idea-shaped agents).
- 14 body include sites use the variant-aware
  `{% include "agents/_partials/communication_" ~ communication_variant ~ ".md.j2" %}`
  pattern. plan-validator_body and test-reviewer_body newly receive REFRAME
  (behavior change explicitly accepted in PLAN R5).
- 5 LLM-judgment skills (agent-quality-rubric, ai-readiness-rubric,
  relevance-filter, security-scanner, refdocs-search) gain
  `communication_variant: full` frontmatter + body include (ADR-005).
  Other 7 procedural skills unchanged.
- `ai_readiness.run_structural()` invokes `audit_communication`; emits
  per-item entries via `signals_failed` and a new `communication_items`
  field on the returned dict.

### Removed
- `_partials/communication.md.j2` (single-variant partial; replaced by the
  3-variant family).

### Notes
- Stage templates retain their inline communication blocks (ADR-003
  RETRACTED in PLAN R5 after stage-specific protocol lines were surfaced as
  load-bearing — e.g. verify.md.j2's "PASS / FAIL — no soft language").
- Cursor `.mdc` render path unaffected (does not include agent bodies).
- New agent template checklist: declare `communication_variant` in source
  frontmatter; `/hm:health` Layer 1 catches the omission.

## 0.13.1 — health bug fixes + Second Brain write fix (2026-05-17)

This patch bundles two unrelated bug fix PLANs that landed on the same day:
the `/hm:health` plugin bugs (PLAN-health-plugin-bugs-2026-05) and the
Second Brain write failure (PLAN-second-brain-write-failure).

### Fixed — /hm:health plugin bugs (PLAN-health-plugin-bugs-2026-05)
- `readiness._dim_observability_setup` now reads date-sharded telemetry
  (`metrics-YYYY-MM-DD.jsonl`) via `_metrics_io._candidate_files`, not only
  the legacy `metrics.jsonl`. Both `metrics_jsonl_present` and
  `metrics_has_samples` signals now PASS on projects with rotated telemetry
  — pre-fix they failed with the misleading "Install the PostToolUse
  telemetry hook (run /hm:make)" recommendation on already-instrumented
  projects. (PLAN ADR-103 reuse.)
- `ai_readiness.run_structural()` return key renamed `"structural"` →
  `"score"`. Pre-fix the producer drifted to use the same name as the outer
  layer namespace (`{"structural": {"structural": <int>}}`), and the
  dashboard renderer + its unit tests always read `.get("score")` → every
  rendered dashboard showed `Structural score: 0 / 100` regardless of the
  real score. The `.health.tmp.json` schema between `health` and
  `health-finalize` changes by this one key rename — internal to the
  pipeline, no documented external consumers. (PLAN ADR-001.)

### Added — /hm:health regression nets
- `tests/integration/test_health_dashboard_roundtrip.py` — round-trip
  contract test that calls real `run_structural()` → real `write_dashboard()`
  → `parse_dashboard()`. Asserts `producer_score >= MIN_FIXTURE_SCORE (30)`
  AND `parsed_score == producer_score`. Plus a meta-test that fakes the OLD
  shape and proves the equality assertion fires on drift — closing the
  exact test-suite gap that let Bug 2 ship green. (PLAN ADR-002.)
- `tests/integration/conftest.py:build_min_fixture` — reusable minimal
  fixture (`.claude/`, `CLAUDE.md`, rotated telemetry, settings.json deny,
  `.github/workflows/ci.yml`, etc.) that deterministically clears the
  30-point floor on Side preset.
- Two paired regression tests in `tests/unit/test_readiness.py` covering
  the rotation-aware metrics signals (rotated-only project, rotated +
  legacy summation).

### Fixed — Second Brain (PLAN-second-brain-write-failure)
- `second_brain._load_config` no longer crashes with
  `yaml.composer.ComposerError: expected a single document in the stream` on
  rendered `harness.yaml` files. Root cause: the renderer prepends a
  provenance YAML frontmatter block, making `harness.yaml` a multi-document
  stream that single-document `yaml.safe_load` rejects. Every `/hm:research`,
  `/hm:wrapup`, and `/hm:plan` Second Brain invocation previously failed
  immediately. (ADR-001)

### Added
- `harness_maker.io_utils.load_harness_yaml(path)` — central provenance-
  frontmatter-aware loader for `harness.yaml`. Used by `second_brain`; a
  staged migration tracker (`docs/followups/io-utils-migration.md`) covers
  the remaining direct readers. (ADR-001 + ADR-007)
- Smart vault detection in `_load_config` (ADR-002): when `vault_path` does
  not exist on disk, accept it iff the parent is a real Obsidian vault
  (`.obsidian/` present) — the subdir is created on first write. A typo'd
  path with no Obsidian-vault parent fails loudly.
- Graceful degrade for `folders: []` (ADR-008): `_load_config` returns a
  degraded config + logs a remediation warning; `search_notes` returns `[]`
  + warns; `write_note` / `append_note` / `patch_note` raise
  `SecondBrainError` whose message points to `/hm:configure`.
- Interview folder enforcement (ADR-003): `_ask_second_brain` now prompts
  for a writable folder when `vault_path + project_id` are set, defaulting
  to `99_HM/{project_id}/` (ADR-004 — matches the `99_*/01_*` Obsidian
  organization style).
- `configure-second-brain` CLI subcommand (slash-command dispatch surface):
  `--check` emits guidance JSON; `--add-folder <path>` appends a writable
  folder entry to `harness.yaml`.
- `tests/integration/test_second_brain_e2e.py` — live render → load
  regression net. No snapshot pinning, so any future renderer-vs-loader
  drift fails here.

### Changed — testing
- `tests/unit/test_second_brain.py:_write_harness_yaml` now injects the
  provenance frontmatter block, mirroring real renderer output. Previous
  fixture omitted it, which is why the production crash went undetected.
  (ADR-005)

### Docs
- `CLAUDE.md` "외부 소비자의 파서 정합성" list now includes
  `.claude/harness.yaml` with explicit pointer to `load_harness_yaml`.

## 0.13.0 — health consolidation (PLAN-health-consolidation)

### Added — Phase 0 (framework groundwork)
- `reconcile.sweep_orphans()` content_hash-gated orphan-sweep (ADR-005). Walks
  `.claude/`, `.cursor/`, `.codex/`, `.agents/`, `AGENTS.md`; deletes only files
  whose frontmatter `generated_by: harness-maker` AND `content_hash` match a
  historical entry in `.claude/.hm-render-manifest.jsonl`. Theirs / copy-paste /
  `.claude/observability/adaptive/*` always KEEP + warn.
- `.hm-render-manifest.jsonl` append-only audit log written by every render via
  `io_utils.atomic_append` (`os.open(O_APPEND) + os.write`, POSIX line-atomic).
- 14 new unit tests covering the 5 ADR-005 fixture cases + R4 (adaptive
  preserved) + R7 (copy-paste foreign generated_by) + manifest idempotency.

### Added — Phase 1 (core refactor)
- `/hm:health` + `health-finalize` CLI subcommands (ADR-002/006). Replaces
  `ai-readiness*`, `refresh*`, and `personalization-audit` typer surfaces.
- `observability/dashboard.py` 3-section schema writer (`Structural` +
  `External risks` + `Personalization`) via `atomic_write`. Each layer scored
  separately; verify Check 3 reads `structural`, Check 4 reads `external_risks`,
  personalization is informational only.
- `ai_readiness.run_structural()` emits the new `structural` field shape.

### Removed — Phase 1
- `relevance.detect_version_drift` + helpers (migrated to
  `hooks/sessionstart_drift` — sole consumer; behavior bit-for-bit preserved).

### Changed — Phase 2 (template consolidation)
- DELETED `templates/commands/hm/{ai-readiness,refresh,personalization-audit}.md.j2`.
- ADDED `templates/commands/hm/health.md.j2` — three sequential layers with
  per-item `accept` / `reject` / `defer` flow (ADR-001 hard rule, no batching).
- UPDATED 3 skill SKILL.md descriptions (ai-readiness-rubric, research-crawler,
  relevance-filter) to reference the new command.

### Changed — Phase 3 (verify gate)
- `templates/stages/verify.md.j2` rewritten:
  - Check 3 reads `structural` (was `Health: NN` scalar).
  - Check 4 reads `external_risks` (path renamed `refresh/` → `health/`).
  - Both emit explicit "no-baseline PASS" when prior dashboard absent or pre-
    0.13.0 schema.
  - Personalization field never gates verify.
- New CI-safe e2e fixtures (invoke `harness_maker.cli` via `subprocess.run` —
  no Claude binary needed): `test_verify_health_dashboard.py` (engineered
  deltas + missing-baseline + pre-0.13.0 + personalization-ignored cases),
  `test_reconcile_orphan_sweep.py` (3 legacy + R4 simultaneously).

### Changed — Phase 4 (this release)
- 5-file version sync `0.12.1 → 0.13.0` (`.claude-plugin`, `.cursor-plugin`,
  `.codex-plugin`, `pyproject.toml`, `src/harness_maker/__init__.py`).
- `CLAUDE.md` + `README.md` updated to reference `/hm:health`. Atomic-stage
  list at line 145 UNCHANGED (health is a command, not a stage).
- New e2e `test_make_update_0_12_1_to_0_13_0.py` asserts `/hm:make --update`
  removes 3 legacy command files from upgraded sandboxes; user-edited theirs
  copies preserved with stdout warning; `.claude/observability/adaptive/`
  untouched.

### Architectural decisions (this PLAN)
- ADR-001: structured-question-only across all 3 layers (no auto-apply).
- ADR-002: scores remain split (3 separate dashboard fields), dashboard view
  unified.
- ADR-003: legacy commands removed atomically (rely on ADR-005 sweep).
- ADR-004: no observability-file compatibility shim; `adaptive/` preserved.
- ADR-005: reconcile gains content_hash-gated orphan-sweep.
- ADR-006: `/hm:personalization-audit` absorbed; `personalization_audit` module
  and `rubrics/personalization.yaml` are byte-identical to pre-PR state.

### Notes
- `personalization_audit.run()` output is bit-identical to 0.12.x — pinned by
  `tests/unit/test_health_personalization_integration.py`.
- ~3500 LOC delta across 4 commits on `phase0-execute-20260516T1406Z` worktree
  branch; squash-merged into main as a single 0.13.0 release commit.

## 0.12.1 — Group A follow-up patch

### Added
- TECH_SPEC.md `## 7. Personalization Architecture (0.12.0)` section — mirrors README.md update with deeper ADR cross-refs (PLAN-personalization-depth-2026-05).

### Fixed
- `detection_cache.CACHED_MANIFESTS` now includes literal filenames from `STACK_GLOB_MANIFESTS` (`stack.yaml`, `package.yaml`). Haskell projects' profile cache correctly invalidates on these manifests' mtime bump; previously stale until 24h ceiling. Glob patterns (`*.csproj`, `*.sln`, `*.cabal`) remain on 24h-ceiling-only path — they cannot be stat'd. (Closes Phase 3 known limitation from 0.12.0.)
- Snapshot fixtures regenerated — 0.12.0 release shipped with 8 failing `test_synthesize_snapshot.py` tests (`commands/hm/ai-readiness.md.j2` hash drift after Phase 10/12 template additions). 0.12.1 closes that quality gap.

### Notes
- 5-file version sync: 0.11.6 → 0.12.0 → 0.12.1 (.claude-plugin, .cursor-plugin, .codex-plugin, pyproject.toml, src/harness_maker/__init__.py).
- Code-review grade A (2 cosmetic nits deferred): asymmetric dedup in `_flatten_stack_manifests` vs `_flatten_stack_glob_concrete`; test sequencing comment.

## 0.12.0 — personalization depth (Tracks A + D + B-start)

### Added — Track A (Detection Depth)
- `ProjectProfile` schema +5 fields: `frameworks`, `package_manager`,
  `ci_provider`, `foreign_ai_configs`, `detection_confidence` (Phase 1).
- `STACK_MANIFESTS` expanded 5 → 12+: java, kotlin, swift, dart, ruby, php,
  csharp, elixir, scala, c-cpp, zig, haskell (Phase 3).
- Framework detection parses python/node/rust deps for fastapi, django,
  flask, streamlit, jupyter, react, vue, next, express, nestjs, remix,
  astro, tauri, axum, tokio, bevy, etc (Phase 3).
- `package_manager` detection: uv / poetry / pip / pipenv / npm / pnpm /
  yarn / bun / cargo (Phase 3).
- `ci_provider` detection: github-actions / gitlab-ci / circleci / jenkins
  / travis (Phase 3).
- `recommend_wrapup_docs()` detects CHANGELOG.md / TODO.md / HISTORY.md /
  docs/ADR-*.md (Phase 4).
- `recommend_mcp_servers()` framework → MCP mapping (frontend →
  playwright) (Phase 4).
- Detection cache `~/.cache/harness-maker/profile-<hash>.json` with
  manifest-mtime invalidation + 24h TTL + `atomic_write` + corruption
  recovery (Phase 2).

### Added — Track D (Foreign AI Config Migration)
- Detects 6 known foreign configs: `.cursor/rules/`, `AGENTS.md`,
  `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`,
  `.github/copilot-instructions.md` (Phase 5).
- LLM-driven mapping `foreign_config.llm_map()` with sha256
  content-keyed cache + 24h TTL (Phase 6).
- `@hm:harness:*` inverted block markers (`block_merge.py`) +
  `MarkerStyle` dispatch for HTML / HASH_COMMENT / JSON_KEY (Phase 6).
- 0.11.x file migration handler — fingerprint detection +
  first-encounter rewrite into new marker family (ADR-009 amendment,
  Phase 6).
- 6 Jinja2 templates in `templates/foreign-configs/` (Phase 6).
- `configure.md.j2` extended with conditional foreign-config import
  section (Phase 6).

### Added — Track B start (Adaptive Self-Tuning)
- `AdaptiveConfig` in `HarnessConfig` with `disable_telemetry: bool =
  False` (opt-out per ADR-005) + `audit_session_threshold: int = 30` +
  `audit_days_threshold: int = 14` (Phase 1).
- `harness_yaml_override` telemetry event with `schema_version: 1`
  mandatory + dual capture (configure-exit primary + SessionStart
  secondary) + dedup key (Phase 9).
- `/hm:personalization-audit` command with ADR-011 rubric (composite
  score 0–100; Bronze < 40 < Silver < 65 < Gold < 85 ≤ Platinum;
  L1 × 0.4 + L2 × 0.3 + L3 × 0.3) (Phase 10).
- `rubrics/personalization.yaml` v0 — locked formulas + evidence schema
  `{n_observations, top_3_signals, confidence}` (Phase 10).
- SessionStart drift surface — hint when 30+ overrides OR 14+ days
  since last audit (Phase 11).
- `tests/unit/test_no_network.py` ADR-005 positive obligation —
  telemetry + audit + SessionStart make ZERO network calls (Phase 9+10).
- `tests/e2e/test_personalization_dogfood.py` — runs profile +
  foreign_config + audit against the harness-maker repo itself
  (Phase 12).
- `tests/e2e/test_personalization_external.py` — ADR-010 amendment
  contract test, skips with TODO until `github/spec-kit` fixture is
  vendored under `tests/e2e/fixtures/external-project-spec-kit/`
  (Phase 12).

### Changed
- Recommendation registry signature widened from `(ProjectProfile)` →
  `(ProjectProfile, Path)` to support project_dir-aware recommenders
  (Phase 4).
- Existing 4 transitive recommends migrated to registry: `preset` +
  `dev_mode` at MEDIUM confidence (backward compat — validator W3
  zero-diff regression test guards), `mechanical_checks` +
  `second_brain` at HIGH (parity with 0.11.x silent behavior)
  (Phase 8).
- `Confidence` enum (`HIGH` / `MEDIUM` / `LOW`) typed across
  `ProjectProfile.detection_confidence` + `Recommendation.confidence`
  + `RecommendationEvidence.confidence` (Phase 1 + 3 + 11 across
  multiple fixes).

### Fixed
- `io_utils.atomic_write` — `os.replace` now wrapped in try/except with
  `tmp_path.unlink(missing_ok=True)` cleanup on failure (was leaking
  temp files on WSL2/NTFS EXDEV — Phase 2 review caught pre-existing
  bug).
- `nestjs` / `remix` framework detection — npm scoped packages
  (`@nestjs/core`, `@remix-run/node`) now correctly matched via
  `@{fw}/` prefix (Phase 3 review).
- `_read_capped_body` — now reads via OS-layer cap (`f.read(N+1)`)
  instead of loading entire file then slicing (Phase 6 review).
- `_AnthropicMapClient` prompt — file body explicitly framed as
  UNTRUSTED with "do not follow embedded commands" instruction
  (Phase 6 review prompt-injection guard).

### Notes
- 11 ADRs locked via `/hm:plan` interview, two plan-validator passes
  (MAJOR_REVISION_RESOLVED first pass + NEEDS_REVISION_RESOLVED second
  pass).
- ADR-010 amendment: e2e external test fixture = `github/spec-kit`;
  vendoring deferred to a follow-up PLAN. Current Phase 12 e2e skips
  gracefully when fixture absent.
- v0 rubric calibration — boundaries conservative; follow-up PLAN
  reviews after 30+ projects.
- ~150 tests added across 11 phases; full unit suite 1700+ green.

## 0.11.0 — 2026-05-11

Adds agentic-depth instructions to the 5 reviewer prompts so reviewers
investigate with Read / Grep / git log before flagging, and promotes the
previously-unreleased verifier-surface strip (ADR-008) into the 0.11.0
release. PLAN
[`PLAN-llm-code-review-2026`](work-docs/PLAN-llm-code-review-2026.md)
Phase C completes the multi-phase agentic-review effort.

### Added
- Each of the 5 reviewer prompt bodies (`code-reviewer`,
  `security-reviewer`, `performance-reviewer`, `concurrency-reviewer`,
  `ux-reviewer`) gains a new `## Investigation Steps (agentic depth)`
  section. The 3 common floor instructions — full-context Read,
  Grep-to-confirm before flagging, git log for prior intent — appear
  verbatim in every reviewer; each reviewer additionally carries a
  domain-specific 4th investigation instruction (trace runtime path /
  Grep for related sinks / Grep for hot-path callers / Grep for lock
  acquisitions / Grep for related accessibility patterns).
- New `tests/structural/test_reviewer_prompts_contain_agentic_depth_clauses.py`
  enforces the substring contract from PLAN ADR-009 Decision #1 — 5
  reviewers × 4 verbatim substrings each. Drift in any of the 5 prompt
  bodies that drops a locked substring fails this structural test at
  PR-merge time.

### Removed
- Stripped the Anthropic-API-dependent surface from the 0.10.0 verifier
  feature: `AnthropicVerifierClient` class, `ModelUnavailableError`
  exception, and the `verify` CLI subcommand (`python -m
  harness_maker.two_pass_review verify`). The target env (Claude Code as a
  subscription tool) has no `ANTHROPIC_API_KEY`, so every shipped
  invocation since 0.10.0 fell back to `model_unavailable` and Pass 1.5
  never actually ran. See ADR-008 in
  `work-docs/PLAN-llm-code-review-2026.md`.
- Removed the Pass 1.5 step from `templates/stages/review.md.j2`. Pass 1
  findings now flow directly to Pass 2; the deferral note in the rendered
  stage points at ADR-008.
- Discarded Phase A7 (wall-time baseline capture). Wall-time measurement,
  if needed, is manual and out-of-band — no auto-test, no
  `tests/fixtures/walltime_baseline_*.json` fixture.
- Removed `test_verify_falls_back_on_model_unavailable`,
  `test_verify_cli_rejects_missing_stdin`,
  `test_verify_cli_rejects_malformed_payload`, and the structural
  `tests/structural/test_review_stage_verifier_wiring.py` test along with
  the corresponding `_RaisingClient` test helper.

### Retained (library surface; future-callable)
- `verify_findings()` function + `VerifierClient` Protocol — reduce-only
  algorithm intact. Callers supplying a custom client (in-process Claude
  Code Task, future external service, mock for tests) still get the
  reduce-only invariant + demote validation + fence-escaped prompts.
  Signature is now `client: VerifierClient` (required) — the previous
  auto-instantiate-Anthropic default is gone.
- `agents/code-verifier` definition retained as the role contract;
  description unchanged.
- Telemetry JSONL schema (15 fields including `verifier_*` counts +
  `wall_time_ms`) retained — fields are now populated manually by the
  stage orchestrator rather than by an auto-invoked CLI.

### Fixed
- `CHANGELOG.md` 0.10.0 "14-field schema" → "15-field schema"
  (release-0-10-0 REVIEW M1; matches the actual `ReviewTelemetryRecord`
  field count).
- `src/harness_maker/two_pass_review.py:_build_verifier_user_prompt` —
  `fixture_label` is now fence-escaped via `_fence_escape` and the
  fixture-label block is relocated AFTER the data-treat preamble so an
  attacker-controlled label cannot inject pre-preamble instructions
  (release-0-10-0 REVIEW O1).
- `src/harness_maker/review_telemetry.py:emit` — absolute
  `observability_dir` is now containment-checked against
  `project_root.resolve()` via `is_relative_to`; escape attempts raise
  `ValueError` (release-0-10-0 REVIEW O2).

### Internal
- PLAN-llm-code-review-2026 status: `phase-a-partial-revert-c-replanned`.
  9 ADRs (ADR-001 through ADR-009) record the design decisions. Phase C
  acceptance criteria adapted post-ADR-008 — verifier-dependent tests
  replaced by prompt-only static guards per ADR-009.

## 0.10.0 — 2026-05-11

Adds a Pass-1.5 verifier sub-role and built-in JSONL telemetry to the
`/hm:review` stage, plus the previously-unreleased Second Brain, research
discovery-lens, and Codex model-omit fixes.

### Added
- New `code-verifier` agent and `verify_findings()` engine for the Pass-1.5
  reduce-only verifier in `/hm:review` (PLAN-llm-code-review-2026 ADR-002).
  Reduce-only invariant — `set(kept ∪ dropped) ⊆ input`; out-of-range LLM
  indices silently dropped; `_validated_demote_severity` rejects promotion
  attempts (a malformed verifier response with `new_severity: "P0"` on a
  P2 finding falls back to one-tier demotion + warning log).
- New `harness_maker.review_telemetry` module emitting an append-only JSONL
  row per `/hm:review` invocation at `.claude/observability/review-{date}.jsonl`
  (ADR-006). 15-field schema (`ts, slug, round, pass1_n, verifier_kept_n,
  verifier_dropped_n, verifier_false_drop_n, verifier_false_keep_n,
  fixture_label, pass2_kept_n, consensus_passed_n, wall_time_ms,
  build_break_count, auto_fix_reverted_n, fallback`). Uses POSIX `O_APPEND` +
  looped `os.write` (EINTR-resilient); PIPE_BUF (4096) write-time guard plus
  pydantic `Field(max_length=...)` schema-time guard. Concurrent reviewers
  sharing `.worktrees/` serialize at the kernel level for writes ≤ PIPE_BUF.
- New `python -m harness_maker.two_pass_review verify` and
  `python -m harness_maker.review_telemetry emit` CLI subcommands so stage
  templates pipe JSON contracts through Python instead of re-implementing
  them in prose.
- New `tests/snapshot/EXCLUSIONS.md` mechanism (empty list at ship — Phase C
  populates) so reviewer-output paths can opt out of snapshot comparison
  when prompt-only agentic depth lands (ADR-005).
- New `tests/structural/` test category for assertions that complement
  snapshot comparison: verifier agent permissions, review-stage wiring,
  reviewer-output schema on a labeled adversarial fixture,
  snapshot-exclusion mechanism, and telemetry-leak grep lint.
- Filesystem-backed Obsidian Second Brain configuration and helper commands
  for typed Markdown notes — project-scoped write allowlists, frontmatter
  / tag / link validation, and stage-aware research / plan / review /
  wrapup guidance.

### Changed
- `/hm:review` Step 3 now runs Pass 1 → Pass 1.5 verifier → Pass 2 (the
  verifier-kept set is the input to Pass 2, not raw Pass 1). Pass 2 prompt
  body now includes `## Diff` explicitly — the parameter was previously
  accepted but never interpolated, leaving reviewers with no diff to
  validate findings against.
- `_build_verifier_user_prompt` fence-escapes LLM-originated `summary` /
  `reasoning` fields per the same defense used in `build_pass2_prompt` so
  a prompt-injected Pass-1 finding cannot break out of its block and leak
  instructions into the verifier turn.
- Updated `/hm:research` so broad trend, roadmap, and opportunity research
  starts with a user-workflow / product discovery lens before papers,
  benchmarks, or architecture-only sources.

### Fixed
- Omit per-agent `model = ...` line from rendered `.codex/agents/*.toml`.
  The hardcoded `o4` / `o4-mini` strings were rejected on ChatGPT-tier Codex
  CLI subscriptions with HTTP 400 `invalid_request_error`, causing reviewer
  / validator subagents (including `/hm:plan` Step 4 plan-validator) to fail
  to spawn. With the field omitted Codex inherits the account's
  `~/.codex/config.toml` profile default automatically. The template's
  `{% if model_codex %}` gate is preserved so a future opt-in
  `codex_agent_models` knob on `HarnessConfig` can re-enable per-agent models
  without touching the template. See ADR-001 in
  `work-docs/PLAN-codex-plan-validator-model-unavailable.md`.

### Internal
- `_codex_agent_files()` count assertions now derive from `_ALL_AGENTS`
  length so future agent registrations don't require manual test edits.
- Tightened the concurrent-writer test: round-trip JSON equality detects
  byte-tearing, not just missed records.

## 0.9.3 — 2026-05-10

Patch release after the Codex target rollout.

### Fixed
- Fixed conditional-router skill frontmatter so YAML descriptions containing
  colons do not create a double-frontmatter parse failure.
- Synchronized sandbox renders and snapshot baselines after the 0.9.3 bump.

## 0.9.2 — 2026-05-10

### Fixed
- Fixed Codex `config_file` rendering so paths do not accidentally include a
  duplicated `.codex/` segment.

## 0.9.1 — 2026-05-10

### Changed
- Version synchronization release after 0.9.0.

## 0.9.0 — 2026-05-10

### Added
- Added OpenAI Codex CLI as a third harness target alongside Claude Code and
  Cursor.
- Codex target renders `AGENTS.md`, `.codex/config.toml`,
  `.codex/hooks.json`, `.codex/agents/*.toml`, and `.agents/skills/*/SKILL.md`
  from the same preset, workflow, skill, and agent definitions.
- Added Codex workflow and loop skills so atomic stages, fused workflows, and
  `/hm:loop` are discoverable through Codex's skill layout.
- Added Codex agent registration in generated config.

### Changed
- Generated outputs (`.claude/`, `.codex/`, `.agents/`, and `AGENTS.md`) are
  treated as render artifacts and ignored in the source repo.
- Reconcile and render paths now understand Codex-specific pure TOML files and
  block-merge-aware `AGENTS.md`.

## 0.8.1 — 2026-05-10

### Added
- Added `ref_folders` and `sibling_repos` to the make interview and CLI flags.
- `ref_folders` can build a local docs index for the `refdocs-search` skill.
- `sibling_repos` lets worktree isolation include related repositories in the
  same logical run.

## 0.8.0 — 2026-05-10

### Added
- Completed the make UX lifecycle for install, configure, update, add, remove,
  and promote flows.
- Added `wrapup_docs`, allowing users to configure documents that `/hm:wrapup`
  should keep updated after work units.
- Added the 3-layer deep interview gate for research, spec, plan, and loop.

## 0.7.1 — 2026-05-08

Patch release closing all P1 + P2 carry-overs from
`REVIEW-harness-gap-cot-2026-05-2026-05-08.md` and
`REVIEW-harness-gap-cot-wiring-2026-05-08.md`. No new features; no
architectural changes; no breaking API changes.

> **Note on version sequencing:** the marketplace stamps had remained at
> 0.6.2 even though the 0.7.0 wiring round (commits 52346c9 → 00d91a0 →
> 3c7304a) was complete on `main`. This release coalesces that internal
> 0.7.0 work + this 0.7.1 cleanup into a single marketplace-published
> 0.7.1 — there is no separate published 0.7.0 artifact.

### Closed REVIEW findings

#### Security
- **Sec-R2-3 (P1)** — `telemetry.py` cwd resolution now uses env-var
  precedence (`CLAUDE_PROJECT_DIR` → `CURSOR_PROJECT_DIR` → stdin
  `workspace.current_dir` → `os.getcwd`). The bare stdin `cwd` field is
  no longer consulted; a poisoned PostToolUse payload can no longer
  redirect metric writes to an attacker-chosen path. (ADR-102)
- **Sec-R2-6 (P1)** — `_load_recent_tool_calls` now reads structured
  `tool_input` whose schema is enforced at write time (whitelist
  projection); upstream poisoning paths are narrowed.
- **Sec F6 parent (P1)** — `DriftMonitor.score` wraps both baseline and
  current text in XML fences with an instruction preamble before
  passing to the LLM judge; embedded `</baseline>` / `</current>`
  close-tags are escaped so an adversarial SPEC body cannot inject
  instructions. (ADR-108)
- **Sec F7 parent (P1)** — `secscan.hallucination._is_available` no
  longer calls `importlib.util.find_spec`; uses a pure filesystem scan
  of `sys.path` so the hallucination gate cannot be coerced into
  executing `__init__.py` or `.pth`-registered finder side effects.
  (ADR-105)
- **Sec F7 R2 (P2)** — `tool_input` strings are scrubbed by
  `_SECRET_PATTERNS` (`sk-…`, `ghp_…`, `AKIA…`, `Bearer …`) before the
  256-char value cap, so a partial-secret tail cannot survive
  truncation. (ADR-107)

#### Concurrency / data integrity
- **Conc-R2-2 (P1)** — Documented the lock-free read contract on
  `SemanticStore.read_all` / `search` and `ProfileStore.get` /
  `get_all`: `os.replace` atomicity guarantees readers see either the
  pre- or post-write file in full, but a read concurrent with a write
  may return the pre-write snapshot. (ADR-104)
- **Code F1 (P1, latent)** — `exclusive_lock` is now re-entrant within a
  single thread via a `threading.local` depth counter keyed by lock
  path string. Same thread can acquire the same lock twice without
  deadlock. (ADR-106)

#### Performance
- **Perf-R2-1 (P1)** — `metrics.jsonl` now rotates per-day to
  `metrics-YYYY-MM-DD.jsonl`; the legacy filename remains readable as a
  compat fallback. New shared reader `harness_maker._metrics_io.iter_recent_entries`
  walks dated files newest-first; both `cache_diagnostics.diagnose_cache`
  and `security_scanner._load_recent_tool_calls` use it (no more
  full-file `read_text().splitlines()`). (ADR-103)
- **Perf F5 (P2)** — `prod_name_guard.scan_sequence` switched to a
  `collections.deque(maxlen=window)` sliding-window walk; per-call cost
  dropped from O(n × window) to O(window).
- **Perf F6 (P2)** — `SemanticStore.write_many` bulk helper acquires
  the lock once for N entries instead of N times via repeated `write`.
- **Perf F7 (P2)** — `EpisodicStore.read_all(max_days=30)` defaults to
  the 30 most recent daily files; pass `None` for the pre-0.7.1
  unbounded behaviour.
- **Perf PF4 (P1, parent)** — `_is_available` now memoises via
  `functools.lru_cache(maxsize=512)`.

#### Code quality
- **Code F2 (P1)** — `security_scanner.scan_all` docstring updated from
  "5 gates" to "7 gates" (matches actual gate count since 0.7.0).
- **Code F3 (P1)** — `two_pass_review.merge_passes` now requires Pass-2
  entries to carry at least one `severity` key; otherwise treats Pass 2
  as failed and falls back to Pass 1, guarding against a malformed
  `[{}]` LLM response silently dropping all findings.
- **Code F7 (P2)** — `secscan.hallucination` now walks `except`
  handler bodies when collecting `guarded_lines`; the fallback import
  in `try/except ImportError: import alt` is now correctly tagged P2
  (guarded) instead of P0.
- **Code F8 (P2)** — `cache_diagnostics` zero-token skip uses
  `(parsed.get(field) or 0) == 0` so JSON `null` values also trigger
  the skip.

#### Tests
- 4 concurrency multiprocess tests bumped `p.join(timeout=30)` →
  `timeout=60` and added `assert not p.is_alive()` before the
  `exitcode` assertion to distinguish timeout from crash.
- New tests: `test_metrics_io.py` (6), `test_locking.py` (3), plus 6
  acceptance tests across telemetry / drift / hallucination /
  episodic / semantic for the items above.

### Out of scope (intentional carry-overs)

These remain on disk as documented limitations; promoted to the 0.8.0
plan if user feedback warrants:
- Sec F2 / F5 (parent) — `security_scanner._persist` and
  `telemetry` JSONL persistence still use plain `open("a")`. Treated as
  a deliberate hot-path exception; documented in code.
- SQLite migration for `semantic` / `profile` (rejected ADR-104).
- LOCK_SH read-side locking (rejected ADR-104).
- `find_spec` retention with `PYTHONNOUSERSITE` (rejected ADR-105).
- Schema versioning for metrics.jsonl entries — handled via
  forward-compatible field addition.
