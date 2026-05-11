# Changelog

## Unreleased

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
