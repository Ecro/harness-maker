---
type: plan
task_slug: plugin-vs-generator-2026-05
status: complete
created: 2026-05-09
tags: [harness-maker, architecture, generator, plugin, adr, upgrade-friction]
research_doc: "[[RESEARCH-plugin-vs-generator-2026-05]]"
interview_rounds: 3
adrs: 1
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Lock generator design via ADR-001; add --update flag to make upgrade re-render explicit"
---

# 🎯 Executive Summary

**What:** Two deliverables.

1. **ADR-001** — formally lock the generator design. Three file categories cannot be runtime-configured and require pre-rendering: hooks.json (schema incompatible between IDEs, consumed pre-LLM), settings.json (permission sandbox set pre-LLM), and CLAUDE.md (has a different reason: soft block via customization-block contract and content_hash reconciliation). Agents/skills/commands could theoretically be runtime-configured but trade-offs outweigh the benefit.

2. **`/hm:make --update` flag** — named alias for the current default silent re-render path (existing harness.yaml, no interview). Companion: update sessionstart_drift message to cite `--update` explicitly so users know exactly what command to run when drift is detected.

**Why now:** Research question ("is rendering needed if plugin reads harness.yaml at runtime?") revealed that rendering is partially irreducible (infra files) and the one genuine friction point — "remember to re-run /hm:make after upgrade" — is addressable with a named flag.

**Key discovery during research:** `sessionstart_drift.py` already fires on SessionStart and detects version drift. The gap is not detection but *named command to run*.

---

# 📚 Prior Work

- `RESEARCH-plugin-vs-generator-2026-05.md` — 5 binding constraints; concluded generator is correct; identified `--update` as the one missing feature
- `src/harness_maker/hooks/sessionstart_drift.py` — already wired to SessionStart; emits drift reminder via additionalContext
- `src/harness_maker/reconcile.py` — content_hash KEEP/REPLACE/MERGE_BLOCK already handles safe re-render

---

# 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note |
|---|-------|----------|----------|--------|------|
| 1 | Plan goal | Scope | ADR only, migration plan, or PoC? | ADR only + --update flag | No runtime-config migration |
| 2 | Pain point | Scope | Actual friction with generator? | upgrade → re-run /hm:make | SessionStart hook already detects drift but no named fix-command |
| 3 | Update scope | Scope | Include --update flag + auto-check? | Yes — hook already notifies, flag makes action explicit | Auto-render in hook = risky |
| V1 | --update contract | Architecture | What happens when --update + no harness.yaml? | Error out (my decision per autonomous protocol) | Falls-back-to-interview would make the flag semantically meaningless |

---

# 📐 Architecture Decision Records

### ADR-001: Generator pattern retained — three irreducible file categories prevent full runtime-config

**Status:** Accepted (2026-05-09, via /hm:plan interview)

**Context:** User asked whether harness.yaml runtime-config at invocation time could replace Jinja2 pre-rendering, eliminating the need to re-run `/hm:make` after upgrades. This was prompted by observing that agents could theoretically read harness.yaml and include domain standards dynamically.

**Decision:** Generator pattern is retained. File categories fall into two groups:

*Hard block (pre-LLM infrastructure, not debuggable via LLM reasoning):*
- `hooks.json` files — consumed by Claude Code / Cursor before any LLM invocation; schemas are IDE-specific and incompatible (PascalCase vs lowercase camelCase, empirically verified); no templating hook exists in either plugin system.
- `settings.json` — permission sandbox established by Claude Code before LLM runs; cannot be set by the LLM for itself.

*Soft block (technically injectable but contract-breaking):*
- `CLAUDE.md` — technically could be generic + reference harness.yaml via `@file` include, but doing so eliminates `<!-- @hm:user:* -->` merge blocks and content_hash-based KEEP/REPLACE/MERGE_BLOCK reconciliation. The entire user-customization-survival contract depends on the file being in the user's project with our frontmatter.

Since the three infrastructure files must be rendered regardless, keeping agents/skills/commands on the same generator path is net-positive (simpler mental model, zero extra tokens per invocation, user customization blocks work uniformly).

**Consequences:**
- ✅ Full personalization (domain injection, locale, preset, dual-IDE schema split) preserved
- ✅ `<!-- @hm:user:* -->` customization blocks survive upgrades via block_merge.py
- ✅ content_hash fingerprinting enables safe KEEP/REPLACE/MERGE across upgrades
- ⚠️ After harness-maker upgrade, `/hm:make --update` re-render is required — mitigated by SessionStart drift hook + the new `--update` flag (Phase 2)

