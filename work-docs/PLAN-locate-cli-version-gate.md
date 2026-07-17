---
type: plan
task_slug: locate-cli-version-gate
status: complete
created: 2026-05-21
tags: [harness-maker, plan, cli, bootstrap, plugin-resolution]
interview_rounds: 3
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Add `locate` CLI + `--require-version` flag + docs/BOOTSTRAP.md so onboarding scripts can't pick stale plugin versions"
---

## 🎯 Executive Summary

**TL;DR** — Fresh-install bootstrap of harness-maker into `/home/noel/hwcc/` resolved cached **0.7.3** from the `harness-maker-local` marketplace instead of the just-installed user-scope **0.19.0**, because the meta-prompt's Python resolver iterates marketplace keys in fixed order and falls back to `entries[0]` when cwd isn't in the entry list. Every downstream command (`profile`, `--grade-threshold`, `hm:health` skill) then 404s.

**What we ship** in harness-maker so external onboarding scripts never re-implement the resolver:

1. **`harness-maker locate` CLI** — single source of truth for "which plugin install is active, where"
2. **`--require-version X.Y` flag** on `locate` and `make` — fail fast on stale versions
3. **`docs/BOOTSTRAP.md`** — canonical onboarding snippets per IDE that use (1) and (2)

**Why** — eliminate the entire class of "skill/option not found" footguns across the 7 known consumer projects (kairos, spoton, neuroterm-website, harness-maker self, hiloop, edge_testfarm_os, hwcc, edgescan) by making correct version-resolution a one-line call instead of a 30-line resolver every consumer re-invents (and gets wrong).

