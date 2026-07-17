---
type: research
task_slug: autopilot-invocation-and-marker-fix
status: complete
created: 2026-06-30
tags: [harness-maker, research, autopilot, templates, worktree, invocation-convention]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: []
summary: "Systemic: ~26 bare python/harness-maker invocations across templates; LLM has no canonical convention; marker worktree-invisible"
---

# RESEARCH — autopilot invocation & marker fix (systemic)

## 🎯 Recommended Direction

The `~/spoton` autopilot "fumbling" is a **symptom of a systemic invocation-convention
split**, not two isolated bugs. The templates emit harness-maker module calls in **two
incompatible conventions** that coexist with no enforced canonical form:

- ✅ **self-contained**: `uv run --with {{ harness_maker_src_path }} python -m harness_maker…`
  (used by `worktree_preflight`, `gate0_receipt`, `hooks.json`, `second_brain`,
  `memory_retrieve`, `spec_mutation`, `feedback_dispatcher`, `worktree-isolator`)
- ❌ **bare**: `python -m harness_maker…` / `harness-maker <subcmd>` (used by `autopilot`,
  `spec_need`, `spec_machine`, `two_pass_review`, `codex_adapter`, `drift_monitor`)

**Audit count: 26 broken executable lines** — 19 bare `!python -m harness_maker` + 7 bare
`Bash("python -m harness_maker…")`, plus the bare `harness-maker autopilot on` picker line.
In any environment without a `python` alias (WSL2: only `python3`/`uv`) or without
harness-maker pip-installed on PATH (every plugin-cache install, incl. spoton), **all 26
fail** exactly as the autopilot one did. The LLM cannot reliably self-correct because the
templates themselves disagree on the convention — it guesses, and the guess (hand-building
`uv run --with <cache>`) is what we observed.

**Recommended fix (maintainer-facing operability):**
1. Introduce ONE canonical Jinja macro/var (`{{ hm_py }}` = `uv run --with
   {{ harness_maker_src_path }} python -m harness_maker`) and migrate all 26 bare sites.
2. Add a **render-gate test** that fails CI if any rendered command emits a bare
   `python -m harness_maker` / `harness-maker <subcmd>` executable line (no-silent-miss
   discipline, mirrors `test_owned_uuids_render_gate`).
3. Add an authoritative **autopilot/marker reference** the LLM reads (marker location,
   session-scoped + 18h TTL, `autopilot_persistent`, worktree interaction).
4. Resolve the marker at the project/task root so the worktree auto-advance check sees it.
5. spoton config: `level: auto_safe` + `autopilot_persistent: true` + re-render.

## 🔍 Refinement Decisions

Discovery lens: Technical architecture / implementation (codebase-internal audit). The
audit (`grep` across `src/harness_maker/templates/`) is the primary evidence; counts are
reproducible: `grep -rn "!python -m harness_maker" … | grep -v "uv run" | wc -l` → 19.

## 🛠️ Approaches Found

### A1 — Single canonical invocation macro (RECOMMENDED)

| Field | Content |
|-------|---------|
| Approach | Define `{{ hm_py }}` (or a `hm_run()` macro) once; migrate all 26 bare sites to it |
| Assumption | `python -m harness_maker <subcmd>` == `harness-maker <subcmd>` (console entry) |
| Evidence | `__main__.py`→`cli:main`; `cli.py:2012 @app.command("autopilot")`. `harness_maker_src_path` already injected at `synthesize.py:170,552,557,563,635,779`. No macro exists yet — only the raw var. |
| Trade-off | Touches many templates → broad snapshot regen; longer command strings |
| Compatibility | Exact parity with the already-correct half of the templates |
| Risk | low (mechanical) — but the render-gate (A2) is what prevents re-introduction |

### A2 — Render-gate regression test

| Field | Content |
|-------|---------|
| Approach | A test that renders every command/skill and asserts no bare `python -m harness_maker` / `harness-maker <subcmd>` executable line survives |
| Assumption | The grep predicate can distinguish executable lines from prose mentions (`# comment`, table cells, code-fence explanations) |
| Evidence | CLAUDE.md cites `test_owned_uuids_render_gate` as the precedent producer-gate |
| Trade-off | Must allowlist legitimate prose mentions (codex toml comments `# harness-maker make`, `loop-p5-batch` doc table) — false-positive management |
| Compatibility | n/a (new test) |
| Risk | medium — the prose/executable discrimination is the hard part |