**Rejected alternatives:**
- *Pure static plugin (agents/skills/commands live in plugin, not user project)* — Rejected: domain injection (`{% for d in config.project.domains %}`), locale variants, preset variants all require per-project render. User customization blocks impossible. Dual-IDE hooks infeasible.
- *Hybrid (thin user wrapper + base in plugin)* — Rejected: Claude Code has no cross-file include mechanism for agent `.md` files.
- *Partial runtime-config (agents/skills/commands at invocation, infra still rendered)* — Rejected: (a) agents reading harness.yaml + domain standard files on every invocation adds token overhead; (b) `<!-- @hm:user:* -->` blocks have no natural home if agent files don't live in user project; (c) content_hash reconciliation infra is still needed for the three hard-block files — the complexity delta is not eliminated.

**Source:** Interview #1–3, V1; Research `RESEARCH-plugin-vs-generator-2026-05.md`

---

# 🏗️ Technical Design

## Current State

- `sessionstart_drift.py`: fires on SessionStart, compares `harness_maker_version` in `harness.yaml` frontmatter to running `__version__`, emits `additionalContext` reminder. **The detection works; the named command to run is vague** ("Run /harness-maker:make").
- `/hm:make` default: already does silent re-render from existing `harness.yaml` (answers preserved via `answers_from_harness_yaml`), but this behavior has no explicit flag name. Users may hesitate ("will this trigger an interview?").

## Affected Components

| File | Change |
|------|--------|
| `src/harness_maker/cli.py` | Add `--update` flag; when set + harness.yaml present: skip interview (same as current default). When set + no harness.yaml: error exit with clear message. |
| `src/harness_maker/hooks/sessionstart_drift.py` | Update message to say "Run `/hm:make --update`" instead of generic re-render hint. |
| `work-docs/PLAN-plugin-vs-generator-2026-05.md` | This document (ADR-001 recorded here). |

## Non-Goals

- No `--dry-run` on `--update` (separate concern; tracked as future improvement if needed).
- No diff output from `--update` (reconcile already logs KEEP/REPLACE/MERGE; surfacing a full diff is separate UX work).
- No auto-invocation of re-render from the SessionStart hook (silent file writes from a hook = unexpected behavior, possible conflict with uncommitted edits).
- No change to `reconcile.py`, `render.py`, or `synthesize.py` logic (--update is a CLI-layer alias, not a new engine path).

## Flag Combination Table

| Flags | Behavior | Rationale |
|-------|----------|-----------|
| `--update` (harness.yaml present) | Silent re-render, no interview | ← target behavior |
| `--update` (no harness.yaml) | Exit non-zero with message "No harness.yaml found — run `/hm:make` (without --update) for initial setup" | Explicit error; fall-back-to-interview would make the flag meaningless |
| `--update --reinterview` | `--reinterview` wins; interview runs | `--reinterview` explicitly overrides silent mode |
| `--update --autoloop` | `--autoloop` wins; default-silent path (same as --update) | Both flags mean "no interview"; --autoloop is the CI variant |
| `--update --preset X` / `--locale X` / `--dev-mode X` / `--targets X` | Override applies, no interview | Overrides compose cleanly with silent re-render |

## Architecture / Data Flow (no change)

```
harness.yaml (existing) ──→ answers_from_harness_yaml() ──→ synthesize() ──→ reconcile() ──→ render()
```

`--update` is a CLI gate that (a) skips the `interview()` call and (b) routes to `answers_from_harness_yaml()` directly. This path already exists; the flag just gives it a name and makes the contract explicit.

---

# 📝 Implementation Plan

### Phase 1 — Add `--update` flag to CLI

**Scope in:** `src/harness_maker/cli.py`
- Add `update: bool = typer.Option(False, "--update", help="Re-render silently using existing harness.yaml answers (no interview). Errors if harness.yaml is absent.")`.
- When `--update` is set and `harness.yaml` is absent: `typer.echo("No .claude/harness.yaml found. Run harness-maker make (without --update) for initial setup.", err=True)` + `raise typer.Exit(1)`.
- When `--update` is set and `harness.yaml` present: proceed with `answers_from_harness_yaml()` (already the default path; flag makes it explicit).
- When `--update --reinterview` both set: respect `--reinterview` (log: "note: --reinterview overrides --update").

**Scope out:** reconcile.py, render.py, synthesize.py — no logic changes.

**Exit criterion:**
```bash
# Creates a throwaway project with harness.yaml present
uv run harness-maker make --update /tmp/hm-test-update  # exits 0 (re-renders silently)
uv run harness-maker make --update /tmp/hm-no-harness   # exits 1 with expected error message
uv run pytest tests/unit/test_cli.py -k "update" -x     # new unit tests pass
```

