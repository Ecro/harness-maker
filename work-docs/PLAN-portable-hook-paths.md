---
type: plan
task_slug: portable-hook-paths
status: complete
created: 2026-07-21
tags: [harness-maker, plan, python, jinja2, hooks, portability, install-ref]
interview_rounds: 3
adrs: 5
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Make install_ref machine-portable ($HOME) so committed .claude hooks stop flip-flopping across a team"
---

# PLAN — Portable hook / command install paths ($HOME substitution)

## 🎯 Executive Summary

**TL;DR.** `_compute_install_ref()` bakes an absolute, home-dir-prefixed plugin-cache
path (`/home/<user>/.claude/plugins/cache/harness-maker/harness-maker/<ver>`) into every
rendered hook command **and** every slash-command / skill body. Teams commit
`.claude/settings.json`, so the absolute path is committed and re-written to each
developer's home on every re-render/rebase → an infinite flip-flop across a shared repo
(observed in `edge_testfarm_os` at 0.41.1, started at 87f8de3).

**Fix.** Substitute the render-machine's home-dir prefix with the literal `$HOME` at the
**source** (`_compute_install_ref`), so it propagates to all rendered surfaces. Switch the
hook-JSON `--with` from single quotes (which block shell expansion) to double quotes so the
IDE's shell expands `$HOME` at hook-execution time. The committed file becomes machine-
portable; the flip-flop path is structurally removed.

**Why / What.** Root cause is a single value used everywhere. Fixing at the source is the
minimal true fix (ADR-002). `$HOME` keeps using the local plugin cache — no network, exact
version match to the installed plugin (ADR-001).

