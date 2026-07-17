---
type: plan
task_slug: make-ux-gaps-2026-05
status: complete
created: 2026-05-10
tags: [harness-maker, plan, ux, install, interview, update, configure, uninstall]
research_doc: "[[RESEARCH-make-ux-gaps-2026-05]]"
interview_rounds: 3
adrs: 7
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "7-phase UX lift: fix broken update-ref, smart-defaults interview, new configs, preview, configure, uninstall"
---

# PLAN — make UX gaps: install, configure, update experience

## 🎯 Executive Summary

**What:** Seven sequential implementation phases that close every identified UX gap in the `/harness-maker:make` lifecycle — from first install through update, daily configure, and eventual removal.

**Why:** The core value proposition of harness-maker is "a harness tailored to *you* and *your project*." But today: (1) the update notification tells users to run a command that doesn't exist, (2) `/harness-maker:make` silently skips the interview (non-TTY detection), (3) no preview before install, (4) minimal post-install feedback, (5) no easy post-install reconfiguration, and (6) no clean removal path. The `commands/make.md` already has solid scaffolding — this plan extends it rather than rewrites.

**Key Decisions (ADR links):**
- ADR-001: Full scope P0~P3 (including uninstall)
- ADR-002: Smart defaults + mandatory confirm philosophy
- ADR-003: Confirm screen contents
- ADR-004: New interview questions (review focus, mechanical_checks, grade_threshold, domains+model)
- ADR-005: Individual CLI flags for extended interview answers
- ADR-006: `/hm:make` = `$ARGUMENTS`-based branching (default: re-render, `--reinterview`: full interview)
- ADR-007: Uninstall skips user-block files with warning

**Estimated impact:** Every harness-maker user who types `/harness-maker:make` will see a qualitatively different experience — they will feel the tool understood their project.

---

## 📚 Prior Work

- **RESEARCH-make-ux-gaps-2026-05**: 6 gaps identified; P0 (broken notification) confirmed broken in production.
- **RESEARCH-plugin-vs-generator-2026-05**: Settled that generator stays a generator. `/hm:configure` is a slash-command-driven targeted yaml edit + re-render, not a runtime config endpoint.
- **commands/make.md** (existing): Already has `STATE=fresh-install/re-render` branching, `--ci` shortcut, `--reinterview` shortcut, 4-dimension AskUserQuestion for Full reconfigure. This plan *extends* section 3 (fresh install) and adds sections.
- **[fail:design] return-type-change-breaks-callers**: grep ALL callers when changing any function signature in cli.py or models.py.
- **[wiki:architecture] generator-not-runtime-config**: hooks.json, settings.json, CLAUDE.md cannot be runtime-configured — only pre-rendered.

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note |
|---|-------|----------|----------|--------|------|
| 1 | Scope | Scope | P0~P3 or subset? | P0~P3 전체 (uninstall 포함) | → ADR-001 |
| 2 | Interview philosophy | Architecture | Smart defaults / Quick-Full / 8-question lift? | Smart defaults + mandatory confirm → 틀린 것만 조정 | No skip option; confirmation required → ADR-002 |
| 3 | Confirm screen items | Architecture | Which items on confirm screen? | profile+preset이유, 활성리뷰어, mechanical_checks감지, grade+auto_fix | → ADR-003 |
| 4 | New interview questions | Scope | Which new configs to add? | 리뷰포커스, mechanical_checks직접입력, grade threshold, domains+model | All 4 → ADR-004 |
| 5 | CLI handoff | Contract | How pass extended answers to CLI? | 개별 CLI 플래그 (--grade-threshold, etc.) | → ADR-005 |
| 6 | /hm:make role | Architecture | re-render only vs full interview vs ARGUMENTS-based? | $ARGUMENTS 분기 (기본 re-render, --reinterview → full) | → ADR-006 |
| 7 | Uninstall safety | Risk | User-block files on uninstall? | 경고 후 건너뜀 | → ADR-007 |

---

## 📐 Architecture Decision Records

### ADR-001: Full scope P0~P3 (uninstall included)
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** 6 UX gaps identified across P0-P3. P3 (uninstall) is technically independent but necessary for a complete plugin lifecycle.
**Decision:** All 6 gaps implemented in 7 sequential phases. Phases 1-3 = infrastructure; Phases 4-7 = user-visible features.
**Consequences:**
- ✅ Complete lifecycle coverage (install → update → configure → remove)
- ⚠️ Uninstall (Phase 7) has highest inherent risk due to file deletion logic
**Rejected alternatives:**
- P0+P1 only — Rejected: leaves preview/summary gaps; delight experience incomplete
- P0 only — Rejected: too narrow to ship as a version increment

---

