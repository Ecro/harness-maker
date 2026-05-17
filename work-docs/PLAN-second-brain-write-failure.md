---
type: plan
task_slug: second-brain-write-failure
status: complete
created: 2026-05-17
tags: [harness-maker, plan, second-brain, obsidian, defect-fix]
research_doc: "[[RESEARCH-second-brain-write-failure]]"
interview_rounds: 3
adrs: 8
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "5-phase fix: loader contract + smart vault + folder enforcement + e2e guard + docs."
---

# 🎯 Executive Summary

The Second Brain connector is non-functional on this repo because three defects stack: (1) `_load_config` uses `yaml.safe_load` against a frontmatter-wrapped `harness.yaml` and crashes, (2) `folders: []` silently rejects all writes and returns empty searches, (3) the configured `vault_path` (`/mnt/c/.../obsidian-vault/second-brain`) does not exist on disk while the parent `obsidian-vault/` is a real Obsidian vault. The fix is a 5-phase implementation that centralizes harness.yaml loading via a shared helper, adds a smart vault-existence check using `.obsidian/` parent detection, makes folder configuration an enforced step in both interview and `/hm:configure`, and locks the contract with both fixture parity and a render-based e2e test.

**Key decisions** (full text in §📐 ADRs):
- ADR-001 — extract `harness_maker.io_utils.load_harness_yaml()` helper; staged migration (this PLAN: `second_brain` only).
- ADR-002 — smart vault detection: auto-mkdir when parent has `.obsidian/`, hard-error otherwise; mkdir within configured folders is intentional.
- ADR-003 — folder configuration enforced at interview first-entry AND `/hm:configure` re-entry.
- ADR-004 — default folder convention `99_HM/{project_id}/` (matches user's `99_*/01_*` vault style).
- ADR-005 — test contract requires BOTH fixture parity with rendered output AND a render-based e2e test (live render, no snapshot).
- ADR-006 — wrapup Obsidian-note write stays Advisory.
- ADR-007 — staged io_utils migration: tracker in `docs/followups/io-utils-migration.md`.
- ADR-008 — existing `folders: []` users get graceful degrade with remediation hint, not hard-error at load.

**Estimated impact**: ~9 file edits + 3 new files (helper, follow-up tracker, e2e test). Backward-compatible for existing users via graceful degrade. Unblocks every `/hm:research`, `/hm:wrapup`, and `/hm:plan` invocation that queries Second Brain.

# 📚 Prior Work

- `work-docs/RESEARCH-second-brain-write-failure.md` — bug analysis with code citations.
- `.claude/memory/session/2026-05-11.md:102-103` — `[decision:user-workflow-opportunities-2026-05]` Second Brain uses project namespaces (validator-enforced `project_id` in writable folder paths).
- `.claude/memory/pending-drift.md:4` — prior E501-only patch in Second Brain override path; non-overlapping with this PLAN.
- CLAUDE.md §"무언가를 고치거나 개선하기 전에" items 1 (state preservation contract), 2 (external-consumer parser compatibility), 4 (CLI vs slash separation), 6 (bidirectional mapper), 7 (test determinism), 8 (integration boundary) — all directly applicable to this fix.
- Prior parser-strategy precedents: `verify.py:34`, `worktree.py:315/340`, `rubric_loader.py:52` use `yaml.safe_load_all`; `context_lint.py:42`, `autoloop_driver.py:233` use `_strip_frontmatter`. This PLAN unifies via a new helper.

# 🎙️ Interview Transcript

| # | Round | Topic | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | 1 | Loader shape | safe_load_all local fix vs io_utils helper vs staged helper | Helper + second_brain-only migration | Staged migration prevents drift while keeping diff bounded | ADR-001 + ADR-007 |
| 2 | 1 | Empty folders behavior | Hard-error / auto-seed / configure prompt / both | /hm:configure enforcement (interview + configure both) | User explicitly chose enforcement timing, not load-time error | ADR-003 |
| 3 | 1 | Missing vault | Auto-mkdir / hard-error / warn / smart (parent .obsidian) | Smart — clarified user's vault does have .obsidian | Free-form note: "smart 로 하고 싶은데 .obsidian 폴더가 없던데 내꺼는" → fact-checked false | ADR-002 |
| 4 | 1 | Test fixture | Fixture only / e2e only / both / loader-direct unit | Both — fixture + render-based e2e | Defense in depth | ADR-005 |
| 5 | 2 | Vault confirm | Smart confirmed / change to hard-error / change to warn | Smart confirmed (after fact-check) | Vault confirmed Obsidian-active w/ recent updates | ADR-002 |
| 6 | 2 | Configure flow | Interview + configure / configure-only / interview-only | Both | Round-trip safety | ADR-003 |
| 7 | 2 | Default folder layout | {pid}/ vs Projects/{pid}/ vs 99_HM/{pid}/ vs free | 99_HM/{project_id}/ | Matches user's 99_Meta/01_Info numeric-prefix style | ADR-004 |
| 8 | 2 | Wrapup contract | Advisory / Strong / Mandatory | Advisory | LLM-best-effort acceptable; mandatory creates synthetic notes risk | ADR-006 |
| 9 | 3 | Existing users gap | Graceful degrade / hard-error at load / auto-seed | Graceful degrade w/ remediation hint | Validator W2 — locked policy for upgrade-path | ADR-008 |
| 10 | 3 | Write-time mkdir | Intentional (keep) / footgun (gate) / hybrid | Intentional — keep | Validator W1 — mkdir within configured folder is user's expressed intent | ADR-002 |

**Layer 3 Ambiguity Score (Round 3)**: 1.0 (Goal 1.0 · Constraint 1.0 · SC 1.0) — PASS, exit gate cleared.

# 📐 Architecture Decision Records

### ADR-001: Extract `harness_maker.io_utils.load_harness_yaml()` helper
**Status:** Accepted (2026-05-17, via /hm:plan interview Round 1)
**Context:** `_load_config` in `second_brain.py:232` crashes on production `harness.yaml` because it uses single-document `yaml.safe_load` against a file with provenance frontmatter. Other modules use three different strategies (`safe_load_all` in verify/worktree/rubric_loader, `_strip_frontmatter` in context_lint/autoloop_driver) — parser-strategy drift is already a pitfall (RESEARCH §Pitfall 2).
**Decision:** Add `harness_maker.io_utils.load_harness_yaml(path: Path) -> dict` that handles provenance frontmatter via `yaml.safe_load_all` and returns the last (= user-data) document. `second_brain._load_config` migrates to this helper.
**Consequences:**
- ✅ Eliminates the crash for every Second Brain CLI invocation.
- ✅ Provides a canonical loader future contributors can reuse.
- ⚠️ Three pre-existing readers (`verify.py`, `worktree.py`, `autoloop_driver.py`, `context_lint.py`) remain on legacy strategies — staged migration tracked in ADR-007.
**Rejected alternatives:**
- Minimal local patch (`safe_load_all` inline at `second_brain.py:232`) — Rejected because RESEARCH §Pitfall 2 shows the same defect class will recur in the next new reader.
**Source:** Interview #1

### ADR-002: Smart vault-existence check + intentional write-time mkdir
**Status:** Accepted (2026-05-17, via /hm:plan interview Rounds 1+2+3)
**Context:** `vault_path` may not exist on disk (user's case: configured `obsidian-vault/second-brain` but only `obsidian-vault/` exists). Current `write_note` blindly calls `mkdir(parents=True, exist_ok=True)`, manufacturing phantom dirs. But within an existing Obsidian vault, creating a subfolder *is* the user's intent.
**Decision:** Two-layer rule.
- **Vault root (load time)**: If `vault_path` does not exist, check whether `vault_path.parent / '.obsidian'` is a directory. If yes → permit (the user is asking for a subfolder of a real Obsidian vault). If no → raise `SecondBrainError("vault parent is not an Obsidian vault")`.
- **Inside configured folders (write time)**: `mkdir(parents=True, exist_ok=True)` stays — once a folder is in `cfg.folders`, the user has expressed intent to write there.
**Consequences:**
- ✅ User's exact case (`obsidian-vault/second-brain/` missing under `obsidian-vault/.obsidian/`) now succeeds.
- ✅ Typo'd vault paths (no `.obsidian/` parent) fail loudly instead of silently producing phantom dirs.
- ⚠️ Smart detection only inspects the immediate parent; nested-vault edge cases not handled (mitigated by R3 in risk register).
**Rejected alternatives:**
- Hard-error always when vault_path missing — Rejected because it blocks the legitimate "create subfolder for me" intent.
- Silent auto-mkdir without parent check — Rejected because it masks real misconfiguration.
- Gate write-time mkdir behind a flag — Rejected at Round 3: user confirmed mkdir within a configured folder is intentional.
**Source:** Interviews #3, #5, #10

### ADR-003: Folder configuration enforced at interview AND `/hm:configure`
**Status:** Accepted (2026-05-17, via /hm:plan interview Rounds 1+2)
**Context:** `interview.py:469` comment: "user adds folders directly to harness.yaml after initial setup" — but nothing in the UX nudges them to, and `folders: []` produces silent-success on search and an obscure error on write.
**Decision:** `interview._ask_second_brain` gets a folder-input step (after vault_path + project_id capture). `/hm:configure` slash command always invokes a CLI subcommand `harness-maker configure --second-brain --check` that inspects state and emits guidance JSON; the slash command then renders an `AskUserQuestion` based on the JSON. Both paths produce one or more `SecondBrainFolder` entries before write.
**Consequences:**
- ✅ New installations cannot reach a `folders: []` state through normal UX.
- ✅ Existing users who re-run `/hm:configure` get prompted to complete setup.
- ✅ Slash-command vs CLI separation honored (CLAUDE.md item 4).
- ⚠️ Existing users who *don't* re-run `/hm:configure` fall through to the graceful-degrade path in ADR-008.
**Rejected alternatives:**
- Configure-only / interview-only — Rejected; round-trip safety needs both.
- Slash command branches conditionally on file state — Rejected because slash commands are Jinja-rendered templates and cannot inspect runtime state; CLI must own state inspection.
**Source:** Interviews #2, #6

### ADR-004: Default folder convention `99_HM/{project_id}/`
**Status:** Accepted (2026-05-17, via /hm:plan interview Round 2)
**Context:** The folder-enforcement step needs a default to propose. The validator (`models.py:_write_folders_are_project_namespaced`) requires `project_id` in any writable folder path.
**Decision:** Default-suggest `99_HM/{project_id}/` with `read: true, write: true, note_types: [all]`. User can edit during interview or via CLI flag.
**Consequences:**
- ✅ Matches the user's vault's `99_Meta/01_Info/02_Week Plan/...` numeric-prefix organization style.
- ✅ Project-namespaced (validator-compliant).
- ⚠️ Other users with different organization styles must edit. CLI flag (`--second-brain-folder add <path>`) provides a non-interactive override.
**Rejected alternatives:**
- `{project_id}/` (root-level) — Rejected; pollutes vault root.
- `Projects/{project_id}/` — Rejected; clashes with user's numeric-prefix style.
- No default proposal (user types every time) — Rejected; high UX friction.
**Source:** Interview #7

### ADR-005: Test contract — fixture parity + render-based e2e
**Status:** Accepted (2026-05-17, via /hm:plan interview Round 1)
**Context:** RESEARCH §Pitfall 1 — `tests/unit/test_second_brain.py:30-35` builds harness.yaml via `yaml.safe_dump` without provenance frontmatter, so unit tests never exercise the real rendered file shape. Result: full unit suite passed while production was 100% broken.
**Decision:** Two complementary regression nets.
- **Fixture parity**: `_write_harness_yaml` injects provenance frontmatter mirroring `harness_maker.render`'s output.
- **Render-based e2e**: `tests/integration/test_second_brain_e2e.py` calls `harness_maker.render` live and asserts on `_load_config`'s output (no snapshot of rendered bytes — that would defeat the test's purpose per validator W8).
**Consequences:**
- ✅ Fast unit suite catches code regressions; slower e2e catches contract drift between renderer and consumer.
- ✅ Production.yaml.j2 changes that break `_load_config` now fail in CI.
- ⚠️ Two test fixtures to maintain. Mitigated by keeping e2e's fixture override surface minimal (only the `second_brain` block).
**Rejected alternatives:**
- Fixture-only — Rejected; doesn't catch renderer-vs-consumer drift.
- E2e-only — Rejected; unit tests need to stay fast.
- Snapshot-pinned e2e — Rejected at validator W8; freezing the rendered bytes defeats the drift-detection purpose.
**Source:** Interview #4, Validator W8

### ADR-006: Wrapup Obsidian-note write stays Advisory
**Status:** Accepted (2026-05-17, via /hm:plan interview Round 2)
**Context:** `templates/stages/wrapup.md.j2:40-53` instructs the LLM to invoke `harness_maker.second_brain write` for durable notes, but it is a prompt suggestion — the LLM may skip it.
**Decision:** Keep Advisory phrasing. Do not add a wrapup gate that fails when zero notes were written this session.
**Consequences:**
- ✅ No synthetic notes manufactured to satisfy a gate.
- ✅ Wrapup remains fast for short sessions.
- ⚠️ Some sessions will leave no durable note. Acceptable — the user explicitly chose this trade-off.
**Rejected alternatives:**
- Strong (warning gate on zero notes) — Rejected; the count signal is noisy and warning fatigue likely.
- Mandatory (wrapup fails on zero notes) — Rejected; risk of fabricated notes is worse than no notes.
**Source:** Interview #8

### ADR-007: Staged `io_utils` migration
**Status:** Accepted (2026-05-17, via /hm:plan interview Round 1)
**Context:** ADR-001 introduces `load_harness_yaml()`. Migrating all 5 existing callers (`second_brain`, `verify`, `worktree`, `autoloop_driver`, `context_lint`) in one PR enlarges the diff and increases regression surface across unrelated subsystems.
**Decision:** Migrate `second_brain._load_config` only in this PLAN. Track the remaining four callers in `docs/followups/io-utils-migration.md` with file path, current strategy, and migration TODO. Add a `# TODO(io-utils-migration)` comment at each unmigrated site.
**Consequences:**
- ✅ Scope-bounded PR.
- ✅ Tracker makes the deferred work discoverable.
- ⚠️ Drift hazard remains until the tracker is closed. Mitigated by the comment markers.
**Rejected alternatives:**
- Migrate everything now — Rejected; out of scope for the user's reported bug.
- Defer silently — Rejected; loses the lesson learned.
**Source:** Interview #1, Validator W5

### ADR-008: Existing-user graceful degrade for `folders: []`
**Status:** Accepted (2026-05-17, via /hm:plan interview Round 3)
**Context:** Users with `harness.yaml` rendered before this PLAN have `folders: []`. After upgrade, the next `/hm:research` or `/hm:wrapup` invocation queries Second Brain. CLAUDE.md item 1 ("사용자 상태 보존 계약") implies we should not hard-break these users.
**Decision:** `_load_config` returns successfully when `folders: []`. `search_notes` returns `[]` (current behavior — but with a logged-once-per-session warning). `write_note` and `append_note` raise `SecondBrainError("second_brain.folders is empty — run /hm:configure to add at least one folder")`. The error message names the remediation step.
**Consequences:**
- ✅ Search-only flows (research-stage Second Brain lookup) keep working in degraded mode without crashing.
- ✅ Write attempts fail loudly with actionable guidance.
- ✅ State-preservation contract honored: no automatic writes to the user's vault.
- ⚠️ The "silently empty results" surface persists for searches until the user runs `/hm:configure`. The one-time warning log makes it discoverable.
**Rejected alternatives:**
- Hard-error at load — Rejected; breaks every SB-touching command for users mid-session.
- Auto-seed `99_HM/{project_id}/` at load time — Rejected; writes to the user's vault without consent is contrary to ADR-002's principle.
**Source:** Interview #9, Validator W2

# 🏗️ Technical Design

## Current state
`second_brain.py:_load_config` (line 228) calls `yaml.safe_load(harness.yaml)`. Production `harness.yaml` always carries a provenance frontmatter block (`---\ngenerated_by:...\n---`) injected by `render.py:_format_frontmatter`. `yaml.safe_load` rejects multi-document streams → every Second Brain invocation crashes immediately. Even if parsing succeeded, `cfg.folders == []` in the current `.claude/harness.yaml` would silently reject all writes and return empty searches; and the configured `vault_path` does not exist on disk.

## Affected components
| File | Change |
|---|---|
| `src/harness_maker/io_utils.py` | New `load_harness_yaml(path)` helper. |
| `src/harness_maker/second_brain.py` | `_load_config` uses helper; smart vault check; degrade for `folders=[]`. |
| `src/harness_maker/interview.py` | `_ask_second_brain` gains folder-input step. |
| `src/harness_maker/synthesize.py` | Default folder proposal (`99_HM/{project_id}/`). |
| `src/harness_maker/cli.py` | New `configure --second-brain` subcommand. |
| `src/harness_maker/templates/commands/hm/configure.md.j2` | Slash command dispatches to CLI for state. |
| `tests/unit/test_second_brain.py` | Fixture injects frontmatter; new degrade-mode tests; 3 vault cases. |
| `tests/unit/test_io_utils.py` | New helper tests. |
| `tests/integration/test_second_brain_e2e.py` | New render-based e2e (live render). |
| `CLAUDE.md` | Add `harness.yaml` to external-consumer parser-compat list. |
| `docs/followups/io-utils-migration.md` | New follow-up tracker for 4 remaining callers. |
| `README.md` or `docs/HOW-IT-WORKS.md` | Second Brain setup anchor. |
| `CHANGELOG.md` | Entry for next version. |

## Data flow
1. User invokes `/hm:research` → slash command calls `second_brain search`.
2. CLI loads `harness.yaml` via `load_harness_yaml()` (ADR-001).
3. `_load_config` validates → either returns full config, or returns degraded config with warning (ADR-008), or raises with remediation hint (ADR-002 vault-missing path).
4. Search/write proceed against configured folders; mkdir on first write inside configured folder (ADR-002).
5. Wrapup may opportunistically write durable notes (ADR-006 advisory).

## Design notes
- `load_harness_yaml()` uses `yaml.safe_load_all(text)` and takes the **last** non-empty document. This works for both frontmatter-wrapped (= 2 docs) and frontmatter-less (= 1 doc) inputs.
- Smart vault check uses `Path(vault_path).parent.joinpath('.obsidian').is_dir()`. Symlinks are followed (default behavior).
- Graceful degrade emits a single warning per process via `logging.getLogger('harness_maker.second_brain').warning(...)`.
- CLI `configure --second-brain --check` outputs JSON: `{"folders_empty": true, "vault_path": "...", "default_suggestion": "99_HM/harness-maker/"}` so the slash command can render `AskUserQuestion` deterministically.

# 📝 Implementation Plan

## Phase 1 — Loader fix + parser-compat doc
**Scope (in):**
- New: `src/harness_maker/io_utils.py` — `load_harness_yaml(path: Path) -> dict` function (extend existing module; `atomic_write` already lives there).
- Edit: `src/harness_maker/second_brain.py` — `_load_config` symbol uses the helper.
- Edit: `tests/unit/test_second_brain.py` — `_write_harness_yaml` fixture symbol injects provenance frontmatter.
- New: `tests/unit/test_io_utils.py` — helper tests (frontmatter / no-frontmatter / empty doc / malformed doc).
- Edit: `CLAUDE.md` — add a row for `harness.yaml` in the §"외부 소비자의 파서 정합성 확인" parser-compat list noting the provenance-frontmatter contract.
- New: `docs/followups/io-utils-migration.md` — tracker listing `verify.py`, `worktree.py`, `autoloop_driver.py`, `context_lint.py` with current strategy and migration TODO. Source-code: add `# TODO(io-utils-migration)` comments at each of the four call sites.

**Scope (out):** Migrating the four other callers themselves.

**Exit criteria (all must pass):**
1. `uv run python -c "from pathlib import Path; from harness_maker.second_brain import _load_config; print(_load_config(Path('.')).enabled)"` prints `True` without raising `yaml.YAMLError`.
2. `uv run pytest tests/unit/test_io_utils.py tests/unit/test_second_brain.py -x` passes (run in background per pytest-background policy).
3. `grep -c "harness.yaml" CLAUDE.md` in the parser-compat section ≥ 1.
4. `docs/followups/io-utils-migration.md` exists and lists 4 caller file paths.
5. `grep -c "TODO(io-utils-migration)" src/harness_maker/{verify,worktree,autoloop_driver,context_lint}.py` totals exactly 4.

**Risk:** low
**Rollback:** revert to `main`.

## Phase 2 — Smart vault detection + graceful degrade
**Scope (in):**
- Edit: `src/harness_maker/second_brain.py` — `_load_config` symbol adds (a) vault-existence + `.obsidian/`-parent detection (ADR-002), (b) graceful degrade for `folders=[]` (ADR-008). `_vault_root` may be split or left as-is.
- Edit: `tests/unit/test_second_brain.py` — add 3 vault cases (exists / missing-but-parent-vault / missing-and-no-parent-vault) and 3 degrade cases (load returns OK / search returns []  / write raises remediation error).

**Exit criteria:**
1. New unit tests pass: 3 vault cases + 3 degrade cases.
2. Manual reproduction: `python -c "from harness_maker.second_brain import _load_config; from pathlib import Path; _load_config(Path('.'))"` succeeds with the current (`folders=[]` + `vault_path=/mnt/c/.../obsidian-vault/second-brain`) configuration and emits the expected warning.
3. Negative test: temporarily setting `vault_path` to `/tmp/not-a-vault-x/` (no `.obsidian/` parent) raises `SecondBrainError` with message containing "not an Obsidian vault".

**Risk:** low
**Rollback:** Phase 1.

## Phase 3 — Interview + `/hm:configure` folder enforcement
**Scope (in):**
- Edit: `src/harness_maker/interview.py` — `_ask_second_brain` symbol adds folder-input step (after vault_path + project_id), defaulting to `99_HM/{project_id}/`.
- Edit: `src/harness_maker/synthesize.py` — `answers_to_config` (or equivalent) propagates the new folder default.
- Edit: `src/harness_maker/cli.py` — new `configure --second-brain --check` subcommand emitting guidance JSON; new `--second-brain-folder add <path>` and `--second-brain-folder list` flags.
- Edit: `src/harness_maker/templates/commands/hm/configure.md.j2` — Second Brain section calls the CLI subcommand and renders `AskUserQuestion` from JSON output (CLAUDE.md item 4 — CLI vs slash separation).

**Exit criteria:**
1. New unit test: running interview with `vault_path=/tmp/v` (mocked) + `project_id=test` produces `folders=[SecondBrainFolder(path='99_HM/test/', read=True, write=True, ...)]`.
2. New CLI test: `harness-maker configure --second-brain --check` on a fixture with `folders=[]` returns exit code 0 with JSON containing `"folders_empty": true`.
3. New snapshot test: rendered `configure.md` contains a dispatch to the CLI subcommand (no inline state inspection).
4. End-to-end (manual): on the current `.claude/harness.yaml`, running `/hm:configure` would surface the folder prompt.

**Risk:** medium (interview UX change; slash-vs-CLI dispatch contract change).
**Rollback:** Phase 2.

## Phase 4 — Render-based e2e regression test
**Scope (in):**
- New: `tests/integration/test_second_brain_e2e.py` — invokes `harness_maker.render.render` live to produce a `harness.yaml`, then calls `_load_config` + a write + a read roundtrip. **No snapshot of rendered bytes** (ADR-005 / validator W8). Override only the `second_brain` block of the test config.

**Exit criteria:**
1. `INTEGRATION=1 uv run pytest tests/integration/test_second_brain_e2e.py -x` passes (run in background).
2. Drift-detection demo (one-off, recorded in PR description): temporarily corrupt `Production.yaml.j2`'s `second_brain:` block (e.g., emit `vault_path: !badtype 1`) — the e2e test must fail, proving the regression guard works.

**Risk:** low
**Rollback:** Phase 3.

## Phase 5 — User-facing docs + CHANGELOG
**Scope (in):**
- Edit: `README.md` or `docs/HOW-IT-WORKS.md` — add a "Second Brain setup" section with an HTML anchor (`<a id="second-brain-setup"></a>`).
- Edit: `CHANGELOG.md` — entry under the next unreleased version mentioning "second_brain" with summary of fix.

**Exit criteria:**
1. `grep -E "second-brain-setup" README.md docs/HOW-IT-WORKS.md 2>/dev/null | wc -l` ≥ 1.
2. `git diff CHANGELOG.md` includes a new entry referencing "second_brain".
3. Full `uv run pytest` suite passes (background; per CLAUDE.md pytest-background policy).
4. `uv run ruff check src/ tests/` + `uv run mypy --strict src/` pass.

**Risk:** low
**Rollback:** Phase 4.

# 🧪 Testing Strategy

| Layer | Where | What |
|---|---|---|
| Unit | `tests/unit/test_io_utils.py` | `load_harness_yaml` edge cases (frontmatter, no-frontmatter, empty doc, malformed YAML, multi-doc with empty trailing). |
| Unit | `tests/unit/test_second_brain.py` | (existing) — fixture updated to mirror render output; (new) 3 vault cases + 3 degrade cases. |
| Unit | `tests/unit/test_interview.py` | New folder-input default produces correct `SecondBrainFolder`. |
| Unit | `tests/unit/test_cli_overrides.py` | `--second-brain-folder add/list` flags. |
| Integration | `tests/integration/test_second_brain_e2e.py` | Render→load→write→read roundtrip, live render (no snapshot). |
| Snapshot | `tests/unit/test_render_snapshot.py` | `configure.md` dispatches to CLI subcommand. |
| Manual | — | `/hm:configure` UX walkthrough on current `.claude/harness.yaml`; expect folder prompt. |
| Manual | — | `/hm:research <topic>` on current state: expect Second Brain search returns [] with warning, no crash. |

# ⚠️ Risks & Mitigation

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Existing users with `folders: []` see degraded mode until `/hm:configure` is run. | low | ADR-008 logged warning + actionable error on write. README setup section. |
| R2 | `99_HM/{project_id}/` default may not suit all users. | low | Editable in interview; CLI flag for non-default; vault root left untouched. |
| R3 | Smart `.obsidian/` parent check may misclassify nested vaults (vault inside a vault). | low | Inspect immediate parent only; behavior documented in ADR-002 and SetUp doc. |
| R4 | Render-based e2e fragility. | low | Live render (ADR-005) — fragility = real signal. Override only the `second_brain` block. |
| R5 | Provenance-frontmatter contract is invisible to future contributors. | medium | Phase 1 adds `harness.yaml` row in CLAUDE.md parser-compat list with grep-able marker. |
| R6 | Staged migration of remaining 4 callers may stall indefinitely. | low | `docs/followups/io-utils-migration.md` + 4 source-comment markers ensure discoverability. |

# ✅ Success Criteria

- [x] `uv run python -m harness_maker.second_brain search 'test' --root /home/noel/harness-maker` runs without `yaml.YAMLError` (may return empty results — that is the degrade signal).
- [x] On the user's current `.claude/harness.yaml`, after running `/hm:configure` and adding a folder, `harness_maker.second_brain write` to `99_HM/harness-maker/test.md` produces a file under `/mnt/c/.../obsidian-vault/99_HM/harness-maker/test.md` that Obsidian indexes on next reload.
- [x] All 5 phases' exit criteria met.
- [x] Full `pytest` + `ruff` + `mypy --strict` pass.
- [x] CLAUDE.md parser-compat list mentions `harness.yaml`.
- [x] Follow-up tracker exists and lists 4 remaining callers.

# 🚫 Non-Goals

1. Migrating `verify.py`, `worktree.py`, `autoloop_driver.py`, `context_lint.py` to `load_harness_yaml()`. Tracked in `docs/followups/io-utils-migration.md` (ADR-007).
2. Hardening the wrapup write contract beyond Advisory. Locked by ADR-006.
3. Removing or gating `mkdir(parents=True, exist_ok=True)` in `write_note`. Locked by ADR-002 — intentional within configured folders.
4. Auto-seeding `folders` when missing. Locked by ADR-008 — graceful degrade only.
5. Re-architecting Second Brain to support non-filesystem backends (e.g., Notion, Logseq). Out of scope.

# 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION (8 warnings + 3 nits) → resolved.

| Critique | Severity | Resolution | Anchor |
|---|---|---|---|
| W1 — Auto-mkdir in write_note still creates phantom dirs | warning | Round 3 Q2 confirmed intent; documented in ADR-002 + Non-Goal #3. | Interview #10 |
| W2 — Backward-compat hard-error too aggressive | warning | Round 3 Q1: graceful degrade; ADR-008 added. | Interview #9 |
| W3 — Slash command can't conditionally branch on file state | warning | Phase 3 dispatch contract: slash → CLI → JSON → AskUserQuestion. | ADR-003 |
| W4 — Phase 1 exit criterion conflicts with Phase 3 enforcement | warning | Phase 1 exit re-scoped to loader-only (no CLI roundtrip). Rollback semantics made explicit. | Phase 1 §Exit |
| W5 — Staged migration has no tracker | warning | `docs/followups/io-utils-migration.md` + 4 source-comment markers; ADR-007. | Phase 1 §Scope |
| W6 — Provenance contract not documented for harness.yaml | warning | Moved CLAUDE.md edit into Phase 1; explicit grep exit. | Phase 1 §Exit |
| W7 — Phase 5 "docs reviewed" too vague | warning | Concrete grep + diff + pytest/ruff/mypy gates. | Phase 5 §Exit |
| W8 — Snapshot-pinning e2e defeats purpose | warning | Live-render only; ADR-005 explicit. | ADR-005 |
| W9 — ADR coverage gaps | warning | Split into ADR-003 + ADR-004 + ADR-007 + ADR-008 (8 total). | §ADRs |
| N1 — Line ranges rot | nit | Anchored by symbol name (`_load_config`, `_write_harness_yaml`) throughout §Scope. | All phases |
| N2 — No Non-Goals section | nit | Added §🚫 Non-Goals. | §Non-Goals |
| (skipped re-validation) | — | NEEDS_REVISION → revised in place per spec; MAJOR_REVISION would have re-run validator. | — |