**Risk:** low (alias path, no engine change)
**Rollback:** revert cli.py; `--update` absent → behavior falls back to current default

### Phase 2 — Update sessionstart_drift message

**Scope in:** `src/harness_maker/hooks/sessionstart_drift.py` — change "Run /harness-maker:make to re-render" to "Run `/hm:make --update` for a silent re-render, or `/harness-maker:make` for a full interactive run."

**Scope out:** no logic change; drift detection unchanged.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_sessionstart_drift.py -x   # existing tests pass + message string updated
```

**Manual verification step:** Open a fresh Claude Code session in a project whose `harness.yaml` has a lower `harness_maker_version` than the running plugin. Verify Claude's first output mentions the drift message (or check `additionalContext` in session logs). — *Note: this is the medium risk. If additionalContext is not surfaced by Claude, the only fallback is `/hm:make`'s own startup output (Phase 3).*

**Risk:** low
**Rollback:** revert message string

### Phase 3 (conditional) — Surface drift warning in `/hm:make` startup output

**Trigger:** Only if Phase 2 manual verification shows additionalContext is NOT surfaced to users.

**Scope in:** `src/harness_maker/cli.py` `make()` — at startup, call `detect_version_drift()` and if drift found, `typer.echo(f"[harness-maker] ...")`.

**Exit criterion:** `uv run harness-maker make` in a drifted project prints the warning before proceeding.
**Risk:** low
**Rollback:** remove the startup echo

---

# 🧪 Testing Strategy

**Unit tests (new):**

| Test | What it asserts |
|------|-----------------|
| `test_cli.py::test_update_flag_with_harness_yaml` | `--update` runs without interview when harness.yaml present |
| `test_cli.py::test_update_flag_without_harness_yaml` | `--update` exits 1 with correct error message when harness.yaml absent |
| `test_cli.py::test_update_reinterview_precedence` | `--update --reinterview` runs interview (reinterview wins) |
| `test_cli.py::test_no_update_still_works` | Existing no-flag path still silently re-renders (regression guard) |
| `test_sessionstart_drift.py::test_message_contains_update_flag` | Updated message string present |

**Manual:**
- Open fresh Claude Code session in drifted project → verify drift message is surfaced in Claude's first turn output.

---

# ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `--update` vs `--reinterview` confusion | low | Help text explicit; flag combination table defines precedence; Phase 1 unit test covers |
| SessionStart additionalContext not visible to user | medium | Manual verification in Phase 2; fallback is Phase 3 (startup echo). If additionalContext is silent, Phase 3 activates. |
| `--update` accidentally becomes a required flag (no-flag path degraded) | low | Regression test `test_no_update_still_works` in Phase 1 |
| Flag combination edge cases (`--update --preset Production --locale en`) | low | Defined in combination table; overrides compose cleanly; no new code path for combinations |

---

# ✅ Success Criteria

- [x] ADR-001 written in this PLAN and cross-referenceable (task_slug in frontmatter)
- [x] `harness-maker make --update <path-with-harness-yaml>` exits 0, no interview prompt
- [x] `harness-maker make --update <path-without-harness-yaml>` exits 1 with clear message
- [x] `harness-maker make --update --reinterview` runs interview (--reinterview wins)
- [x] `harness-maker make` (no flag, harness.yaml present) still silently re-renders — no regression
- [x] sessionstart_drift message updated to cite `--update`
- [x] `uv run pytest tests/unit/ -x` passes after Phase 1 + 2

---

# 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION (8 warnings, 0 critical)

**Resolutions:**

| Warning | Resolution |
|---------|-----------|
| ADR-001 CLAUDE.md rationale conflated with hooks/settings | Split into "hard block" (hooks/settings, pre-LLM) vs "soft block" (CLAUDE.md, customization contract) — see ADR-001 Decision above |
| Missing 3rd rejected alternative (partial runtime-config) | Added explicitly with 3 concrete rejection reasons |
| Phase 2 --update contract undefined for missing harness.yaml | Decision: error out (flag is semantically meaningful only when harness.yaml exists) — see flag combination table |
| SessionStart hook visibility unverified | Phase 2 exit criterion adds explicit manual verification step; Phase 3 is the fallback |
| Flag combination ambiguity | Flag combination table added to Technical Design |
| Missing Non-Goals | Non-Goals section added |
| Phase 1 trivial exit criterion (grep tautology) | Phase 1 is now code-producing (CLI flag); exit criterion is bash + pytest commands |
| Test strategy gaps | 5 unit test cases + manual test row added |