### ADR-002: Smart defaults + mandatory confirm philosophy
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** `/harness-maker:make` currently silently uses autoloop defaults (non-TTY detection). The interview is the core UX.
**Decision:** The fresh-install path in `commands/make.md` section 3 is extended to: (1) run profile, (2) compute smart defaults, (3) show AskUserQuestion confirm screen with "looks right / adjust / full setup" — **confirmation is mandatory** (no skip-all option). The re-render path shows current settings and asks intent (this already exists in the command).
**Consequences:**
- ✅ Every first-time user sees and confirms their setup
- ✅ Tool demonstrates it read the project (stack, scale, etc.)
- ⚠️ Adds 1-2 extra AskUserQuestion calls to fresh install; acceptable trade-off
**Rejected alternatives:**
- Quick/Full 2-tier — Rejected: "skip" option undermines the "tool that gets you" value prop
- 8-question lift (same as current) — Rejected: abstract knobs, not intent-driven

---

### ADR-003: Smart defaults confirm screen contents
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** The confirm screen must show enough for the user to trust/verify, but not overwhelm.
**Decision:** Four items always shown on the confirm screen:
1. **profile + preset recommendation with reason** — e.g., "stack=Python+FastAPI, scale=medium, lifecycle=active → Production recommended"
2. **Active reviewer list** — which reviewers will run on each PR
3. **Detected mechanical_checks** — lint/type commands detected from pyproject.toml/Makefile
4. **grade threshold + auto_fix** — review strictness and auto-fix behavior
**Consequences:**
- ✅ User sees concrete impact before committing
- ✅ "Detected mechanical_checks" demonstrates project awareness
- ⚠️ profile.py must be extended to detect mechanical_checks (Phase 3)
**Rejected alternatives:**
- Full file list — Rejected: 40+ files is overwhelming for fresh install

---

### ADR-004: Four new interview questions added
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** The current interview asks only locale/targets/preset/dev_mode/workflows/consensus/caching/ref_folders. Several high-impact personalization dimensions are missing.
**Decision:** Four new dimensions added to `commands/make.md` Full reconfigure + shown on confirm screen:
1. **Review focus** — "What's your primary work on this project?" → maps to reviewer enablement via `--focus` CLI flag
2. **mechanical_checks** — direct input of lint/type commands
3. **grade threshold** — A/B/C explicit choice (currently hard-coded per preset)
4. **domains + recommended_model** — technology domains + Claude model preference

Mapping: `focus=security` → `--focus security` → `_apply_dimension_overrides` enables security-reviewer + security-auditor beyond preset defaults.

