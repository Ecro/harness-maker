---
type: plan
task_slug: help-command
status: execute-complete
created: 2026-05-21
tags: [harness-maker, plan, slash-command, ux, i18n, help]
interview_rounds: 2
adrs: 4
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Add /hm:help — locale-aware overview of available hm commands, fused workflows, and current harness settings"
---

## 🎯 Executive Summary

**TL;DR:** Add `/hm:help` — a static, locale-aware (en/ko) user-facing slash command that surfaces the full hm command catalogue, the recommended workflow path, and the user's current harness settings. No arguments; one screen; targets-driven cross-IDE blocks. Triple-IDE rendered (Claude Code + Cursor share `commands/hm/help.md`; Codex gets `.agents/skills/hm-help/SKILL.md` matching `/hm:loop`).

**Why:** Users (especially ko-locale) currently have no single entry point for command discovery — they must `ls .claude/commands/hm/`. The user explicitly asked for "locale 적용필수" + "보기 좋게" + "이해하기 쉽게" + "사용할 수 있는 커맨드 및 workflow 베이스". A static help template is the smallest change that meets all four constraints.

**Key Decisions:**
- [ADR-001](#adr-001-static-locale-templates) — Static `help.{ko,en}.md.j2` pair via `_localized()` (deterministic, no per-invocation LLM cost)
- [ADR-002](#adr-002-no-arguments--overview-only) — No arguments; overview-only
- [ADR-003](#adr-003-targets-driven-cross-ide-display) — `{% if "cursor"|"codex" in config.targets %}` Jinja conditionals
- [ADR-004](#adr-004-codex-dual-render-following-hmloop-pattern) — Codex dual-render via `.agents/skills/hm-help/SKILL.md` (matches `/hm:loop` precedent)

**Impact:** 3 new template files + 1 synthesize wiring change + snapshot regen (8 fixtures) + 1 unit test + 5-file patch bump (0.19.3 → 0.19.4).

---

## 📚 Prior Work

- `src/harness_maker/templates/claude-md/Side.{ko,en}.md.j2`, `templates/memory/{wiki,failures}.{ko,en}.md.j2` — existing static-locale pattern (the chosen precedent for ADR-001).
- `src/harness_maker/synthesize.py:368-380` — `_TEMPLATE_LOCALES = {"en", "ko"}` + `_localized()` helper. Unknown locales silently fall back to `en`.
- `src/harness_maker/synthesize.py:413-418` — `_base_files()` insertion point for meta commands (loop, health, make, configure, uninstall).
- `src/harness_maker/synthesize.py:540-544` — `_codex_target_files()` loop_skill dual-render — the canonical pattern ADR-004 follows.
- `src/harness_maker/templates/commands/hm/loop.md.j2:547` — canonical use of `config.workflows` (NOT `fused_workflows`) inside a Jinja template. The PLAN's validator caught `fused_workflows` as the wrong field name; HarnessConfig.workflows is the source of truth at render time.
- `templates/codex/loop_skill.md.j2` — Codex SKILL.md template the new `codex/help_skill.md.j2` mirrors.
- CHANGELOG.md — 0.19.0 was Node-pin (CI-only) yet marked minor; convention is mixed. User chose **patch** (0.19.4) for help-command per Round 2 #4 — additive, non-breaking, follows the smaller-change convention.

---

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | → ADR |
|---|-------|-------|----------|--------|-------|
| 1 | 1 | Locale rendering strategy | Architecture | Static `.ko`/`.en` template pair via `_localized()` | ADR-001 |
| 2 | 1 | Content scope | Scope | Medium — commands + workflows + current settings + next steps | (assumption documented) |
| 3 | 1 | Argument model | Contract | No arguments — overview only | ADR-002 |
| 4 | 1 | Cross-IDE display | Architecture | Targets-driven Jinja conditional | ADR-003 |
| 5 | 2 (post-validator) | Codex support | Architecture | Yes — dual-render via `.agents/skills/hm-help/SKILL.md` (mirror `/hm:loop`) | ADR-004 |
| 6 | 2 (post-validator) | Version bump severity | Release | Patch (0.19.4) | (Phase 5 scope) |
| 7 | 2 (post-validator) | Unsupported-locale notice | UX | End interview — silent fallback acceptable | (review-stage adjustable) |

---

## 📐 Architecture Decision Records

### ADR-001: Static locale templates

**Status:** Accepted (2026-05-21, via /hm:plan Round 1)
**Context:** Help text must reliably display in the user's configured locale. Codebase has two patterns: static `.{en|ko}.md.j2` pair (claude-md, memory/wiki, memory/failures) and runtime translation (configure.md.j2, loop.md.j2 — Claude translates `{{ config.locale }}` at invocation).
**Decision:** Use `_localized("commands/hm/help", locale)` mirroring `claude-md/Side.{ko,en}.md.j2`. Render at make-time, not at /hm:help invocation.
**Consequences:**
- ✅ Deterministic output, stable snapshots, zero per-invocation LLM cost.
- ✅ Consistent with the heaviest user-facing locale surfaces (CLAUDE.md, wiki, failures).
- ⚠️ Two template files (en/ko) to keep in sync when help text changes.
- ⚠️ Non-en/ko locales silently fall back to en (existing `_TEMPLATE_LOCALES` behavior; no new mitigation added — Round 2 #7 ended interview).
**Rejected alternatives:**
- Runtime translation — rejected: non-determinism conflicts with "locale 적용필수"; help text should not be re-translated on every invocation.
- Hybrid (locale skeleton + Jinja dynamic data) — rejected: dynamic data injection is already done via `config.*` Jinja in either approach; the locale axis itself does not need hybridization.
**Source:** Interview #1.

### ADR-002: No arguments — overview only

**Status:** Accepted (2026-05-21, via /hm:plan Round 1)
**Context:** Could support `/hm:help <topic>` (e.g. `commands|workflows|agents`) or `/hm:help <command_name>` for per-command details.
**Decision:** `/hm:help` takes no arguments and always renders the overview.
**Consequences:**
- ✅ Smallest possible surface; matches user's "너무 과하지 않게" constraint.
- ✅ Implementation: zero argument-parsing or dispatch logic.
- ⚠️ Per-command details require opening `.claude/commands/hm/<name>.md` directly.
- ✅ Future expansion to topic args is additive (non-breaking).
**Rejected alternatives:**
- Topic args — rejected: 4-5 topic-specific sections multiplies content surface.
- Command-name args — rejected: N (commands) × M (locales) maintenance burden.
**Source:** Interview #3.

### ADR-003: Targets-driven cross-IDE display

**Status:** Accepted (2026-05-21, via /hm:plan Round 1)
**Context:** `harness.yaml.targets` is multi-select of `claude-code | cursor | codex`. The help body must reflect what the user actually configured — a `[claude-code]`-only user should not see Codex `@hm-*` syntax.
**Decision:** Help template uses `{% if "cursor" in config.targets %}` / `{% if "codex" in config.targets %}` blocks. The command stub (`/hm:help` vs `@hm-help`) and IDE-specific notes appear only for configured targets.
**Consequences:**
- ✅ Output stays focused on what the user can actually use.
- ✅ Codex-only users see `@hm-*` syntax, not `/hm:*`.
- ⚠️ Snapshot tests must cover at least the claude-only and all-three permutations.
**Source:** Interview #4.

### ADR-004: Codex dual-render following /hm:loop pattern

**Status:** Accepted (2026-05-21, via /hm:plan Round 2 post-validator)
**Context:** Validator surfaced an inconsistency: ADR-003 advertises `@hm-help` to Codex-target users, but the meta-command pattern (configure/health/make/uninstall) renders ONLY to `commands/hm/*.md` (Claude/Cursor). `/hm:loop` is the sole exception with a Codex SKILL.md. Either help must also render to Codex, or the Codex Jinja block must be removed to avoid advertising a non-existent skill.
**Decision:** Render `/hm:help` to BOTH `.claude/commands/hm/help.md` AND `.agents/skills/hm-help/SKILL.md` (the latter only when `"codex" in config.targets`). The Codex SKILL.md uses a parallel `codex/help_skill.md.j2` template, mirroring `templates/codex/loop_skill.md.j2`.
**Consequences:**
- ✅ Codex users have parity for the help discovery surface.
- ✅ ADR-003's `@hm-help` advertising is now backed by a real skill file.
- ⚠️ Three template files (help.en.md.j2, help.ko.md.j2, codex/help_skill.md.j2) — keeping content parity across all three is a maintenance cost.
- ⚠️ Codex skill names use `hm-<name>` (hyphen, not slash). The Codex template body must use `@hm-help` syntax, not `/hm:help`.
**Rejected alternatives:**
- Skip Codex (follow configure/health/make/uninstall pattern) — rejected: a help/discovery surface has higher first-touch value than configure/health, so the user-side payoff of mirroring `/hm:loop` exceeds the maintenance cost.
- Codex Jinja block in claude-rendered help only (no SKILL.md) — rejected: advertises something users cannot invoke.
**Source:** Interview #5 (post-validator follow-up).

---

## 🏗️ Technical Design

### Current State

No `/hm:help` exists. Command discovery requires `ls .claude/commands/hm/`. The native Claude Code `/help` shows registered slash commands but does not group, prioritize, or surface the user's `default_workflow`.

### Affected Components

| File | Change | Reason |
|------|--------|--------|
| `src/harness_maker/templates/commands/hm/help.en.md.j2` | NEW | English help body (Claude Code + Cursor) |
| `src/harness_maker/templates/commands/hm/help.ko.md.j2` | NEW | Korean help body (Claude Code + Cursor) |
| `src/harness_maker/templates/codex/help_skill.md.j2` | NEW | Codex SKILL.md (locale-agnostic; falls back to English by Codex convention — matches `loop_skill.md.j2`) |
| `src/harness_maker/synthesize.py` | EDIT | Add `_localized("commands/hm/help", locale)` to `_base_files()` (~line 418) AND add Codex skill entry in the codex target block (mirror line 540-544 loop_skill) |
| `tests/snapshot/expected/*.yaml` | REGEN | 8 fixtures gain 1-2 file entries each (depending on whether the fixture's targets include codex) |
| `tests/unit/test_help_command.py` | NEW | 6 assertions (see Testing Strategy) |
| `pyproject.toml`, `src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json` | EDIT | Version bump 0.19.3 → 0.19.4 |
| `CHANGELOG.md` | EDIT | `[0.19.4]` entry |

### Jinja Context

The help templates receive the standard `config` dict (`HarnessConfig.model_dump(mode="json")`). They read:

- `config.locale` — echoed in current-settings block.
- `config.preset` — `Side` or `Production`.
- `config.targets` — drives `{% if "cursor" %}` / `{% if "codex" %}` blocks (per ADR-003).
- `config.default_workflow` — highlighted as "your default" in the workflows table.
- `config.workflows` — dict of `{workflow_name: [stages]}`. **NOTE (validator C1):** the field name is `workflows`, NOT `fused_workflows`. `fused_workflows` exists only on `InterviewAnswers`; at render time only `HarnessConfig.workflows` is in scope. The canonical precedent is `templates/commands/hm/loop.md.j2:547`.

### Content Shape (Medium)

Both en and ko templates share this skeleton (translated headers + prose):

```
# /hm:help — harness-maker {{ config.locale }}

> [1-line tagline]

## 📋 Available commands

### Atomic stages (7)
| command | purpose |
|---|---|
| /hm:research | 사전 조사 / research |
| /hm:spec      | 명세 작성 / spec |
| /hm:plan      | 구현 계획 / plan |
| /hm:execute   | 실행 / execute |
| /hm:review    | 검토 / review |
| /hm:wrapup    | 마무리 / wrapup |
| /hm:verify    | 검증 / verify |

### Fused workflows (현재 등록된 {{ config.workflows | length }}개)
{% for name, stages in config.workflows.items() %}
| /hm:{{ name }}{% if name == config.default_workflow %} ⭐ (your default){% endif %} | {{ stages | join(" → ") }} |
{% endfor %}

### Meta commands
| command | purpose |
|---|---|
| /hm:make      | 풀 재렌더 / full re-render |
| /hm:configure | 설정 변경 / targeted config change |
| /hm:health    | 3-layer audit |
| /hm:loop      | bounded autoloop |
| /hm:uninstall | 제거 / remove |
| /hm:help      | (this) |

## 🔁 추천 워크플로

  research ─► spec ─► plan ─► execute ─► review ─► wrapup
                                  │
                                  └─► verify (필요시)

your default:  /hm:{{ config.default_workflow }}

## ⚙️ Your current settings
- preset:           {{ config.preset }}
- locale:           {{ config.locale }}
- targets:          {{ config.targets | join(", ") }}
- default workflow: {{ config.default_workflow }}

{% if "cursor" in config.targets %}
> **Cursor:** `/hm:*` 동일 동작.
{% endif %}
{% if "codex" in config.targets %}
> **Codex CLI:** `@hm-*` 형식으로 호출 — `@hm-help`, `@hm-execute`, …
{% endif %}

## 💡 Next steps
- 처음이라면: `/hm:{{ config.default_workflow }}` 로 시작
- 설정 변경:  `/hm:configure`
- 건강도 점검: `/hm:health`
```

The Codex `help_skill.md.j2` uses the same skeleton but with `@hm-*` stubs throughout and SKILL.md frontmatter at the top (mirroring `loop_skill.md.j2`).

### Failure Modes Closed by This Design

- `config.workflows | length == 0` → "Fused workflows" table shows count 0 with no rows; section still renders (no Jinja crash).
- Unknown locale → `_localized()` returns `help.en.md.j2`; output is English (silent fallback per ADR-001 consequences; no notice — Round 2 #7).
- `config.targets == ["claude-code"]` → Cursor and Codex `{% if %}` blocks both skip; output focused on Claude Code only.
- `config.targets == ["codex"]` only → Claude Code blocks still render (the template body uses `/hm:*` as canonical); Codex section adds `@hm-*` note. This is acceptable since the user can read both — the canonical SKILL.md for the Codex-only user is the dual-rendered `.agents/skills/hm-help/SKILL.md`.

---

## 📝 Implementation Plan

### Phase 1 — Template authoring

**Scope (in):**
- Write `src/harness_maker/templates/commands/hm/help.en.md.j2`
- Write `src/harness_maker/templates/commands/hm/help.ko.md.j2`
- Write `src/harness_maker/templates/codex/help_skill.md.j2` (mirroring `templates/codex/loop_skill.md.j2`)

**Scope (out):** synthesize wiring; tests; version bump.

**Exit criterion (runnable):**
```bash
uv run python -c "
from jinja2 import Environment, FileSystemLoader, StrictUndefined
env = Environment(loader=FileSystemLoader('src/harness_maker/templates'), undefined=StrictUndefined)
ctx = {'config': {'preset': 'Production', 'locale': 'en', 'targets': ['claude-code', 'cursor', 'codex'], 'default_workflow': 'exec-rev-wrap', 'workflows': {'exec-rev-wrap': ['execute', 'review', 'wrapup']}}}
for tpl_path in ('commands/hm/help.en.md.j2', 'commands/hm/help.ko.md.j2', 'codex/help_skill.md.j2'):
    body = env.get_template(tpl_path).render(**ctx)
    assert len(body) > 100, tpl_path
    assert 'exec-rev-wrap' in body, tpl_path
print('OK')
"
```
prints `OK` (StrictUndefined catches the `fused_workflows` regression).

**Risk:** low (pure template authoring).
**Rollback point:** pre-PLAN main (no commits yet).

### Phase 2 — synthesize.py wiring

**Scope (in):**
- In `_base_files()` (synthesize.py, after the `uninstall.md.j2` line ~418), add: `(_localized("commands/hm/help", locale), "commands/hm/help.md", {})`.
- In the codex target block where `loop_skill` is added (~line 540-544), add a parallel entry: `("codex/help_skill.md.j2", ".agents/skills/hm-help/SKILL.md", {...standard codex context...})`.

**Scope (out):** snapshots; tests; version bump.

**Exit criterion (runnable):**
```bash
uv run python -c "
from harness_maker.synthesize import synthesize
from harness_maker.models import InterviewAnswers
ans = InterviewAnswers(locale='ko', targets=['claude-code', 'cursor', 'codex'])
files = synthesize(ans)
paths = [f.dst for f in files]
assert 'commands/hm/help.md' in paths, paths
assert '.agents/skills/hm-help/SKILL.md' in paths, paths
print('OK')
"
```
prints `OK`. Equivalent runs with `locale='en'` and `locale='ja'` (unknown → en fallback) must also pass.

**Risk:** low (additive change in two places that follow established patterns).
**Rollback point:** Phase 1 complete.

### Phase 3 — Snapshot regen + unit tests

**Scope (in):**
1. Run `uv run python tests/snapshot/regenerate.py` to refresh **all 8 expected.yaml fixtures** — adding `commands/hm/help.md` for every fixture and `.agents/skills/hm-help/SKILL.md` for any fixture whose `targets` includes codex.
2. Commit the 8 updated fixture files together with the template/wiring changes (so reviewer sees the snapshot delta atomically).
3. Add `tests/unit/test_help_command.py` with 6 assertions:
   - (a) `synthesize()` output contains `commands/hm/help.md` for `locale='en'` and `locale='ko'`.
   - (b) `locale='ko'` body contains the substring `사용 가능한` (or whichever specific Korean header lands in the .ko template).
   - (c) `locale='en'` body contains the substring `Available commands`.
   - (d) `targets=['claude-code']` body does NOT contain `@hm-` AND does NOT contain `> **Codex CLI:**`.
   - (e) `targets=['claude-code', 'codex']` body DOES contain `> **Codex CLI:**` AND `synthesize()` output DOES contain `.agents/skills/hm-help/SKILL.md`.
   - (f) For a fixture with `default_workflow='exec-rev-wrap-ver'`, the rendered help body contains exactly the substring `/hm:exec-rev-wrap-ver ⭐` (the star-marked default) — matches the fixture value byte-for-byte, not just "contains the workflow name somewhere".

**Scope (out):** version bump; manual e2e; release.

**Exit criterion (runnable):**
```bash
uv run pytest -q              # green
uv run mypy --strict src/     # green
uv run ruff check src/ tests/ # green
uv run ruff format --check .  # green
```
All four green. Run pytest in background per CLAUDE.md (full suite ~30-60s).

**Risk:** medium (snapshot churn affects 8 fixtures; missing the explicit `regenerate.py` step would surface as 8 confusing snapshot failures, which is why this step is now first in scope per validator W1).
**Rollback point:** Phase 2 complete.

### Phase 4 — Manual verification (file-content asserts + IDE manual check)

**Scope (in):**
1. **Automated file checks** (post `/hm:make --update`):
   - `test -f .claude/commands/hm/help.md` exits 0.
   - `test -f .agents/skills/hm-help/SKILL.md` exits 0 (current repo has `codex` in `harness.yaml.targets`).
   - `grep -q '사용 가능한' .claude/commands/hm/help.md` exits 0 (current repo has `locale: ko`).
   - `grep -q '> \*\*Cursor:\*\*' .claude/commands/hm/help.md` exits 0 (current repo targets include cursor).
   - `grep -q '> \*\*Codex CLI:\*\*' .claude/commands/hm/help.md` exits 0 (current repo targets include codex).
   - `grep -q '/hm:exec-rev-wrap-ver ⭐' .claude/commands/hm/help.md` exits 0 (current repo `default_workflow == exec-rev-wrap-ver`).
2. **Manual IDE check** (acknowledged non-automatable, per `tests/cursor-compat/MANUAL_CHECKLIST.md` convention):
   - Invoke `/hm:help` in a Claude Code session (this repo); verify the rendered output reads naturally in Korean and the tables align visually. If layout is broken, return to Phase 1.

**Scope (out):** release.

**Exit criterion (runnable):** all 6 automated checks above pass; manual IDE check noted as performed in PR description (no auto-pass).

**Risk:** low (read-only verification).
**Rollback point:** Phase 3 complete.

### Phase 5 — Release (5-file patch bump + CHANGELOG)

**Scope (in):**
- Bump version `0.19.3 → 0.19.4` in: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`.
- CHANGELOG.md: add `## [0.19.4]` section noting "Add `/hm:help` — locale-aware (en/ko) command + workflow overview. Triple-IDE rendered (Codex via `.agents/skills/hm-help/SKILL.md`)."
- **Semver rationale (validator W3):** patch chosen because the change is additive, non-breaking, and the new surface is a single read-only discovery command. The user explicitly chose patch in Round 2 #6 acknowledging the project's mixed semver history (0.19.0 was a CI-only minor; here we prefer the conservative reading).
- Commit with the conventional `chore(release): bump to 0.19.4` style; tag `v0.19.4` push; DO NOT manually `gh release create` (per CLAUDE.md release-procedure rule — release workflow auto-creates).

**Scope (out):** nothing.

**Exit criterion (runnable):**
```bash
grep -l '0\.19\.4' .claude-plugin/plugin.json .cursor-plugin/plugin.json .codex-plugin/plugin.json pyproject.toml src/harness_maker/__init__.py | wc -l
# expect: 5
grep -c '## \[0\.19\.4\]' CHANGELOG.md
# expect: 1
gh run list --workflow=release.yml --limit 1 --json status,conclusion -q '.[0].conclusion'
# expect: "success" (after tag push)
```

**Risk:** medium (release workflow can fail on quality-gate or boundary-parse advisory; per CLAUDE.md, on failure: diagnose via `gh run view --log-failed`, never bypass).
**Rollback point:** Phase 4 complete (no release yet).

---

## 🧪 Testing Strategy

- **Unit:** 6 assertions in `tests/unit/test_help_command.py` (enumerated in Phase 3).
- **Integration:** snapshot fixture regen covers full-stack synthesize output for all 8 preset/target combinations.
- **Manual:** Phase 4 automated grep checks (6) + 1 acknowledged manual IDE check.
- **LLM-mock:** not applicable — `/hm:help` is static rendered markdown with no LLM call in its execution path.
- **e2e:** Phase 4's `/hm:make --update` round-trip on this repo IS the e2e (per CLAUDE.md §8 "Integration 경계 한 줄 테스트" — user-facing slash commands need a real-render check beyond unit).

---

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| `config.workflows` vs `fused_workflows` regression in template | low (validator already caught) | high (silent empty table for all users) | Phase 1 exit uses `StrictUndefined` Jinja env to crash-fail on undefined; Phase 3 test (f) asserts exact substring presence. |
| Snapshot regen explodes (8 fixtures touch) | medium | low | Phase 3 names `regenerate.py` as the first step, before pytest, so the executor does not mistake fixture churn for a Phase 3 bug. |
| Korean ↔ English drift over time | medium | medium | CLAUDE.md to note "editing help.en.md.j2 must update help.ko.md.j2 in same commit"; reviewer prompt unchanged (general code-reviewer covers content parity). |
| Codex SKILL.md drift vs claude help.md content | medium | medium | All three templates share the structural skeleton; reviewer must check parity. Phase 1 exit renders all three templates together. |
| User's locale not in {en, ko} → silent English | low | low | Documented in ADR-001 consequences; not user-facing in `/hm:health` (no notice per Round 2 #7). |
| Release workflow fails on quality-gate | medium | medium | Phase 5 exit gates on `gh run` conclusion = success. Fix path: per CLAUDE.md, diagnose with `gh run view --log-failed`, never bypass. |
| `/hm:help` discovered too late to be useful | low | low | Optional README mention (out of scope here; if added, separate patch). |

---

## ✅ Success Criteria

- [ ] `.claude/commands/hm/help.md` is rendered after `/hm:make --update` (Phase 4 grep).
- [ ] `.agents/skills/hm-help/SKILL.md` is rendered for users whose `targets` includes `codex` (Phase 4 grep).
- [ ] Both `help.en.md.j2` and `help.ko.md.j2` pass Jinja render under StrictUndefined for all interview-decision combinations (Phase 1 exit).
- [ ] `_localized()` correctly picks `.ko` for `locale='ko'`, `.en` for `locale='en'`, `.en` for unknown locales (Phase 2 exit).
- [ ] Output respects `config.targets`: claude-only fixture has no Cursor/Codex blocks; targets-including-codex fixture has both (Phase 3 tests d/e).
- [ ] Default workflow is highlighted exactly (`/hm:<name> ⭐`) — fixture-exact substring assertion (Phase 3 test f).
- [ ] `uv run pytest`, `uv run mypy --strict src/`, `uv run ruff check src/ tests/`, `uv run ruff format --check .` all green (Phase 3 exit).
- [ ] Manual `/hm:help` invocation in Claude Code displays Korean (Phase 4 manual check; PR description acknowledges).
- [ ] 5-file version bump to 0.19.4 with `## [0.19.4]` CHANGELOG entry; release workflow conclusion = success (Phase 5 exit).

---

## 🔍 Plan Validation

**Outcome:** `NEEDS_REVISION_RESOLVED` — plan-validator (claude-sonnet-4-6) returned 1 critical + 5 warnings + 1 suggestion. All resolved before write:

| # | Severity | Finding | Resolution |
|---|---|---|---|
| C1 | critical | `config.fused_workflows` is not a HarnessConfig field — would Jinja-crash or silently render empty | Template uses `config.workflows` (matches `loop.md.j2:547`). Phase 1 exit uses `StrictUndefined` to catch any regression. |
| W1 | warning | Snapshot regen touches all 8 expected.yaml files; PLAN did not name `regenerate.py` step | Phase 3 names `regenerate.py` as step 1 of scope, explicitly. |
| W2 | warning | Codex meta-command skip is undefended given `/hm:loop` exception; could advertise non-existent `@hm-help` | Round 2 #5 → ADR-004 dual-renders to `.agents/skills/hm-help/SKILL.md`. |
| W3 | warning | Version bump severity not justified | Round 2 #6 → patch (0.19.4); Phase 5 scope adds the rationale. |
| W4 | warning | Phase 4 "manual invocation displays correctly" is subjective | Phase 4 replaced with 6 grep-based file-content assertions + 1 acknowledged manual IDE check (mirroring `MANUAL_CHECKLIST.md` convention). |
| W5 | warning | Unsupported-locale fallback notice strategy not stated | Round 2 #7 → end interview, silent fallback acceptable; ADR-001 consequences note no notice added. |
| S1 | suggestion | Test (f) `default_workflow string interpolated` vague | Phase 3 test (f) rewritten to assert exact substring `/hm:<default_workflow_value> ⭐` from fixture. |

## 🏃 Execute Stage Log (2026-05-21)

Worktree: `.worktrees/execute-20260521T0453Z`

| Phase | Status | Notes |
|---|---|---|
| 1 — Template authoring | ✅ done | help.en.md.j2 / help.ko.md.j2 / codex/help_skill.md.j2 written; StrictUndefined render passed all 12 ctx combinations. |
| 2 — synthesize wiring | ✅ done | `_base_files` gained `_localized("commands/hm/help", locale)`; `_codex_target_files` gained pre-rendered help_body + SKILL entry. |
| 3 — Snapshot regen + tests | ✅ done | 8 fixtures regenerated; `tests/unit/test_help_command.py` added (7 assertions, all green); 3 pre-existing count tests updated for new file count (test_codex_phase7 / test_synthesize / test_synthesize_codex). pytest + mypy --strict + ruff + ruff format all GREEN. |
| 4 — Manual verification | ✅ done (automated portion) | Phase 4's 6 grep checks all PASS against user's actual harness.yaml (locale=ko, targets=[claude-code, cursor, codex], default_workflow=exec-rev-wrap-ver). Manual IDE invocation acknowledged as non-automatable. |
| 5 — Release file edits | ✅ done (no commit/tag) | 5 version files at 0.19.4; CHANGELOG `[0.19.4]` entry added. **No commit, no tag** — `/hm:exec-rev` workflow has no wrapup; user invokes `/hm:wrapup` or commits manually. |

No git commit invoked from execute stage. PLAN file edit also uncommitted.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->

<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the plan stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