### A3 — Marker worktree-visibility (bug ④)

| Field | Content |
|-------|---------|
| Approach | Auto-advance boundary resolves the marker at the project root (walk up out of `.worktrees/<wt>/`), not worktree-relative `--root .` |
| Assumption | autoarm/picker write at main root; stages run in `.worktrees/<slug>/` |
| Evidence | `autopilot.py:59 marker_path=project_root/.claude/.hm-autopilot`; `autopilot_autoarm.py:75 arm_if_persistent(Path.cwd())`; `worktree.py:1043 _current_session_uuid` project-scoped (acknowledged limitation). |
| Trade-off | Resolver in `autopilot_caps` vs explicit `--root` in template; interacts with project-scoped session_uuid (worktree's differs → foreign reject) |
| Compatibility | Must not break standalone (non-worktree) runs nor cross-session uuid guard |
| Risk | medium |

### A4 — spoton config opt-in (consumer)

| Field | Content |
|-------|---------|
| Approach | spoton `harness.yaml.autonomy`: `level: auto_safe` + `autopilot_persistent: true` → `/harness-maker:make` |
| Evidence | `~/spoton/.claude/harness.yaml:155 level:"gated"`, `:160 autopilot_persistent:false`; `autopilot_autoarm.py:47,57` no-op on both |
| Trade-off | Config-only; does NOT fix the 26 bare sites until spoton re-renders to the patched version |
| Risk | low |

## ⚠️ Pitfalls

- **Config-only (A4) without source fix leaves all 26 sites broken** — persistence on
  still renders bare picker/advance/plan/wrapup calls. Source fix must land first.
- **Render-gate prose false-positives** — codex `config.toml.j2:9,37` / `agent.toml.j2:15`
  comments and `loop-p5-batch.md.j2:73` doc-table mention `harness-maker make` /
  `python -m …` as prose, not executable `!`/`Bash(...)` lines. The gate must target only
  executable forms or those mentions will block CI forever.
- **Marker root resolution (A3) interacts with project-scoped session_uuid** — copying the
  marker into a worktree is rejected (`active_marker` uuid mismatch); the resolver must
  READ from project root so the uuid matches.
- **spoton won't pick up the fix until re-render** to the patched harness-maker version
  (`/harness-maker:make`). Version-sync 5 files on release.
- **Broad snapshot regen** — migrating 26 sites changes every command/skill snapshot that
  includes them. Expect a large but mechanical diff.

## ❓ Open Questions

1. Macro shape: a bare-string var `{{ hm_py }}` (caller appends `.module subcmd …`) vs a
   `hm_run('module', 'args')` macro (encapsulates `-m harness_maker.<module>`)? The former
   is lower-churn; the latter is harder to misuse.
2. Render-gate discrimination: regex on `!`/`Bash(` executable lines only, with an explicit
   prose allowlist — or render-then-extract-bash-blocks? Which is maintainable?
3. A3 fix shape: resolver in `autopilot_caps` (robust to template drift) vs explicit
   project-root `--root` in the template (localized)?
4. Should the picker (`step_manifest`) also write the marker at project root so a
   worktree-run picker arms where the advance check reads?
5. Do A4 (spoton config) now, or hand to user? (User asked for all three → do it.)

## 📚 Sources

- (internal audit only — no external citations)
- Reproduction transcript: `~/spoton` session 2026-06-30 (`harness-maker: command not
  found`, `python: command not found`, marker in main not worktree)

## 🔗 Related Internal Docs

- PLAN-human-bottleneck-auto-advance (autopilot marker origin — `cli.py:2031`)
- PLAN-autopilot-config-surface (ADR-003 persistence — `autopilot_autoarm.py:9`)
- ADR-004 §2 dirname-embed UUID migration (deferred — `worktree.py` session_uuid limit)
- `test_owned_uuids_render_gate` (precedent producer-gate render test — CLAUDE.md)