**Consequences:**
- ✅ Interview asks about intent (what are you doing?) not just abstract settings
- ✅ mechanical_checks question alone saves significant review time by catching trivial issues pre-LLM
- ⚠️ Adds ~4 AskUserQuestion calls to Full reconfigure; mitigated by Smart defaults confirm (most users won't hit Full reconfigure)
**Rejected alternatives:**
- Keep 8-question interview as-is — Rejected: misses the "감동" (delight) goal

---

### ADR-005: Individual CLI flags for extended interview answers
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** AskUserQuestion answers (grade_threshold, domains, mechanical_checks, etc.) must be passed from `commands/make.md` to the CLI without a TTY.
**Decision:** Add individual CLI flags to `harness-maker make`:
- `--grade-threshold=A|B|C`
- `--domains=python,react,tauri` (comma-separated)
- `--mechanical-checks='cmd1;cmd2'` (semicolon-separated list)
- `--recommended-model=opus|sonnet|haiku`
- `--focus=feature|bugfix|security|performance|refactoring`

All handled in `_apply_dimension_overrides`. `--focus` maps to additional reviewer enablement via `_focus_to_additional_reviewers()`.

**Consequences:**
- ✅ Explicit, testable, easy to document
- ✅ Composable: any flag can be passed from any caller
- ⚠️ 5 new flags added to cli.py make() signature; `_apply_dimension_overrides` grows
**Rejected alternatives:**
- JSON temp file — Rejected: more moving parts, cleanup complexity, harder to test
- Hybrid (flags + JSON) — Rejected: two mechanisms for same concern

---

### ADR-006: `/hm:make` = $ARGUMENTS-based branching
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** The drift notification references `/hm:make` (nonexistent). A new `/hm:make` command must be generated. Its scope needs definition.
**Decision:** `/hm:make` (generated in user's harness) is `$ARGUMENTS`-based:
- Default (no args) = `harness-maker make --update` (silent re-render with existing harness.yaml)
- `--reinterview` = routes to `/harness-maker:make` with note explaining the full reconfigure flow

Drift notification message updated to say: "Run `/hm:make` for a quick re-render, or `/harness-maker:make --reinterview` for full reconfigure."

**Consequences:**
- ✅ Single command user types after update notification; works immediately
- ✅ Covers "reinterview" path without duplicating the full interview logic
- ⚠️ Must document in `/hm:make` that it only re-renders (not re-interviews)
**Rejected alternatives:**
- `/hm:make` = full interview (duplicates /harness-maker:make) — Rejected
- `/hm:make` = re-render only with no `--reinterview` support — Rejected: user needs a path to full reconfigure from the project's commands

---

### ADR-007: Uninstall skips user-block files with warning
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** Files with `@hm:user:*` block markers contain mixed harness + user content. Deleting them loses user work.
**Decision:** `harness-maker remove` identifies harness-managed files via `generated_by: harness-maker` frontmatter. Files that additionally contain `@hm:user:` markers are **skipped** with a printed warning listing the path and a hint to manually delete after reviewing the content. `harness.yaml` is kept by default with a separate `--remove-yaml` flag to explicitly opt into removing it.
**Consequences:**
- ✅ Zero data loss risk; user blocks always preserved
- ⚠️ Uninstall is not always "clean" — some files may need manual deletion. Documented in warning message.
**Rejected alternatives:**
- Extract user blocks to separate file then delete — Rejected: extraction logic is complex and error-prone
- Ask per-file — Rejected: tedious for many files; preferred for zero-friction experience

---

## 🏗️ Technical Design

### Current State

`commands/make.md` (plugin-level slash command, `commands/` at repo root):
- State detection (fresh vs re-render)
- Re-render menu: Update / Switch IDE targets / Switch preset / Add component / Full reconfigure / Audit only
- Fresh install: 4-dimension AskUserQuestion → dispatch with `--preset`, `--locale`, `--dev-mode`, `--targets`
- **Gap**: no smart defaults confirm, no new dimensions (focus/grade/mechanical_checks/domains/model)

`src/harness_maker/cli.py` — `make()`:
- `_apply_dimension_overrides(answers, preset_override, locale_override, dev_mode_override, targets_override)`
- **Gap**: no flags for grade_threshold, domains, mechanical_checks, model, focus

`src/harness_maker/hooks/sessionstart_drift.py`:
- Emits `additionalContext` on version drift
- **Gap**: message references `/hm:make` which doesn't exist

`src/harness_maker/profile.py` — `ProjectProfile`:
- Detects stack, scale, lifecycle, existing_dotclaude, spec_only, vault_member
- **Gap**: no detected_checks field

### Affected Components

| Component | Phase | Change type |
|-----------|-------|-------------|
| `hooks/sessionstart_drift.py` | 1 | Fix string literal |
| `templates/commands/hm/make.md.j2` | 1 | New file |
| `synthesize.py` | 1, 6, 7 | Add 3 new file entries |
| `cli.py` | 2, 3, 5, 7 | New flags, profile subcommand, dry-run, remove subcommand |
| `profile.py` + `models.py` | 3 | detected_checks field |
| `commands/make.md` | 4 | Extend fresh-install section |
| `templates/commands/hm/configure.md.j2` | 6 | New file |
| `templates/commands/hm/uninstall.md.j2` | 7 | New file |

### Architecture — New Interview Flow in `commands/make.md`

```
/harness-maker:make (fresh install)
  │
  ├── 1. Detect state → fresh-install
  ├── 2. Run profile scan:
  │      ! python -m harness_maker.cli profile . --json
  ├── 3. Compute smart defaults:
  │      preset = heuristic(stack, scale, lifecycle)
  │      reviewer_list = preset_defaults(preset)
  │      detected_checks = profile.detected_checks
  │      grade_threshold = "A" if Production else "B"
  ├── 4. AskUserQuestion: "Smart defaults confirm"
  │      Shows: detected profile, preset+reason, reviewers, checks, grade
  │      Options: "Looks right" / "Adjust a few things" / "Full setup"
  ├── 5a. "Looks right" → dispatch with smart defaults
  ├── 5b. "Adjust" → targeted AskUserQuestion (which dimension?)
  │         → loop back to dispatch
  ├── 5c. "Full setup" → existing Full reconfigure path
  │         + NEW questions: focus, mechanical_checks, grade_threshold, domains, model
  ├── 6. Preview AskUserQuestion:
  │      "Will install N files. Key changes: [summary]. Proceed?"
  │      Options: "Proceed" / "Show full file list" / "Cancel"
  └── 7. Dispatch + summary
```

### Architecture — Focus → Reviewer Mapping

```python
# New in interview.py (or cli.py _apply_dimension_overrides)
_FOCUS_REVIEWERS: dict[str, list[str]] = {
    "feature":      ["code-reviewer", "ux-reviewer"],
    "bugfix":       ["code-reviewer", "test-reviewer"],
    "security":     ["code-reviewer", "security-reviewer", "security-auditor"],
    "performance":  ["code-reviewer", "performance-reviewer"],
    "refactoring":  ["code-reviewer", "concurrency-reviewer"],
}

def _focus_to_additional_reviewers(focus: str, preset: Preset) -> list[str]:
    """Return additional reviewers to enable beyond preset default."""
    wanted = set(_FOCUS_REVIEWERS.get(focus, ["code-reviewer"]))
    preset_defaults = set(_SIDE_ENABLED_REVIEWERS if preset == Preset.SIDE else _PROD_ENABLED_REVIEWERS)
    return sorted(wanted - preset_defaults)
```

### Architecture — Mechanical Checks Detection

```python
# New in profile.py
def _detect_mechanical_checks(project_dir: Path) -> list[str]:
    """Scan pyproject.toml [tool.ruff], [tool.mypy], Makefile for common check commands."""
    checks: list[str] = []
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        if "[tool.ruff]" in content:
            checks.append("uv run ruff check .")
        if "[tool.mypy]" in content or "mypy" in content:
            checks.append("uv run mypy .")
        if "pytest" in content:
            checks.append("uv run pytest --tb=short -q")
    makefile = project_dir / "Makefile"
    if makefile.exists():
        content = makefile.read_text()
        for line in content.splitlines():
            if line.strip().startswith(("lint:", "check:", "typecheck:", "test:")):
                target = line.split(":")[0].strip()
                checks.append(f"make {target}")
    return checks[:4]  # cap at 4 to avoid overwhelming
```

### Data Flow — CLI flag chain

```
commands/make.md (slash command)
  → AskUserQuestion collects: focus, grade_threshold, domains, mechanical_checks, model
  → Dispatch: harness-maker make <path>
      --focus=security
      --grade-threshold=A
      --domains=python,react
      --mechanical-checks='uv run ruff check .;uv run mypy .'
      --recommended-model=opus
  → cli.py _apply_dimension_overrides()
      → _focus_to_additional_reviewers(focus, preset)
      → answers.reviewers["enabled"] += additional
      → answers.grade_threshold = grade_threshold
      → answers.domains = parse(domains)
      → answers.mechanical_checks = parse(mechanical_checks)
      → answers.models["default"] = recommended_model
  → synthesize() → render()
```

### API Changes (new CLI flags)

```
harness-maker make [OPTIONS] [TARGET]

New flags:
  --grade-threshold TEXT   Review grade gate: A (strict) | B (moderate) | C (relaxed)
  --domains TEXT           Comma-separated domain packs: python, tauri, react, ...
  --mechanical-checks TEXT Semicolon-separated pre-review commands
  --recommended-model TEXT Claude model: opus | sonnet | haiku
  --focus TEXT             Primary work focus: feature|bugfix|security|performance|refactoring
  --dry-run                Print what would be installed; do not write files
```

New subcommand:
```
harness-maker remove [OPTIONS] [TARGET]
  --remove-yaml            Also remove harness.yaml (default: keep)
  --dry-run                Show what would be removed; do not delete
```

---

## 📝 Implementation Plan

### Phase 1 — P0 Fix: create /hm:make command + install manifest (Low risk)

**Validator critique resolved:** The existing `sessionstart_drift.py` message already says `/hm:make --update` (correct text). The breakage is that the referenced command does not exist as a generated file. Phase 1 does NOT change the message text; it creates the command.

**Scope (in):**
- `src/harness_maker/templates/commands/hm/make.md.j2` — new template implementing ADR-006: `$ARGUMENTS`-based branching (default: `harness-maker make --update`; `--reinterview`: routes to `/harness-maker:make`)
- `src/harness_maker/synthesize.py` — (a) add `make.md` to the generated file list; (b) write `.claude/.harness-manifest.json` after render (list of all file paths written — required for Phase 7 uninstall to identify frontmatter-less files like `settings.json`, `hooks/hooks.json`)
- `src/harness_maker/render.py` (or `cli.py`) — hook to write `.harness-manifest.json` containing `{"generated_by": "harness-maker", "version": "...", "files": [...]}` after render completes
- `tests/unit/test_synthesize.py` — verify `make.md` is in file list
- `tests/unit/test_cli.py` (new case) — `harness-maker make <tmp>` writes `.claude/.harness-manifest.json` with valid JSON
- Snapshot test regen

**Scope (out):** No sessionstart_drift.py changes. No CLI flag changes. No profile changes. No commands/make.md changes.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_synthesize.py -x
uv run pytest tests/unit/test_cli.py -k "manifest" -x
uv run pytest tests/ -k "snapshot" --tb=short  # new make.md snapshot must pass
# Manual: harness-maker make /tmp/test-project
#   → .claude/commands/hm/make.md exists
#   → .claude/.harness-manifest.json exists with valid JSON listing settings.json, hooks/hooks.json, etc.
```

**Risk:** Low — 1 string fix + 1 new template file + 1 synthesize.py file-list addition.

**Rollback point:** Before Phase 1 (git revert 3 files).

---

### Phase 2 — CLI flags extension (Low-Medium risk)

**Validator critiques resolved:**
- `--dry-run` moved to Phase 5 (avoids split between Phase 2 tests locking in an early format and Phase 5 format changes).
- Preset-rebuild interaction: when `--preset` changes, `_build_answers` rebuilds base answers. The `update` overlay in `_apply_dimension_overrides` must be applied AFTER the rebuild to restore all new flags. Exit criterion test explicitly verifies this.

**Scope (in):**
- `src/harness_maker/cli.py`:
  - Add `--grade-threshold`, `--domains`, `--mechanical-checks`, `--recommended-model`, `--focus` parameters to `make()` (all `str | None`)
  - Extend `_apply_dimension_overrides()` to handle all 5 new flags. **Critical ordering**: the `update` dict is built before the preset-rebuild branch; after the rebuild, re-apply `update` so extended flags survive a `--preset` change
  - Add `_focus_to_additional_reviewers(focus: str, preset: Preset) -> list[str]` function
- `src/harness_maker/interview.py` — add `_FOCUS_REVIEWERS` constant + export `_focus_to_additional_reviewers`
- `tests/unit/test_cli.py` — one test per new flag + one combo test: `make --preset=Production --grade-threshold=A --domains=python` → assert all three survive into rendered `harness.yaml`
- `tests/unit/test_interview.py` — test `_focus_to_additional_reviewers` for all 5 focus values

**Scope (out):** `--dry-run` is Phase 5. No template changes. No profile changes. No commands/make.md changes.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_cli.py -k "grade_threshold or domains or mechanical or focus" -x
uv run pytest tests/unit/test_cli.py -k "preset_plus_extended_flags" -x  # combo test
uv run pytest tests/unit/test_interview.py -k "focus" -x
uv run mypy src/harness_maker/cli.py src/harness_maker/interview.py --strict
```

**Risk:** Low-Medium — growing `_apply_dimension_overrides` increases cognitive load. Mitigation: keep each flag's handler to ≤5 lines; add docstring listing all flags' precedence order (CLI flag > harness.yaml > preset default).

**Rollback point:** Phase 1.

---

### Phase 3 — Profile extension: mechanical_checks detection (Low risk)

**Scope (in):**
- `src/harness_maker/models.py` — add `detected_checks: list[str] = Field(default_factory=list)` to `ProjectProfile`
- `src/harness_maker/profile.py` — add `_detect_mechanical_checks(project_dir)` function; call in `profile()`, assign to `ProjectProfile.detected_checks`
- CLI: add `profile` subcommand (read-only; prints JSON of ProjectProfile) so `commands/make.md` can call it to get detected_checks for the confirm screen
- `tests/unit/test_profile.py` — fixture projects with pyproject.toml/Makefile; assert correct detection

**Scope (out):** No CLI make() changes (Phase 2 added dry-run/flags; this adds profile subcommand). No template changes.

**Validator critique resolved:** `cli.py` is explicitly added to Phase 3 Affected Components (see table above). The `profile` subcommand contract is:
```
harness-maker profile <target> [--json]
```
`--json` prints `ProjectProfile.model_dump_json()` (one line); default prints human-readable summary. `commands/make.md` calls with `--json` to parse detected_checks, preset recommendation, stack, etc.

**Design note:** `profile <target> --json` is the data source for the Phase 4 smart defaults confirm screen. The subcommand must be stable before Phase 4 begins.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_profile.py -k "mechanical" -x
uv run python -m harness_maker.cli profile /tmp/python-project --json  # must output valid JSON
python3 -c "import json, sys; d=json.loads(sys.stdin.read()); assert 'detected_checks' in d" \
  <<< "$(uv run python -m harness_maker.cli profile /tmp/python-project --json)"
uv run mypy src/harness_maker/profile.py src/harness_maker/models.py src/harness_maker/cli.py --strict
```

**Risk:** Low — additive field to `ProjectProfile`. Existing code that constructs `ProjectProfile` without `detected_checks` still works (field has default_factory).

**Rollback point:** Phase 2.

---

### Phase 4 — `commands/make.md` rewrite: Smart defaults + new interview questions (Medium risk)

**Scope (in):**
- `commands/make.md` — extend section 3 (fresh-install) with:
  1. Call `profile` subcommand to get detected profile + detected_checks
  2. Compute smart defaults (preset recommendation + reason, reviewer list, grade_threshold, detected_checks)
  3. AskUserQuestion: "Smart defaults confirm" screen (ADR-003 contents)
  4. Branch: "Looks right" → dispatch / "Adjust" → targeted AskUserQuestion loop / "Full setup" → extended interview
  5. Extended Full setup: add 4 new AskUserQuestion calls (review focus, mechanical_checks, grade_threshold, domains+model)
  6. Preview AskUserQuestion before dispatch: "Will install N capabilities. Proceed?"
  7. Dispatch with all collected flags (Phase 2 new flags)
  8. Post-install: read summary from CLI stdout and present as "Quick start" with first command to try

**Scope (out):** The re-render branch (section 2 of commands/make.md) is left intact. No CLI changes. No template changes.

**Preview format decision:** Fresh install → "Will install 40+ files under .claude/. Key capabilities: [workflow list], [reviewer count] reviewers, [skill count] skills. Proceed?" Re-render → "Will update N files. Changes: X replaced, Y merged (user blocks preserved). Proceed?"

**Validator critiques resolved:**
- A snapshot test for `commands/make.md` is added to exit criterion (asserting Section 2 menu options are unchanged).
- The diff review step explicitly requires Section 2 to be untouched.

**Exit criterion (manual test — no e2e automation for slash commands):**
```
Run /harness-maker:make on a fresh Python project
  ✓ Smart defaults confirm screen appears
  ✓ Shows "stack=python → Production recommended" or correct inference
  ✓ "Adjust" branch works (can change grade_threshold without full interview)
  ✓ "Full setup" branch includes all 4 new questions
  ✓ Preview "N capabilities" AskUserQuestion appears before dispatch
  ✓ Post-install shows quick-start command
  ✓ All existing Section 2 options (Update / Switch IDE targets / Switch preset / Full reconfigure / Audit) still work
```

Document as `tests/cursor-compat/MANUAL_CHECKLIST_MAKE_UX.md`.

Additionally:
```bash
# Automated guard on Section 2 content
git diff commands/make.md | grep "^-" | grep -E "(Update|Switch IDE|Switch preset|Full reconfigure|Audit)" \
  && echo "ERROR: Section 2 menu options were removed — revert!" || echo "Section 2 intact"
# Snapshot test for commands/make.md (new):
uv run pytest tests/ -k "snapshot_make_command" --tb=short
```

**Risk:** Medium — largest prose change in this plan. Regression risk: existing re-render / Switch targets / Add component flows in section 2 must continue working. Mitigation: extend, not rewrite; section 2 is untouched.

**Rollback point:** Phase 3. (`git restore commands/make.md`)

---

### Phase 5 — Preview (dry-run) + post-install summary (Low risk)

**Validator critique resolved:** `--dry-run` is moved here from Phase 2. Phase 2 unit tests will assert string flags only; Phase 5 adds the `--dry-run` flag + format tests. No split.

**Scope (in):**
- `src/harness_maker/cli.py`:
  - Add `--dry-run` boolean flag to `make()`
  - `--dry-run` path: call `profile()` + `interview()` + `synthesize()` + `reconcile()` (same inputs as real install), then print category summary table (NEW: N, KEEP: M, MERGE: K, REPLACE: P), then `raise typer.Exit(0)` before any `render()` call
  - `_emit_install_summary(answers, bp, merge_reports, target_dotclaude)` — new function called after `render()`, prints: harness-maker version, slash commands available (from bp.files paths), active reviewers, active skills, preserved/merged counts, "quick start" next command
- `templates/commands/hm/make.md.j2` — add `--dry-run` usage hint in generated `/hm:make`
- `tests/unit/test_cli.py`:
  - `test_dry_run_writes_no_files` — assert exit 0, "NEW:" in output, no files written to tmp_path
  - `test_dry_run_format` — assert output contains "NEW:", "KEEP:", "MERGE:", "REPLACE:" substrings
  - `test_install_summary_contains_sections` — assert `_emit_install_summary` output contains slash-command list + "Reviewers active:" + "Quick start:"

**Scope (out):** No commands/make.md changes (Phase 4 handled the preview AskUserQuestion). This phase improves CLI-level output only.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_cli.py -k "dry_run or install_summary" -x
# Manual: harness-maker make /tmp/fresh-project --dry-run
# Expect: table showing NEW:/KEEP:/MERGE:/REPLACE: counts, no files written, exit 0
# Manual: harness-maker make /tmp/fresh-project
# Expect: _emit_install_summary at end with commands + reviewers list + quick-start
```

**Risk:** Low — additive output only. `_emit_install_summary` is called after all critical paths complete; failure is wrapped in broad except (matching `_emit_post_make_readiness` pattern).

**Rollback point:** Phase 4.

---

### Phase 6 — `/hm:configure` generated command (Low risk)

**Scope (in):**
- `src/harness_maker/templates/commands/hm/configure.md.j2` — new template:
  - AskUserQuestion: "What would you like to change?" (preset / reviewers / grade_threshold / dev_mode / targets / domains / mechanical_checks / model)
  - For each selection: targeted AskUserQuestion with current value shown
  - Dispatch: `harness-maker make <path> --<flag>=<new_value>` (using Phase 2 flags)
  - Confirmation that re-render completed
- `src/harness_maker/synthesize.py` — add `configure.md` to file list
- Snapshot test regen

**Scope (out):** No CLI changes needed (Phase 2 flags cover all selectable dimensions).

**Validator critique resolved:** `/hm:configure` dispatches with only the changed flag (e.g., `--grade-threshold=B`), which risks resetting other extended fields (domains, mechanical_checks) if `_apply_dimension_overrides` doesn't preserve unspecified fields. This is fixed by Phase 2's `update` overlay logic — unspecified flags remain `None` and `_apply_dimension_overrides` only overwrites fields whose flag is non-None. The Phase 6 exit criterion verifies this explicitly.

**Exit criterion:**
```bash
uv run pytest tests/ -k "snapshot" --tb=short  # snapshots must include configure.md
# After harness-maker make <project>, verify:
ls .claude/commands/hm/configure.md  # must exist
# Partial-override preservation test (manual):
#   1. make <project> --domains=python,react --mechanical-checks='ruff check .'
#   2. make <project> --grade-threshold=B  (no --domains, no --mechanical-checks)
#   3. Assert harness.yaml still has domains=[python,react] and mechanical_checks=['ruff check .']
# Automated version:
uv run pytest tests/unit/test_cli.py -k "partial_override_preserves_unchanged_fields" -x
```

**Risk:** Low — one new template file + one synthesize.py line. The command itself delegates to existing CLI flags.

**Rollback point:** Phase 5.

---

### Phase 7 — Uninstall: `harness-maker remove` + `/hm:uninstall` (Medium risk)

**Validator critique resolved:** `generated_by: harness-maker` frontmatter check alone misses frontmatter-less files (settings.json, hooks/hooks.json, .cursor/mcp.json). Phase 1 creates `.claude/.harness-manifest.json` listing ALL rendered file paths. Phase 7 reads this manifest as the authoritative file list for removal, falling back to `generated_by` frontmatter scan only for files not in the manifest (forward-compat). ADR-007 Consequences updated accordingly.

**Updated ADR-007 Consequences (addendum):**
- ⚠️ `generated_by` frontmatter alone is insufficient — settings.json, hooks/hooks.json, .cursor/mcp.json have no frontmatter. `.harness-manifest.json` (Phase 1) is the authoritative removal list.

**Scope (in):**
- `src/harness_maker/cli.py` — new `remove` subcommand:
  - Read `.claude/.harness-manifest.json` (Phase 1 output) to get authoritative file list
  - Fallback for files not in manifest: scan for `generated_by: harness-maker` frontmatter
  - Skip files containing `@hm:user:` markers (ADR-007); print warning listing skipped paths
  - Remove remaining managed files; rmdir empty directories
  - Handle `.cursor/` removal: if `harness.yaml` shows `cursor` in targets, include `.cursor/rules/harness.mdc`, `.cursor/commands/hm-*.md`, `.cursor/mcp.json` in removal list (from manifest or hard-coded for cursor-specific paths)
  - `harness.yaml`: keep by default; `--remove-yaml` flag to delete
  - `--dry-run`: print what would be removed, exit 0
  - Print summary: removed N files, skipped K (user blocks), kept harness.yaml
- `src/harness_maker/templates/commands/hm/uninstall.md.j2` — new template:
  - AskUserQuestion: "Remove harness-maker from this project?" with consequences listed
  - Optional: "Also remove harness.yaml? (keeps answers for future reinstall)"
  - Dispatch: `harness-maker remove <path>` [+ `--remove-yaml`]
  - Post: "Removal complete. To reinstall: /harness-maker:make"
- `src/harness_maker/synthesize.py` — add `uninstall.md` to file list
- `tests/unit/test_cli_remove.py` — unit tests for `remove` subcommand: managed-only files deleted, user-block files skipped, harness.yaml kept by default
- `tests/e2e/test_uninstall.py` — e2e: make → remove → verify clean state

**Scope (out):** `.worktrees/` directory is never touched by uninstall. User-authored agents/skills (not generated by harness-maker) are skipped (no `generated_by: harness-maker` frontmatter).

**Exit criterion:**
```bash
uv run pytest tests/unit/test_cli_remove.py -x
uv run pytest tests/e2e/test_uninstall.py -x
uv run mypy src/harness_maker/cli.py --strict
# Verify: after remove on a project with user blocks, user-block files remain
# Verify: harness.yaml still present after remove (without --remove-yaml)
# Verify: settings.json, hooks/hooks.json removed (frontmatter-less files via manifest)
uv run pytest tests/e2e/test_uninstall.py -k "frontmatter_less_files_removed" -x
```

**Risk:** Medium — file deletion is irreversible. Mitigations:
1. `generated_by: harness-maker` check before any delete
2. `@hm:user:` check before any delete of a marked file
3. `--dry-run` tested before actual removal
4. Unit tests use `tmp_path` (pytest fixture) → no real user files at risk

**Rollback point:** Phase 6.

---

## 🧪 Testing Strategy

### Unit tests (per phase)
- Phase 1: `tests/unit/test_sessionstart_drift.py` — new message text assertions
- Phase 2: `tests/unit/test_cli.py` — one parametrized test per new flag; `test_interview.py` for focus mapping
- Phase 3: `tests/unit/test_profile.py` — fixture pyproject.toml/Makefile → assert detected_checks
- Phase 5: `tests/unit/test_cli.py` — dry-run writes no files; install summary contains expected sections
- Phase 7: `tests/unit/test_cli_remove.py` — managed-file deletion, user-block skip, harness.yaml retention

### Snapshot tests
- Phase 1: `make.md` snapshot (new)
- Phase 6: `configure.md` snapshot (new)
- Phase 7: `uninstall.md` snapshot (new)
- Run `python tests/snapshot/regenerate.py` from **main repo root** (not worktree — see [fail:test] snapshot-regen-inside-worktree)

### Integration tests
- Phase 3: `INTEGRATION=1` test for profile() on real Python project
- Phase 5: CLI subprocess test for `--dry-run` mode

### Manual tests
- Phase 4: `tests/cursor-compat/MANUAL_CHECKLIST_MAKE_UX.md` (new) — 6 scenarios covering all branches of the new fresh-install flow

### What is NOT automated
- Phase 4: Full AskUserQuestion flow in `/harness-maker:make` — Claude Code slash command context cannot be automated; manual checklist only.

---

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Dry-run preview diverges from actual install (blueprint changes between preview and install) | Low | Medium | Dry-run calls `reconcile()` with same inputs as real install; no second call |
| `_apply_dimension_overrides` grows unwieldy (7+ params) | Medium | Low | Extract into `DimensionOverrides` dataclass in Phase 2 if >6 params |
| Snapshot tests fail when run in worktree | High (known) | Low | Always run `regenerate.py` from main repo root ([fail:test] snapshot-regen-inside-worktree) |
| `harness-maker remove` deletes a file without `generated_by` frontmatter (edge case: binary, empty, or pre-frontmatter file) | Low | High | Guard: only delete if frontmatter present AND contains `generated_by: harness-maker` exactly |
| Phase 4 commands/make.md rewrite breaks existing re-render / Switch targets flows | Medium | High | Preserve section 2 intact; only extend section 3; manual regression test each option |
| `--focus` reviewer mapping produces duplicate reviewers in `enabled` list | Low | Low | Use set arithmetic before appending to reviewers["enabled"] |

---

## ✅ Success Criteria

- [x] After plugin update, drift notification says "Run `/hm:make`" — command exists and works
- [x] `/harness-maker:make` on fresh project: smart defaults confirm screen appears with profile-derived reasoning
- [x] "Adjust" branch in confirm screen allows changing grade_threshold without full re-interview
- [x] Full setup includes: review focus → reviewer mapping, mechanical_checks input, grade threshold, domains+model
- [x] `--dry-run` prints manifest summary, writes no files, exits 0
- [x] Post-install summary: lists slash commands, active reviewers, quick-start command
- [x] `.claude/commands/hm/configure.md` present after `harness-maker make`; reconfigures correctly
- [x] `harness-maker remove --dry-run` prints removal manifest; `remove` deletes managed files, skips user-block files
- [x] `.claude/commands/hm/uninstall.md` present after `harness-maker make`; dispatches correctly
- [x] All existing behaviors (re-render / Switch targets / Add component / Audit) continue working in `commands/make.md`
- [x] `uv run mypy src/harness_maker/ --strict` passes
- [x] `uv run pytest tests/ -x` passes (all snapshots regenerated from main repo root)

---

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION_RESOLVED

Validator (plan-validator agent) returned NEEDS_REVISION with 7 warnings. All resolved in the plan above. No critical findings.

| Critique | Severity | Resolution |
|----------|----------|------------|
| Phase 1 over-states "fix message text" (message already correct) | warning | Removed "fix message text" from Phase 1 scope; Phase 1 = create command + manifest only |
| `--dry-run` split across Phase 2 and Phase 5 | warning | `--dry-run` moved entirely to Phase 5; Phase 2 = string flags only |
| Preset-rebuild + new flags interaction in `_apply_dimension_overrides` | warning | Explicit: re-apply `update` dict after preset-rebuild; combo test added to Phase 2 exit criterion |
| Phase 3 missing `cli.py` from Affected Components | warning | Added to table; `profile <target> --json` subcommand contract documented explicitly |
| Phase 7: `generated_by` frontmatter misses frontmatter-less files | warning | Phase 1 adds `.harness-manifest.json`; Phase 7 reads manifest as primary, frontmatter as fallback |
| Phase 4: no automated guard that Section 2 is untouched | warning | `git diff` check + snapshot test for commands/make.md added to Phase 4 exit criterion |
| Phase 6: partial-override may reset unchanged fields | warning | Verified by Phase 2 `_apply_dimension_overrides` logic (None flags = no-op); test added to Phase 6 exit criterion |

Post-resolution checklist:

| Check | Status |
|-------|--------|
| Every phase has scope/exit/risk/rollback | ✅ |
| No "Verify? / OK? / Accept?" phrasing | ✅ |
| ADR count (7) matches ## 📐 heading count | ✅ |
| Each architectural decision links to ADR | ✅ |
| Failure modes are concrete | ✅ |
| P0 regression (broken notification) is Phase 1 | ✅ |
| Highest-risk phase (7: uninstall) has the most detailed mitigation | ✅ |
| commands/make.md rewrite is extend-not-rewrite; automated guard added | ✅ |
| `.harness-manifest.json` covers frontmatter-less file removal | ✅ |