**Key decisions.**
- ADR-001 — Portable form = `$HOME` prefix substitution (not PyPI pin, not settings.local split).
- ADR-002 — Fix at `_compute_install_ref` source; propagate to all surfaces.
- ADR-003 — Hook JSON `--with`: single→double quote. Command/skill bodies: unchanged (already unquoted, expands).
- ADR-004 — Keep `.claude/settings.json` committed (don't gitignore in consumers).
- ADR-005 — Render-time assert scoped to substitution-correctness; regression tests over a `/hm:health` check.

**Estimated impact.** 1 core function (`_compute_install_ref`), 3 live hook-JSON templates
(Production/Side settings, cursor, codex), `regenerate.py` pin, a render-time assert, a
migration doc + CHANGELOG, a 5-file version bump. Large snapshot regen (mechanical). No
behavior change for correctly-installed single-machine users; committed team repos become
portable on next re-render.

## 📚 Prior Work

- CLAUDE.md §버전업 정책 — install path lives in provenance; 5-file version sync required.
- `render.py` `_normalize_hm_managed_command` / `_merge_hooks_json` (ADR-001 of
  PLAN-hooks-merge-stale-path-dedup) — hook identity is already **path-agnostic** (keyed on
  the `python -m harness_maker.<invocation>` suffix). This is what makes the migration a pure
  re-render: a freshly-rendered portable entry has the SAME identity as the on-disk absolute
  entry, so the merge drops the old and keeps the new.
- `synthesize._compute_install_ref` history (0.15.1/0.15.3) — the `file://`-path branch was
  added precisely because plugin-marketplace installs resolve to the cache dir; that same
  branch is the source of the non-portable path.
- Prior commit `165feb99` ("autopilot guard no longer false-blocks the ~/.claude/plugins
  cache path") — same cache-path family, different symptom.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Portable-ref strategy | Contract | `$HOME` sub vs PyPI pin vs settings.local split | **$HOME substitution (keep local cache)** | No network, exact version; team must have plugin installed | ADR-001 |
| 2 | Plan scope | Scope | Renderer only vs renderer + consumer migration guide | **Renderer + migration guide** | User explicitly wants team-wide cleanup of edge_testfarm_os | ADR-004, Phase 4 |
| 3 | Target coverage | Scope | All 3 IDE hooks vs Claude only | **All three (Claude+Cursor+Codex)** | They share one `install_ref` | ADR-002, Phase 2 |
| 4 | Consumer commit policy | Contract | Keep settings.json committed vs gitignore it | **Keep committed (portable ⇒ safe)** | Sharing permissions/preset/hooks is valuable; no gitignore change | ADR-004 |
| 5 | Recurrence guard | Observability | /hm:health check vs render assert only | **Render assert + regression tests only** | health check deferred | ADR-005 |
| 6 | Fix location | Architecture | Source (install_ref) vs hook-3 only | **Source (install_ref)** | Propagates to command/skill bodies too; no latent bug | ADR-002 |

Interview closed at Round 3: zero high/medium architectural ambiguities remained; all slots
reached confidence ≥ τ.

## 📐 Architecture Decision Records

### ADR-001: `$HOME` prefix substitution as the portable form
**Status:** Accepted (2026-07-21, via /hm:plan interview)
**Context:** The committed install path's only machine-varying segment is the home-dir prefix.
**Decision:** Replace the render-machine's home prefix with the literal `$HOME`, keeping the
rest of the plugin-cache path. The IDE's shell expands `$HOME` at hook-execution time.
**Consequences:**
- ✅ No network dependency; exact version match to the locally installed plugin cache.
- ✅ Committed `.claude/settings.json` is machine-portable → flip-flop removed.
- ⚠️ Requires every teammate to have the plugin installed at the standard cache path
  (`$HOME/.claude/plugins/cache/...`). True for marketplace installs. Substitution keys on the
  **home prefix**, not the install kind: a dev-checkout that lives **under** home (e.g. the
  regen pin `/home/noel/harness-maker`) IS substituted; only a path **not** under the
  render-machine home (a system-wide `/opt/...` install) is left absolute — still works
  locally, legitimately non-portable.
**Rejected alternatives:**
- PyPI name+version pin (`--with harness-maker==<ver>`) — Rejected: adds a network/PyPI
  dependency and re-downloads a second copy though the plugin cache already has it.
- Split hooks into gitignored `settings.local.json` — Rejected: loses shared permissions/
  preset/hooks and regresses clone-to-working UX (teammates must re-render before hooks fire).
**Source:** Interview #1, #4

### ADR-002: Fix at the `_compute_install_ref` source, propagate to all surfaces
**Status:** Accepted (2026-07-21, via /hm:plan interview)
**Context:** `install_ref` is a single value fanned out to 3 hook files AND every slash-
command / skill body. Fixing only the hooks leaves the command bodies with the same latent
flip-flop if a team commits `.claude/commands/`.
**Decision:** Perform the substitution once, on the final computed raw ref inside
`_compute_install_ref` (covering **all** return branches — direct-URL, source-tree fallback,
and the parse-error fallback), so every consumer of `harness_maker_src_path` inherits the
portable value.
**Consequences:**
- ✅ One code site; all surfaces (hooks + commands + skills) become portable together.
- ⚠️ Nearly every rendered asset changes → large but mechanical snapshot regen.
**Rejected alternatives:**
- Per-template substitution in the 3 hook-JSON templates only — Rejected: leaves command/
  skill bodies non-portable (latent bug) and duplicates logic.
**Source:** Interview #3, #6; refined by codex second opinion (single-helper, all return paths).

### ADR-003: Standardize hook-JSON `--with` on double quotes; command/skill bodies stay unquoted
**Status:** Accepted (2026-07-21, via /hm:plan interview; **revised** post-validator)
**Context (actual per-template state — verified 2026-07-21, corrects the first draft):**
- `settings/Production.json.j2:71`, `settings/Side.json.j2:17` — **single-quoted**
  `--with '{{ harness_maker_src_path }}'` (single quotes block `$HOME` expansion).
- `cursor/hooks.json.j2:29`, `codex/hooks.json.j2:12` — **UNQUOTED**
  `--with {{ harness_maker_src_path }}` (already expands `$HOME`, but not space-safe).
- Command/skill `.md.j2` bodies — **unquoted**.
**Decision:** Standardize the `--with` argument across **all 4 live hook-JSON templates** on
**double quotes** (`--with "{{ harness_maker_src_path }}"`): settings go single→double;
cursor/codex go unquoted→double. Uniform, space-safe, and it makes the single Phase-2 exit
substring `"$HOME/` hold for every rendered hook. Cursor already double-quotes its
`CLAUDE_PROJECT_DIR`/`PATH` vars on the same line, so this matches the file's own style. Leave
command/skill bodies unquoted (`$HOME/...` expands under a shell; no spaces in Linux/WSL/macOS
home paths).
**Consequences:**
- ✅ All 4 hook files render an identical, space-safe, expanding form; one exit criterion covers all.
- ⚠️ A home path containing spaces (unusual; some Windows homes) would still break an unquoted
  command body — see Risk R2. Support scope for this fix is POSIX-shell runners.
**Rejected alternatives:**
- Leave cursor/codex unquoted and drop the leading `"` from the exit substring — Rejected:
  two rendered forms for the same concept, not space-safe, and a messier gate.
- Double-quote every command/skill body too — Deferred: large edit surface for a
  negligible-on-target-platforms gain; revisit if Windows support is prioritized.
**Source:** Interview #1; refined by codex second opinion (#7) and plan-validator (critical:
cursor/codex are unquoted, not single-quoted).

### ADR-004: Keep `.claude/settings.json` committed in consumer repos
**Status:** Accepted (2026-07-21, via /hm:plan interview)
**Context:** With `$HOME` the committed file is portable, so committing is now safe.
**Decision:** Do NOT add `.claude/settings.json` to `_HARNESS_GITIGNORE_PATTERNS`. The
migration guide's default recommendation is "re-render → commit once".
**Consequences:**
- ✅ Teams keep sharing permissions/preset/hooks; clone → hooks work immediately.
- ⚠️ A team that prefers per-machine config can gitignore it themselves (documented as the
  alternative, not the default).
**Rejected alternatives:**
- Ship a consumer gitignore rule for settings.json — Rejected: loses shared config,
  contradicts the recent "track config + memory tiers" gitignore direction.
**Source:** Interview #5 (commit policy)

### ADR-005: Render-time assert = render-machine-home leak check on `install_ref`
**Status:** Accepted (2026-07-21, via /hm:plan interview; **revised** post-validator)
**Context:** A guard is wanted to catch renderer regressions, but a naive "no absolute path"
assert would false-fire on legitimate non-home (system-wide) installs. The first draft
proposed a helper returning a `was_substitution_required` flag — but `regenerate.py:121`
monkeypatches `_compute_install_ref` **wholesale** (`lambda: _pinned`), so any helper-return
signal never exists during snapshot regen (validator W1).
**Decision:** Assert directly on the emitted `install_ref` string: it MUST NOT be, or start a
path-segment under, the **render-machine** home — `install_ref != str(Path.home())` and
`not install_ref.startswith(str(Path.home()) + os.sep)`. This is exactly the substitution-
correctness invariant (any home-prefixed ref must have become `$HOME/...`), needs no helper
flag, and holds under the regen monkeypatch (the pinned `$HOME/harness-maker` does not start
with the mocked home). A genuine non-home install (`/opt/...`) passes; a home-prefixed ref
that failed to substitute raises. It does NOT assert general portability.
**Consequences:**
- ✅ Catches the exact regression class (home prefix leaking) without penalizing non-home
  installs, and works identically in real render and in the regen harness.
- ⚠️ Does not catch runtime `$HOME`-non-expansion on a non-POSIX runner (see R1/R2) — that is
  covered by the Phase 4 manual smoke test, not the assert.
**Rejected alternatives:**
- Helper returns `was_required`, assert reads it — Rejected: dead under regen's wholesale
  monkeypatch (validator W1).
- `/hm:health` "non-portable path" finding now — Deferred (Interview #5).
- Assert "no `/home/` or `/Users/` substring in rendered hooks" — Rejected: false-fires on
  legitimate non-home installs.
**Source:** Interview #5; refined by codex second opinion (#6) and plan-validator (W1: the
render-machine-home leak check resolves both the assert and the regen path).

## 🏗️ Technical Design

### Current State
- `synthesize._compute_install_ref()` returns, in order: source-tree fallback
  (`_HARNESS_MAKER_PKG_ROOT`, line ~82), decoded `file://` path (line ~93), PyPI name
  `"harness-maker"` (line ~96), or the parse-error fallback (line ~95). The `file://` branch
  dominates for marketplace installs and yields the home-prefixed absolute path.
- 8 call sites pass the result to templates as `harness_maker_src_path`.
- Live hook-JSON templates (verified quoting differs — corrects first draft):
  `settings/Production.json.j2:71` + `settings/Side.json.j2:17` use **single quotes**
  `--with '{{ harness_maker_src_path }}'`; `cursor/hooks.json.j2:29` + `codex/hooks.json.j2:12`
  are **unquoted** `--with {{ harness_maker_src_path }}` (cursor's line already ships
  `PATH="$HOME/.local/bin:$PATH"`, proving Cursor expands `$HOME` in hooks on POSIX today).
- `templates/hooks/hooks.json.j2` is **NOT rendered to disk** (`synthesize.py:462`, ADR-005 of
  PLAN-permission-deny-and-hooks-wiring; its FileSpec was removed). It survives only as the
  byte-source for `render.render_stale_hooks_json_bytes()`, which `cli._retire_stale_hooks_json`
  uses to delete a stale `.claude/hooks/hooks.json` **when byte-pristine** (fail-safe: WARN +
  keep on mismatch). Because it is never rendered, ADR-003's quoting change does not touch it —
  the retire byte-match break in R3 comes from the `install_ref` path content changing, not quoting.
- Command/skill `.md.j2` bodies interpolate `harness_maker_src_path` unquoted.
- `tests/snapshot/regenerate.py` **monkeypatches** `_compute_install_ref = lambda: _pinned`
  (pinned to `/home/noel/harness-maker` or `$HM_REGEN_PIN`) while mocking `Path.home()` to a
  temp dir — so it bypasses substitution entirely today.

### Affected Components
- `src/harness_maker/synthesize.py` — `_compute_install_ref` + a new `_portablize_ref` helper.
- `src/harness_maker/templates/settings/{Production,Side}.json.j2`,
  `templates/cursor/hooks.json.j2`, `templates/codex/hooks.json.j2` — quoting.
- `src/harness_maker/render.py` — substitution-correctness assert in the hook-render path.
- `tests/snapshot/regenerate.py` — pin the portable (`$HOME/...`) form.
- Snapshot fixtures under `tests/` — regenerated.
- `cli._retire_stale_hooks_json` — verify behavior against new pristine bytes (R3).
- `CHANGELOG.md`, migration doc, 5 version files.

### Design Decisions (→ ADRs)
- Substitution helper `_portablize_ref(raw: str) -> str` (ADR-002): boundary-safe —
  substitute iff `raw == home or raw.startswith(home + os.sep)` (NOT a bare `startswith`,
  which would corrupt `/home/noel-other` → `$HOME-other`). Return `"$HOME" + raw[len(home):]`.
  Non-home paths and the PyPI name return unchanged. Applied to the final raw ref before
  `_compute_install_ref` returns, covering all branches.
- Quoting per ADR-003 (all 4 hook `--with` → double quotes).
- Assert per ADR-005 = render-machine-home leak check on the `install_ref` string (`install_ref
  != str(Path.home())` and `not install_ref.startswith(str(Path.home()) + os.sep)`); no helper flag.

### Data Flow
`_compute_install_ref()` → `_portablize_ref` → `install_ref` (`$HOME/...`) → `synthesize`
templates → `harness_maker_src_path` → hook JSON (double-quoted) + command bodies (unquoted)
→ rendered files → committed → IDE shell expands `$HOME` at hook run → `uv run --with
$HOME/.claude/plugins/cache/...`.

### API Changes
None external. Internal: new private helper `_portablize_ref`; `_compute_install_ref` return
value form changes (home paths now `$HOME`-prefixed).

## 📝 Implementation Plan

### Phase 1 — `$HOME` substitution in `_compute_install_ref`
- **depends_on:** []
- **parallel_group:** serial-core
- **merge_hazards:** `src/harness_maker/synthesize.py` (also touched by no other phase); none cross-phase.
- **Scope (in):** `synthesize.py` (add `_portablize_ref`, wire into `_compute_install_ref`
  final return covering all branches); `tests/unit/test_synthesize*.py` (new cases).
- **Scope (out):** templates, render assert, snapshots.
- **Exit criterion:** `uv run pytest tests/unit -k "install_ref or portablize"` green, with
  cases: home path → `$HOME/...`; `raw == home` exact; sibling `/home/<user>-other` NOT
  substituted; PyPI name `"harness-maker"` unchanged; non-home abs unchanged; `Path.home()`
  mocked in every case.
- **Risk:** low
- **Rollback point:** revert to pre-Phase-1 (no prior phase).

### Phase 2 — Hook-JSON quoting + render-time assert
- **depends_on:** [1]
- **parallel_group:** serial-core
- **merge_hazards:** shared templates (`settings/*.json.j2`, `cursor/hooks.json.j2`,
  `codex/hooks.json.j2`) and `render.py` — serialize after Phase 1.
- **Scope (in):** standardize the `--with` argument on **double quotes** in the 4 live hook
  templates, per their actual current state: `settings/Production.json.j2:71` +
  `settings/Side.json.j2:17` single→double; `cursor/hooks.json.j2:29` + `codex/hooks.json.j2:12`
  unquoted→double. Add the ADR-005 render-machine-home leak-check assert in the `render.py`
  hook-render path (raises iff emitted `install_ref == str(Path.home())` or startswith
  `str(Path.home()) + os.sep`).
- **Scope (out):** command/skill bodies (unchanged per ADR-003); `templates/hooks/hooks.json.j2`
  (not rendered — untouched; R3 owns its retire byte-match); snapshots (Phase 3).
- **Opportunistic (optional, while editing the cursor template):** sweep the pre-existing stale
  comment `cursor/hooks.json.j2:7` ("Claude Code reads .claude/hooks/hooks.json" — false per the
  2026-07-17 finding). Not introduced by this work; low-risk one-line doc fix if touching the file.
- **Exit criterion:** render a fixture harness to a temp dir; assert every HM hook command in
  `settings.json` / `.cursor/hooks.json` / `.codex/hooks.json` contains the exact substring
  `--with "$HOME/` and none contains the render-machine home prefix; the new assert unit-test
  both passes on portable input and RAISES on a synthetically home-leaked `install_ref`.
- **Risk:** medium (retirement byte-match — R3)
- **Rollback point:** Phase 1.

### Phase 3 — regenerate.py pin fix + snapshot regen + full gates
- **depends_on:** [1, 2]
- **parallel_group:** serial-core
- **merge_hazards:** the entire snapshot fixture tree — must be the sole in-flight writer.
- **Scope (in):** update `tests/snapshot/regenerate.py` so its pin yields the portable form
  (pin `_compute_install_ref` to return `"$HOME/harness-maker"`, i.e. the post-substitution
  canonical, so snapshots are deterministic and home-free); regenerate all snapshots; run full
  `uv run pytest`, `mypy --strict`, `ruff check` + `ruff format`.
- **Scope (out):** docs, version bump.
- **Exit criterion:** `uv run pytest` fully green (background); `mypy --strict` clean; `ruff`
  clean; snapshots are home-free — grep the render-machine home dynamically **and** match both
  `/home/` and `/Users/` (`grep -RE "/home/|/Users/|$HOME_LITERAL" tests/**/snapshots` finds no
  HM-hook install paths), so a macOS/CI leak (`/Users/...`) cannot slip through a `/home/`-only grep.
- **Risk:** medium (regen churn)
- **Rollback point:** Phase 2.

### Phase 4 — Migration guide + CHANGELOG + manual smoke test
- **depends_on:** [1, 2, 3]
- **parallel_group:** serial-docs
- **merge_hazards:** `CHANGELOG.md` (append-only), a new `docs/` migration note — none.
- **Scope (in):** write a consumer migration note (`docs/` or `work-docs/`) — for a repo like
  edge_testfarm_os: (1) `/plugin update` to the new version, (2) re-render via
  `/harness-maker:make --update`, (3) `git diff .claude/settings.json` now shows `$HOME`,
  (4) commit once, (5) teammates pull + `/plugin update` → works; include the root-cause "why"
  and the alternative gitignore option (ADR-004). CHANGELOG entry. **Manual smoke test**:
  re-render this repo, trigger a PostToolUse hook (a Write/Edit), confirm a
  `.claude/observability/*.jsonl` telemetry entry appears — proving `$HOME` expanded and uv
  resolved the cache path at runtime. **Record which target the smoke covered** (Claude Code /
  WSL-POSIX). The codex-rendered hook's runtime `$HOME` expansion is assumed-POSIX (the cursor
  `PATH="$HOME/..."` precedent proves Cursor, not Codex) — mark codex as an **explicitly-
  deferred** smoke target (within R1's accepted Medium scope), not silently covered.
- **Scope (out):** version bump (Phase 5).
- **Exit criterion:** migration note exists and states the re-render-auto-replaces-old-path
  fact; CHANGELOG updated; smoke test documented as PASS (hook fired, telemetry logged) in the
  PLAN/REVIEW trail.
- **Risk:** low
- **Rollback point:** Phase 3.

### Phase 5 — 5-file version bump
- **depends_on:** [4]
- **parallel_group:** serial-release
- **merge_hazards:** the 5 version files — atomic set.
- **Scope (in):** bump `0.41.1 → 0.42.0` across `.claude-plugin/plugin.json`,
  `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`,
  `src/harness_maker/__init__.py` (minor bump: rendered-path contract changed).
- **Exit criterion:** all 5 files report `0.42.0`; `uv run pytest -k version` (or the version-
  consistency test) green.
- **Risk:** low
- **Rollback point:** Phase 4.

## 🧪 Testing Strategy

- **Unit:** `_portablize_ref` — home-exact, home-subpath, sibling non-match
  (`/home/noel-other`), PyPI name, non-home abs, `HOME` mocked; the render-time assert both
  passes and raises.
- **Integration:** render a fixture harness; assert portable `"$HOME/` in all 3 live hook
  files and home-free command bodies; assert `_merge_hooks_json` replaces a seeded old
  absolute-path hook with the portable form (proves the migration claim).
- **Snapshot:** regenerated; determinism verified (home-free, `$HOME` literal).
- **Manual (Phase 4):** re-render → trigger hook → telemetry entry appears (runtime `$HOME`
  expansion proof). Records which target(s) the smoke covered (Claude Code / WSL POSIX shell).
- **Regression guard (R3):** a test asserting `_retire_stale_hooks_json` does not crash and
  fails safe (WARN + keep) when on-disk pristine bytes differ from the new render.

## ⚠️ Risks & Mitigation

| ID | Risk | Sev | Mitigation |
|----|------|-----|------------|
| R1 | `$HOME` not expanded because a hook runner isn't a POSIX shell — genuinely unknown only for **Windows cmd/PowerShell / direct-spawn** runners (codex #2, narrowed by validator W3) | Medium | Cursor-on-POSIX $HOME expansion is **already proven** by shipped `cursor/hooks.json.j2:29` (`PATH="$HOME/.local/bin:$PATH" uv run ...`) — not a new unknown. Scope this fix's portability claim to POSIX-shell runners (Linux/WSL/macOS — the team's env); Phase 4 smoke records the covered target. Windows cmd/PowerShell `$HOME` handling is explicit **out-of-scope / follow-up** in the migration doc; do NOT claim Windows portability. |
| R2 | Unquoted command/skill body + a home path with spaces (some Windows homes) breaks (codex #7) | Medium | ADR-003 scopes support to space-free POSIX homes; documented. Double-quoting command bodies is the deferred follow-up if Windows is prioritized. |
| R3 | Changing rendered bytes breaks `_retire_stale_hooks_json` pristine byte-match → upgraders keep a dead `.claude/hooks/hooks.json` + a WARN (codex #5) | Medium | Verify the retirement path fails safe (WARN + keep, no crash) against the new pristine bytes; add the R3 regression test; document the harmless one-time WARN + manual `rm .claude/hooks/hooks.json` in the migration note. (Full retirement of the dead file remains a separate future phase per CLAUDE.md.) |
| R4 | Bare `startswith(str(Path.home()))` corrupts a sibling path `/home/<user>-other` → `$HOME-other` (codex #3) | High | `_portablize_ref` uses boundary-safe `raw == home or raw.startswith(home + os.sep)`; explicit sibling-non-match unit test. |
| R5 | Substitution applied to only one return branch leaves source-checkout / parse-error fallbacks non-portable (codex #4) | Medium | Apply `_portablize_ref` to the final raw ref (all branches); unit tests for each branch. |
| R6 | `HOME` unset/overridden in the hook process at runtime → `$HOME/...` resolves wrong (codex #8) | Low | Out of practical range for IDE-launched hooks (HOME is always exported); Phase 4 smoke is the empirical backstop. |
| R7 | Snapshot regen non-determinism / developer-home leakage | Medium | regenerate.py pins the portable `$HOME/...` form; grep asserts home-free snapshots. |

## ✅ Success Criteria

- [x] `_portablize_ref` substitutes home-prefixed refs to `$HOME/...`, boundary-safe, all branches.
- [x] All 3 live hook files render `--with "$HOME/..."` (double-quoted, expands).
- [x] Command/skill bodies render `--with $HOME/...` (home-free).
- [x] Render-time assert raises on a home-leaked install_ref, passes on portable.
- [x] `_merge_hooks_json` replaces a seeded absolute-path hook with the portable form on re-render.
- [x] regenerate.py emits home-free snapshots; full pytest + mypy --strict + ruff green.
- [x] `_retire_stale_hooks_json` fails safe against new pristine bytes (no crash).
- [x] Migration note + CHANGELOG present; manual smoke (hook fires) recorded.
- [x] 5 version files at 0.42.0.

## 🔍 Plan Validation

- Cross-model second opinion (Production-mandatory): **codex — invoked** (8 findings, folded
  into ADR-001/002/005 refinements + R3/R4/R5 + Phase 1/3 tasks); **antigravity — failed**
  (returned no parseable JSON payload; ledgered `status: failed`, verdict is codex+Claude for
  this stage). See `.claude/observability/second-opinion.jsonl`.
- **plan-validator pass 1: MAJOR_REVISION** — 1 critical + 3 warnings + 2 suggestions, all
  verified against code and all resolved in this revision:
  - *Critical (Phase 2 premise wrong)*: cursor/codex hook templates are **unquoted**, not
    single-quoted → ADR-003 + Phase 2 rewritten to enumerate real per-template state and
    standardize all 4 on double quotes; exit criterion now `--with "$HOME/`.
  - *W1 (assert design dead under regen monkeypatch)*: ADR-005 switched to a direct
    render-machine-home leak check on `install_ref` (no helper flag).
  - *W2 (Current State said hooks/hooks.json.j2 "still rendered")*: corrected — it is not
    rendered, only the byte-source for the retire path.
  - *W3 (R1 overstated Cursor risk)*: narrowed to Windows-only; Cursor-POSIX $HOME proven by
    shipped template.
  - *Suggestions*: ADR-001 wording clarified (dev-checkout under home IS substituted); Phase 3
    grep now matches `/home/` + `/Users/` + dynamic home.
- **plan-validator pass 2: APPROVED** — all 5 pass-1 findings verified resolved against the
  code; no new critical introduced. Two non-blocking suggestions folded in: Phase 4 marks codex
  as an explicitly-deferred smoke target; Phase 2 optionally sweeps the pre-existing stale
  `cursor/hooks.json.j2:7` comment. Note: "4 live hook templates" (source) vs "3 live hook
  files" (output) is not a contradiction — Production/Side are mutually exclusive per preset.
  Cross-model second opinion echoed: codex invoked, antigravity failed.

## 🚦 Execution Status (/hm:execute)

All 5 phases DONE; changes staged on `hm/portable-hook-paths`, no commit (wrapup owns it).

| Phase | Status | Evidence |
|-------|--------|----------|
| 1 — `_portablize_ref` + wiring | ✅ done | `synthesize._portablize_ref` (boundary-safe) wraps every `_compute_install_ref` return; 14 `test_install_ref.py` tests green (incl. sibling non-match, home-exact, PyPI, non-home) |
| 2 — hook quoting + assert | ✅ done | 4 hook templates → double-quote `\"$HOME/...\"`; `render._assert_portable_install_ref` leak-check; `test_portable_hooks.py` (6 tests) renders all 3 IDE surfaces + asserts raise/pass |
| 3 — regen pin + snapshots + gates | ✅ done | `regenerate.py` + `conftest.py` pins → `$HOME/harness-maker`; 8 snapshots regenerated; full pytest + mypy --strict + ruff all green |
| 4 — migration + CHANGELOG + smoke | ✅ done | `docs/migration/portable-hook-paths.md`; CHANGELOG 0.42.0; smoke PASS — `sh -c 'uv run --with \"$HOME/harness-maker\" ...'` expanded `$HOME` + uv resolved + module loaded (Claude Code / WSL-POSIX; codex deferred per R1) |
| 5 — 5-file version bump | ✅ done | 0.41.1 → 0.42.0 across the 5 manifests/`pyproject`/`__init__`; version-sync tests green |

Deviations from PLAN: none material. Two existing `test_install_ref.py` fallback tests were
updated to expect the portablized form (the fallback branch is now portablized per ADR-002 —
intended behavior change, not scope creep). The stale `cursor/hooks.json.j2:7` comment was
swept (Phase 2 optional).