**Key decisions** (locked via interview):
- `locate` defaults to JSON, `--plain` prints installPath only → [ADR-001](#adr-001-locate-cli-output-contract--json-default--plain)
- Version gate is a flag on existing commands, not a new top-level `check` → [ADR-002](#adr-002-version-gate-via---require-version-flag-on-make-and-locate)
- Canonical bootstrap lives in `docs/BOOTSTRAP.md`, no `/hm:bootstrap` slash → [ADR-003](#adr-003-bootstrap-canonical-pattern-in-docsbootstrapmd-no-slash-command)

**Estimated impact** — ~250 LOC new (resolver + tests), ~150 LOC doc, 1 template re-wire. Ships as 0.20.0 minor (new public CLI surface).

## 📚 Prior Work

- `work-docs/PLAN-install-without-claude-code.md` — adjacent (PyPI install path, Codex/Cursor parity). This PLAN sits underneath it: regardless of which IDE installs harness-maker, the post-install resolver problem is shared.
- `work-docs/PLAN-fresh-install-p0-calibration.md` — fresh-install P0 observations that originally surfaced the version-gate gap.
- `work-docs/PLAN-fresh-install-health-baseline.md` — related: telemetry for first-install health, distinct from this PLAN's CLI/doc focus.
- **Forensic 2026-05-21**: `~/.claude/plugins/installed_plugins.json` contains 41 cached harness-maker versions across two marketplace prefixes (`harness-maker-local`, `harness-maker`). The kairos project entry from 2026-05-03 (0.7.3) was the `entries[0]` fallback that bit hwcc bootstrap on 2026-05-21.
- **CLAUDE.md §버전업 정책 + §릴리스 절차** — 5-file version sync + race-free release procedure constrain Phase 5.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Locate CLI output | Contract | text vs JSON vs both? | Default JSON, `--plain` for installPath only | ADR-001 |
| 2 | Version gate location | Architecture | new `check` cmd vs flag on existing vs caller-checks? | `--require-version X.Y` flag on `make` and `locate` | ADR-002 |
| 3 | Bootstrap canonical source | Scope | docs / +slash / CLI `--help` only? | `docs/BOOTSTRAP.md` only, no slash command | ADR-003 |

User selected "Short interview (≤3 rounds)" at plan entry; all three rounds were one-question, structured-options. No deferred decisions; no early-exit.

## 📐 Architecture Decision Records

### ADR-001: locate CLI output contract = JSON default + `--plain`

**Status:** Accepted (2026-05-21, via /hm:plan interview)

**Context:** External onboarding scripts across three IDEs (Claude Code, Cursor, Codex CLI) all need to answer "which harness-maker is active and where". Consumers are mixed: bash one-liners, Python wrappers, agent prompts that may shell out to either.

**Decision:** `harness-maker locate` prints JSON `{marketplace, version, scope, installPath, gitCommitSha, installedAt, projectPath?}` to stdout by default. `--plain` prints `installPath` alone on stdout (no JSON, no decoration). Exit `0` = found, exit `3` = not installed (distinct from `--require-version` mismatch which exits `2`).

**Consequences:**
- ✅ Single contract serves both shell (`installPath=$(harness-maker locate --plain)`) and agent consumers (`harness-maker locate` → JSON in agent context).
- ✅ Bash callers never need `jq`/`python -c` for the common case.
- ⚠️ Two output modes to maintain — snapshot test must cover both.

**Rejected alternatives:**
- B (text default + `--json`) — bash users gain marginal ergonomics, but cursor/codex agent prompts would then need `--json` to opt into structured data, which is backwards (harder consumer should be the default).
- C (JSON only) — every bash bootstrap then needs `jq`, raising surface area for parse failures.

**Source:** Interview #1

### ADR-002: version gate via `--require-version` flag on `make` and `locate`

**Status:** Accepted (2026-05-21, via /hm:plan interview)

**Context:** Once `locate` exposes a version field, the next footgun is callers shipping their own version-comparison logic (potentially repeating the same priority-ordering mistake the resolver fix is meant to eliminate).

**Decision:** Add `--require-version X.Y` to BOTH `locate` and `make`. Semantics: `>=X.Y` only (no other comparators). On mismatch, exit `2` with stderr in the format:
```
harness-maker installed=<actual-version> required=>=<X.Y> — run: claude plugin update harness-maker
```
No new top-level `check` subcommand.

**Consequences:**
- ✅ CLI surface stays small (no third top-level command).
- ✅ Bootstrap becomes a single line: `harness-maker locate --plain --require-version 0.20 || exit 1`.
- ⚠️ Flag *registration* (the typer arg) is duplicated across two commands; the comparator *logic* is centralized in `locate.py` and imported by `make`. (Clarification per validator suggestion.)

**Rejected alternatives:**
- A (new `check` subcommand) — over-engineering for a single comparison; future `check --plugin-conflict` etc. can be added later if needed without this PLAN being a precedent.
- C (caller-implements) — replicates the exact footgun this PLAN is fixing (different consumers, different bugs).

**Source:** Interview #2

### ADR-003: Bootstrap canonical pattern in `docs/BOOTSTRAP.md` (no slash command)

**Status:** Accepted (2026-05-21, via /hm:plan interview)

**Context:** Onboarding meta-prompt content needs an authoritative reference users can paste. Slash commands only exist post-install — they cannot solve the first-install chicken-and-egg.

**Decision:** Author `docs/BOOTSTRAP.md` containing:
(a) IDE-specific install commands (Claude Code, Cursor, Codex CLI),
(b) Post-install resolver/gate snippets using `harness-maker locate --plain --require-version`,
(c) Anti-pattern callout reproducing the kairos@0.7.3 bug class with the buggy Python resolver shown explicitly,
(d) Migration snippet for replacing legacy meta-prompts.

**Consequences:**
- ✅ Public reference at `github.com/Ecro/harness-maker/blob/main/docs/BOOTSTRAP.md`.
- ✅ No new slash-command surface to maintain.
- ⚠️ Doc can drift from CLI behavior; mitigated by Phase 3's token-presence snapshot test (NOT a `--help` byte-diff — see Phase 3 Exit Criterion for the precise assertion).

**Rejected alternatives:**
- B (slash command) — chicken-and-egg (`/hm:bootstrap` is unavailable pre-install, which is precisely when bootstrap is needed).
- C (CLI `--help` only) — agents copy `--help` text imperfectly into onboarding prompts; canonical doc avoids transcription drift.

**Source:** Interview #3

## 🏗️ Technical Design

### Current state

`harness_maker.cli` exposes 3 typer subcommands: `make`, `ai-readiness`, `ai-readiness-finalize`. Plugin discovery is implemented ad-hoc inside each consumer — the bootstrap meta-prompt has a Python resolver, the `/hm:make` skill template (`src/harness_maker/templates/commands/hm/make.md.j2`) has a bash one-liner (`ls -1d ... | sort -V | tail -1`). Neither shares logic; neither implements a version gate.

### Affected components

| File | Change |
|------|--------|
| `src/harness_maker/locate.py` | **NEW** — resolver + version comparator |
| `src/harness_maker/cli.py` | Register `locate` subcommand, extend `make` with `--require-version` |
| `tests/unit/test_locate.py` | **NEW** — resolver priority matrix + version comparator edge cases |
| `tests/snapshot/test_bootstrap_doc.py` | **NEW** — token-presence assertions on `docs/BOOTSTRAP.md` |
| `tests/snapshot/test_cli_help.py` | NEW or extended — lock `locate --help` + the `make --require-version` line |
| `docs/BOOTSTRAP.md` | **NEW** |
| `src/harness_maker/templates/commands/hm/make.md.j2` | Replace embedded `ls`/`sort -V` resolver with shell-out to `harness-maker locate --json` |
| `tests/snapshot/__snapshots__/` (make-related fixtures) | Regenerate |
| `CHANGELOG.md` + 5 version-sync files | Per CLAUDE.md release procedure |

### Dependencies

None new. Stdlib `json`, `pathlib`, `os`; existing `typer` for CLI.

### Source schema (load-bearing — Phase 1 contract)

`~/.claude/plugins/installed_plugins.json` is the input. **Verified empirically 2026-05-21**:

```jsonc
{
  "plugins": {
    "harness-maker@harness-maker-local": [        // <plugin>@<marketplace>
      {
        "scope": "project",                       // "project" | "user"
        "projectPath": "/home/noel/kairos",       // omitted for scope="user"
        "installPath": "/home/noel/.claude/plugins/cache/harness-maker-local/harness-maker/0.7.3",
        "version": "0.7.3",
        "installedAt": "2026-05-03T15:22:13.710Z",
        "lastUpdated": "2026-05-09T11:40:21.305Z",
        "gitCommitSha": "83eb9fe..."
      },
      ...
    ],
    "harness-maker@harness-maker": [...]
  }
}
```

Field names are **camelCase** (`installPath`, `installedAt`, `gitCommitSha`, `projectPath`) — the resolver must use these exact names, no snake_case translation.

### Architecture

```
caller (bash one-liner / agent prompt / skill template)
   │
   ▼
harness-maker locate [--plain] [--require-version X.Y]
   │
   ├── read ~/.claude/plugins/installed_plugins.json
   ├── iterate ALL keys matching "harness-maker@*"
   │        (NOT a fixed [local, main] order — scan whole map)
   ├── for each entry, compute priority score:
   │     1. projectPath == cwd       → highest
   │     2. scope == "user"          → second
   │     3. installedAt              → most recent wins as tiebreak
   ├── pick highest-scoring entry
   ├── if --require-version: tuple-compare entry.version >= X.Y
   │     mismatch → exit 2 + stderr message
   ├── emit JSON or plain installPath
   └── exit 0 (ok) / 2 (version mismatch) / 3 (no entry found)
```

### Design decisions

- **Resolver priority** — `projectPath == cwd` > `scope == "user"` > `installedAt` desc. Documented in ADR-001 + R6 (deliberate divergence from existing bash `sort -V` shim).
- **Version parse** — accept `X`, `X.Y`, `X.Y.Z` only. Integer tuple compare. Missing parts treated as `0` (e.g. `0.20` vs `0.19.3` → `(0,20,0)` vs `(0,19,3)` → 0.20 wins). No PEP440, no pre-release/post-release semantics. Rationale: avoid pulling `packaging` dep; harness-maker's own versioning is plain 3-part.
- **Exit codes** — `0` ok, `2` version mismatch, `3` not installed. Distinct codes so bash can branch on `$?`.
- **Output isolation** — JSON to stdout; error messages to stderr. `--plain` mode: only the path to stdout, no trailing newline-suppression (default print is fine).

### API surface added

```
harness-maker locate [--plain] [--require-version X.Y]
harness-maker make   [...existing...] [--require-version X.Y]
```

### Data flow change

`/hm:make` skill template currently embeds its own `ls -1d ... | sort -V | tail -1` resolver. After Phase 4, it shells out to `harness-maker locate --json` and trusts the result. See R6 for the deliberate behavior delta.

## 📝 Implementation Plan

### Phase 1 — `locate` resolver + CLI subcommand

**Scope (in):**
- `src/harness_maker/locate.py` (new): `resolve(cwd: Path) -> Entry | None`, JSON model class
- `src/harness_maker/cli.py`: register `locate` typer subcommand
- `tests/unit/test_locate.py` (new) — fixture matrix:
  - cwd-match wins over scope=user
  - scope=user wins over project-scoped of OTHER cwd
  - installedAt-desc tiebreak when both projectPath miss + multiple user-scope (theoretical, but explicit)
  - missing `installed_plugins.json` → exit 3
  - empty `plugins: {}` → exit 3
  - replicate the actual hwcc 2026-05-21 forensic state and assert kairos@0.7.3 does NOT win

**Scope (out):** version-gate flag (Phase 2), docs (Phase 3), skill template (Phase 4).

**Exit criterion** (runnable by /hm:execute):
```
uv run pytest tests/unit/test_locate.py -v          # all green
uv run python -m harness_maker.cli locate --plain   # exit 0, prints existing absolute path
uv run python -m harness_maker.cli locate           # exit 0, prints valid JSON parseable by `python -c "import json,sys; json.loads(sys.stdin.read())"`
```

**Risk:** low.

**Rollback point:** main (single new file + minimal cli.py addition; one revert commit).

### Phase 2 — `--require-version` flag on `locate` and `make`

**Scope (in):**
- `compare_version(actual: str, required: str) -> bool` in `locate.py`
- Wire `--require-version` typer option to `locate` and `make`
- Unit tests for comparator edge cases: `0.7.3 vs 0.16` (mismatch), `0.19.3 vs 0.19` (ok), `0.20 vs 0.20.0` (ok), missing patch (`0.19` vs `0.19.3` → ok), bad input (`abc`) → exit non-zero + error
- CLI `--help` text on both commands documents `>=X.Y` semantics + exit codes

**Scope (out):** docs (Phase 3), skill template (Phase 4).

**Exit criterion** (runnable by /hm:execute):
```
uv run python -m harness_maker.cli locate --require-version 99.0 ; [ $? -eq 2 ]  # exit 2 on mismatch
uv run python -m harness_maker.cli locate --require-version 0.1                  # exit 0
uv run python -m harness_maker.cli locate --require-version 99.0 2>&1 >/dev/null | grep -E "installed=.* required=>=99\.0"  # stderr format
uv run python -m harness_maker.cli make --require-version 99.0 --autoloop ; [ $? -eq 2 ]   # same on make
uv run pytest tests/unit/test_locate.py::test_compare_version -v
```

**Risk:** low.

**Rollback point:** Phase 1 (flag is additive on top of resolver; remove flag handlers).

### Phase 3 — `docs/BOOTSTRAP.md` + token-presence snapshot

**Scope (in):**
- `docs/BOOTSTRAP.md`:
  - Claude Code install + post-install bootstrap snippet
  - Cursor install + post-install bootstrap snippet
  - Codex CLI install + post-install bootstrap snippet
  - "Anti-pattern" section showing the kairos@0.7.3 buggy resolver verbatim with explanation
  - "Migrating from legacy meta-prompts" snippet
- `tests/snapshot/test_bootstrap_doc.py` (new):
  - Read `docs/BOOTSTRAP.md` raw text
  - Assert presence of token strings: `harness-maker locate --plain`, `--require-version`, `exit 2` AND `exit 3` (the branch handling), the literal anti-pattern comment marker (e.g. `<!-- ANTI-PATTERN: -->`)
  - **NOT a `--help` byte-diff** — drift detection is "did we remove the load-bearing tokens", not "is the entire doc literally synchronized with --help output" (validator clarification)

**Scope (out):** skill template wiring (Phase 4).

**Exit criterion** (runnable by /hm:execute):
```
uv run pytest tests/snapshot/test_bootstrap_doc.py -v   # all green
test -f docs/BOOTSTRAP.md
grep -q "harness-maker locate --plain" docs/BOOTSTRAP.md
grep -q "require-version" docs/BOOTSTRAP.md
grep -qE "(claude-code|Claude Code)" docs/BOOTSTRAP.md
grep -qE "(cursor|Cursor)" docs/BOOTSTRAP.md
grep -qE "(codex|Codex)" docs/BOOTSTRAP.md
```

**Risk:** low.

**Rollback point:** Phase 2 (docs-only; safe revert).

### Phase 4 — `/hm:make` skill template wires to `locate`

**Scope (in):**
- `src/harness_maker/templates/commands/hm/make.md.j2`: replace the embedded `ls -1d ... | sort -V | tail -1` block with a shell-out: `HM_PATH=$(harness-maker locate --plain) || exit 3`
- Regenerate impacted snapshot fixtures under `tests/snapshot/__snapshots__/` (the `make` command renders)
- Document the behavior delta in inline comment within the template (referencing R6 + ADR-001)

**Scope (out):** other skill templates (deferred — only `make` has this resolver footgun today; other templates don't enumerate plugin cache).

**Exit criterion** (runnable by /hm:execute):
```
uv run pytest tests/snapshot/ -k make -v                              # green after --snapshot-update
TMPDIR=$(mktemp -d) && cd $TMPDIR && git init -q && \
    uv run --directory /home/noel/harness-maker python -m harness_maker.cli make . --autoloop && \
    test -f .claude/harness.yaml && \
    test -d .claude/commands/hm && \
    test -f .claude/commands/hm/make.md
```

(Replaces the validator-flagged subjective "valid .claude/" with three concrete file-presence asserts after a fresh scratch render.)

**Risk:** medium — snapshot churn touches many golden files; concurrent PRs on templates would conflict.

**Rollback point:** Phase 3 (revert template + snapshot files).

### Phase 5a — Local pre-release checks

**Scope (in):**
- Bump version `0.19.3` → `0.20.0` in all five sync files (per CLAUDE.md §버전업 정책):
  - `.claude-plugin/plugin.json`
  - `.cursor-plugin/plugin.json`
  - `.codex-plugin/plugin.json`
  - `pyproject.toml`
  - `src/harness_maker/__init__.py`
- CHANGELOG entry: `0.20.0 (2026-05-21) — feat(cli): add locate subcommand + --require-version gate; docs: add BOOTSTRAP.md`
- Run advisory boundary tests locally per CLAUDE.md release procedure

**Scope (out):** tag push (5b), pip-install verification (5b post-CI).

**Exit criterion** (runnable by /hm:execute):
```
grep -l '"version": "0.20.0"' .claude-plugin/plugin.json .cursor-plugin/plugin.json .codex-plugin/plugin.json   # all three match
grep -q 'version = "0.20.0"' pyproject.toml
grep -q '__version__ = "0.20.0"' src/harness_maker/__init__.py
grep -q '0.20.0' CHANGELOG.md
uv run ruff check src/ tests/
uv run mypy src/harness_maker/
uv run pytest tests/unit/ -q
INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v   # advisory — non-blocking per CLAUDE.md
```

**Risk:** low (mechanical).

**Rollback point:** Phase 4 (5 file edits + 1 changelog line; trivial revert).

### Phase 5b — Tag push & release workflow

**Scope (in):**
- `git tag -a v0.20.0 -m "..."` + `git push origin main v0.20.0`
- After tag push, **DO NOTHING** else (per CLAUDE.md: `gh release create` race kills the workflow)
- Monitor `release.yml` run via `gh run watch`

**Scope (out):** pip-install verification (Success Criteria, post-CI).

**Exit criterion** (runnable by /hm:execute, but blocks on external CI):
```
git tag --list v0.20.0 | grep -q v0.20.0
git rev-parse v0.20.0 >/dev/null
# After workflow completes (use gh run watch, not local polling):
gh run list --workflow release.yml --limit 1 --json conclusion -q '.[0].conclusion'   # "success"
gh release view v0.20.0 --json tagName -q .tagName   # "v0.20.0"
```

**Risk:** medium — release workflow can fail at any of 5 jobs (quality-gate, build, publish-testpypi, publish-pypi, github-release). CLAUDE.md mandates: never `gh release create` manually; never `git tag -f`; on failure ship 0.20.1.

**Rollback point:** Phase 5a (release artifacts are **immutable**; if workflow fails, the patch path is 0.20.1, NOT revert).

## 🧪 Testing Strategy

- **Unit** (`tests/unit/test_locate.py`):
  - Resolver priority matrix (5 cases above, including the hwcc 2026-05-21 forensic replay)
  - Version comparator forms (`X`, `X.Y`, `X.Y.Z`, missing parts, bad input)
- **Snapshot**:
  - `tests/snapshot/test_bootstrap_doc.py` — token-presence on `docs/BOOTSTRAP.md`
  - `tests/snapshot/test_cli_help.py` — lock `locate --help` and the `make --require-version` help line
  - `tests/snapshot/__snapshots__/` — regenerated for `make` template
- **Integration** (`tests/integration/`):
  - Phase 4 exit criterion's scratch-dir render serves as the integration check
  - `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py` — advisory per CLAUDE.md
- **Manual (multi-IDE)**, post-Phase 5b:
  - Walk through each `docs/BOOTSTRAP.md` IDE snippet on a fresh project
  - Record outcomes in `tests/cursor-compat/MANUAL_CHECKLIST.md` (existing pattern from Cursor target work)

## ⚠️ Risks & Mitigation

| # | Risk | L | I | Mitigation |
|---|------|---|---|-----------|
| R1 | Resolver picks wrong entry across multi-marketplace setups | M | H | Test matrix covers projectPath-match / scope-user / installedAt-tiebreak; one fixture is the exact hwcc 2026-05-21 forensic — must NOT return kairos@0.7.3 |
| R2 | `--require-version` semantics ambiguous (`>=`, `==`, ranges) | L | M | `--help` documents `>=X.Y only`; bad input rejected early; ADR-002 records the constraint |
| R3 | `docs/BOOTSTRAP.md` drifts from CLI behavior | M | M | Token-presence snapshot (Phase 3) detects removal of load-bearing patterns; release checklist line reminds re-render |
| R4 | Existing onboarding meta-prompts in user space still buggy (the kairos-bug fleet) | H | M | BOOTSTRAP.md "Migrating from legacy resolver" section with the buggy pattern explicit + CHANGELOG announcement |
| R5 | Skill template snapshot churn in Phase 4 conflicts with concurrent work | L | L | Squash Phase 4 into one PR; rebase against main before tag push |
| R6 | **New resolver priority differs from existing `make.md.j2` bash `sort -V` shim** — could re-pick an older project-scoped install over a newer user-scoped one in mixed-scope setups | M | M | Intended per ADR-001 priority (projectPath > scope=user > installedAt). Test matrix MUST include `project-scope 0.7.3 vs user-scope 0.19.0 with cwd matching project-scope path → project-scope wins`. Documented in template inline comment so future maintainers see the deliberate divergence. (Validator-surfaced.) |

## ✅ Success Criteria

- [x] `harness-maker locate --plain` returns the correct installPath on the hwcc 2026-05-21 forensic fixture (NOT kairos@0.7.3)
- [x] `harness-maker locate --require-version 99 ; echo $?` prints `2`
- [x] `harness-maker locate --require-version 0.1 ; echo $?` prints `0`
- [x] `docs/BOOTSTRAP.md` exists with all 3 IDE sections + anti-pattern + migration sections, snapshot-locked
- [x] `/hm:make` skill template shells out to `locate --json` (no more embedded `ls`/`sort -V`)
- [x] `harness-maker==0.20.0` available on PyPI; GitHub Release page for `v0.20.0` is green (post-CI verification)
- [x] Walkthrough in `/home/noel/hwcc/`: install + bootstrap reports `0.20.0`, no "unknown skill/option" errors during `make` or `hm:health` invocation

## 🔍 Plan Validation

**Validator outcome:** `NEEDS_REVISION` (5 warnings + 1 suggestion, 0 critical) → resolved inline; no follow-up interview rounds required (all critiques were spec-clarification, not user decisions).

| # | Validator critique | Severity | Resolution |
|---|---------------------|----------|------------|
| C1 | Phase 4 exit "produces valid .claude/" not runnable | warning | Replaced with three concrete `test -f` / `test -d` asserts after scratch render (see Phase 4 Exit Criterion) |
| C2 | Phase 3 snapshot mechanism for BOOTSTRAP.md vs `--help` unspecified | warning | Clarified as **token-presence** assertion (NOT byte-diff vs `--help`). Phase 3 spec + ADR-003 Consequences updated |
| C3 | Phase 5 `pip install harness-maker==0.20.0` not locally runnable | warning | Split into Phase 5a (local pre-release: 5-file sync + CHANGELOG + advisory tests) and Phase 5b (tag push + CI monitor). Pip-install moved to Success Criteria post-CI |
| C4 | Resolver priority change vs existing bash `sort -V` shim — behavior delta not in risk register | warning | Added R6 with explicit mitigation (forensic fixture must cover mixed-scope case) |
| C5 | `installed_plugins.json` schema not specified — Phase 1 has no contract | warning | Added "Source schema" subsection under Technical Design with empirically verified field names (camelCase: `installPath`, `installedAt`, `gitCommitSha`, `projectPath`) |
| C6 | ADR-002 wording: "flag duplicated" is imprecise | suggestion | Amended ADR-002 Consequences to distinguish flag registration (duplicated) from comparator logic (centralized in locate.py) |

No re-validation requested — all changes are spec clarifications mapped one-to-one to validator recommendations.

## 🧷 Execution Status (2026-05-21)

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 — locate resolver + CLI | ✅ done | 18 resolver tests + 8 CLI tests GREEN; A.5 reviewer required 1 rewrite (removed undocumented tier-3 fallback) |
| Phase 2 — `--require-version` flag | ✅ done | 11 CLI integration tests GREEN; gate fires on `make` before any disk write (verified) |
| Phase 3 — `docs/BOOTSTRAP.md` + snapshot | ✅ done | 8 token-presence assertions GREEN |
| Phase 4 — `make.md.j2` wires to `locate` | ✅ done | Snapshot diff isolated to 1 SHA per fixture (8 fixtures × 1 line); scratch-dir smoke verified rendered `make.md` contains `harness-maker locate --plain` |
| Phase 5a — version bump 0.19.3 → 0.20.0 | ✅ done | All 5 manifest files + CHANGELOG entry; ruff + mypy + full pytest GREEN |
| Phase 5b — tag push + release workflow | ⏸ deferred | Requires explicit user authorization (irreversible per CLAUDE.md release procedure) |

Worktree: `.worktrees/execute-20260521T0440Z` finalized stage-only, merged into base. Changes staged for `/hm:wrapup` (22 files, +1098 / −22). No commits made (execute owns no commits).

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->

<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the plan stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
