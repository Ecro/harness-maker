---
type: research
task_slug: test-fidelity-gap
status: complete
created: 2026-05-19
tags: [harness-maker, research, testing, prompt-engineering, qa-strategy]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://docs.anthropic.com/en/docs/build-with-claude/evaluation
  - https://docs.claude.com/en/docs/claude-code/cli-reference
related_docs:
  - "[[PLAN-llm-code-review-2026]]"
  - "[[PLAN-health-plugin-bugs-2026-05]]"
  - "[[PLAN-fresh-install-health-baseline]]"
  - "[[PLAN-second-brain-write-failure]]"
summary: "Tests miss because they verify rendered strings, not consumer-side parse + LLM execution. Close gap with 3 layers."
---

# RESEARCH — Test Fidelity Gap

## 🎯 Recommended Direction

**Close the "what Python sees" vs "what the consumer sees" gap with a three-layer defense, ordered by effort/payoff:**

1. **Layer 1 — Boundary-parse tests** (cheap, deterministic, CI-safe): for every rendered artifact, add a test that pipes the renderer output through the *real* consumer parser (`jq` on `hooks.json`, `tomllib` on Codex TOML, `yaml.safe_load_all` for harness.yaml, the bash command list for `lib/*.sh`, the Cursor `.mdc` frontmatter schema). This is the same pattern as `tests/integration/test_health_dashboard_roundtrip.py` — generalized across every parser/file pair.
2. **Layer 2 — Cross-template invariant lints** in `/hm:health` (already partly built): extend silent-miss detection (today: `communication_variant`) to the recurring drift classes — locale propagation, `work-docs/` literal path, `AskUserQuestion` gating on `--deep`, `is_codex` branch coverage, frontmatter key parity between source and rendered output.
3. **Layer 3 — Transcript canary suite** (one-time setup, LIVE-gated, runs weekly): handful of real `claude -p "/hm:<stage>"` invocations against `tests/e2e/sandbox-plugin-test/`, capture transcript, **LLM-judge** the transcript against a rubric ("Did Claude ask in Korean? Did it write to `work-docs/`? Did it stop after Phase 4?"). This is the only layer that catches Class 3 / 4 / 5 failures (LLM interpretation bugs).

**Main impact**: maintainer value — kills the recurring "tests green, user breaks" cycle that has produced ~30 fix-commits in the last 3 months. Indirectly user-facing because every undetected regression lands in a `/plugin update`.

This is informational. `/hm:plan` will lock the actual scope (most likely Layer 1 first as a single PR, with regression-fixture conventions).

## 🔍 Refinement Decisions

- `--deep` flag NOT set → Phase 0 / 0.5 interview skipped, dove straight into Phase 1.
- **Discovery lenses**: (1) Technical architecture — current test layer coverage in `tests/{unit,integration,e2e,snapshot}/`; (2) Risk / compliance — recurring failure classes in `.claude/memory/failures.md` and recent `fix(...)` commits as ground truth for "what real users hit." Skipped User-workflow discovery: the question is internal-maintainer process, not user-facing value (so the Phase 1 discovery guard does not apply).

## 🛠️ Approaches Found

### Approach A — Boundary-parse tests (round-trip contract testing)

| Field | Content |
|-------|---------|
| Assumption | Every rendered file is consumed by a non-Python parser; if Python and the parser disagree, the artifact is broken. |
| Evidence | `[wiki:pattern] round-trip-contract-test-floor-plus-equality` (already used for `ai_readiness → dashboard`). Recent precedent fixes: `yaml-colon-in-unquoted-frontmatter-description` (Codex couldn't read it, Python could); `toml-section-header-variable-injection` (Python `tomllib` accepts it but key-shape is wrong); `phantom-key-on-rerender-breaks-idempotency` (caught by `tests/integration/test_fresh_install_readiness.py::test_render_idempotent_byte_identical` — proves the pattern works). |
| Trade-off | Each new file type needs one extra parser-roundtrip test (~10-20 LoC). Cheap. Snapshot tests stay; this just sits next to them. |
| Compatibility | Drop-in next to `tests/integration/`. Already 7 files there; this approach just extends the pattern. |
| Risk | low |

### Approach B — Cross-template invariant lints in `/hm:health`

| Field | Content |
|-------|---------|
| Assumption | Drift between source template and rendered output is the dominant Class 3 failure mode (silent-miss). LLM-judgment is overkill — most drifts are deterministic string/regex patterns. |
| Evidence | The `communication_variant` silent-miss check is already implemented (`render._extract_source_communication_variant`, `/hm:health` Layer 1 `communication_protocol` sub-check). `[fail:design] yaml-key-value-name-mismatch-llm-footgun` produced a two-layer guardrail (Layer 1 prevention warning in 4 stage templates + Layer 2 bash probe in `verify.md.j2`). `[fail:render] yaml-empty-list-renders-null` would be caught by a "list rendered as null" lint. |
| Trade-off | One-time investment to define each invariant; needs sources of truth and stable file paths. Some invariants (like "AskUserQuestion only when `--deep` is set") are easier as Python regex than as LLM-judge. |
| Compatibility | `/hm:health` already exists as the lint host. No new infrastructure. |
| Risk | low — false positives hurt only `/hm:health` output, not user behavior. |

### Approach C — Transcript canary suite with LLM judge

| Field | Content |
|-------|---------|
| Assumption | Rendered artifact correctness is necessary but not sufficient — the *only* fidelity test for Class 3+ bugs is "does the real LLM execute the prompt as intended?" |
| Evidence | `tests/e2e/test_plugin_live.py` already runs real `claude -p` for `/harness-maker:make`. It's never been extended because the `--ci` flag was added explicitly to **skip** AskUserQuestion — proving the maintainer-side awareness that "real claude" testing matters, but only for the install flow today. Anthropic's own eval guidance (docs.anthropic.com evaluation) recommends LLM judge + rubric for non-deterministic outputs. |
| Trade-off | Each canary call costs subscription quota + ~30-180s wall clock. Non-deterministic — need rubric assertions, not exact string match. LIVE-gated so CI doesn't run them per-PR. |
| Compatibility | Builds on existing `test_plugin_live.py`. New module `tests/e2e/test_stage_canary.py` would house the per-stage runs. |
| Risk | medium — LLM judge can flake; requires careful rubric design; subscription quota is a real constraint. |

### Approach D — Pre-release sandbox smoke ritual

| Field | Content |
|-------|---------|
| Assumption | The bottleneck isn't test infrastructure — it's that nobody runs the existing live test before tagging. Add a CHANGELOG-style checklist that requires running one transcript canary per stage manually before each minor release. |
| Evidence | Recent release cycle: `0.13.0` shipped with dashboard score=0 for every user (`[fail:design] producer-consumer-schema-drift-in-same-process-pipeline`); `0.13.1` patched it. `0.15.1` and `0.15.2` patched preserve-user-edits bugs that would have been caught by re-rendering an existing sandbox. The cost was 4 patch releases in a week. |
| Trade-off | Pure process; zero code. Requires discipline. Doesn't scale — manual canaries grow O(stages × targets). |
| Compatibility | `tests/cursor-compat/MANUAL_CHECKLIST.md` already establishes the pattern. Extend to Claude Code and Codex. |
| Risk | medium — discipline-dependent, not enforced. |

## ⚠️ Pitfalls

Concrete failure modes already documented in `.claude/memory/failures.md` that the current test suite missed, with the layer that *would have* caught each:

1. **`fixture-vs-production drift`** ([fail:test] `unit-fixture-skips-renderer-frontmatter`, 2026-05-17): `_write_harness_yaml` test fixture used single-doc `yaml.safe_dump`, while the renderer emits a provenance frontmatter producing multi-doc YAML. Production crashed for months while unit suite passed. **Caught by Layer 1** (render LIVE in test, parse via the consumer's loader).
2. **`producer-consumer schema drift in same process`** ([fail:design] `producer-consumer-schema-drift-in-same-process-pipeline`, 2026-05-17): `ai_readiness.run_structural()` returned `{"structural": <int>}` while dashboard renderer read `.get("score")`. Two unit suites each passed against its own assumed shape. **Caught by Layer 1** (real producer → real consumer in one test with both floor and equality asserts).
3. **`Cursor / Codex parser strictness`** ([fail:render] `yaml-colon-in-unquoted-frontmatter-description`, 2026-05-10): unquoted YAML colon broke `_split_template_frontmatter`, renderer prepended its own block, Codex read only the first (provenance) doc → "missing description." Python silently swallowed the `YAMLError`. **Caught by Layer 1** — boundary parse asserts Codex-equivalent schema, not Python's lenient view.
4. **`TOML dotted-key injection`** ([fail:render] `toml-section-header-variable-injection`, 2026-05-10): `[mcp_servers.{{ server_name }}]` accepted server names with dots, silently nesting tables. **Caught by Layer 1** if the round-trip test asserts `parsed["mcp_servers"][server_name]` resolves at the intended depth — *not* if it asserts only "tomllib parses without error."
5. **`Hook output channel mismatch`** ([fail:hook] `sessionstart-additionalcontext-invisible`, 2026-05-13): SessionStart drift hook wrote `hookSpecificOutput.additionalContext` (Claude-facing, invisible to user) but no `systemMessage` (user-facing). Unit test verified JSON shape — same shape Claude Code would accept. **Caught by Layer 3** (transcript canary: "Did the user see the drift banner?"). Layer 1 cannot catch this — both fields are valid JSON.
6. **`Built-in slash command in AI runbook`** ([fail:design] `readme-prompt-embeds-built-in-slash-as-runbook`, 2026-05-19): README bootstrap prompt said `/plugin install ...` as instruction to the AI, but `/plugin install` is user-only. AI parroted the instruction back to the user. **Caught by Layer 3** (transcript canary on a fresh project: "Did the AI actually execute the install?"). Layer 1 cannot catch — the README is a valid markdown file regardless.
7. **`Locale leak through pre-rendered stage bodies`** (`d6d522b fix(synthesize): propagate user locale into pre-rendered stage bodies`, 2026-05-19): Codex stage skills embedded `is_codex=True`-rendered bodies but locale defaulted to `en` even when user picked `ko`. **Caught by Layer 2** (cross-template invariant: every pre-render path must thread `locale` from `HarnessConfig`).
8. **`Snapshot regen inside worktree`** ([fail:test] `snapshot-regen-inside-worktree`, count:5): `synthesize._HARNESS_MAKER_PKG_ROOT` resolves to absolute path. When regen runs inside a worktree, hashes diverge from main. This is a *meta*-test-infrastructure bug — not a real-world regression — but the recurrence count (5) shows test-runtime environment fidelity matters too. **Caught by Layer 4** (out of scope here): a pre-commit hook that refuses snapshot updates with a worktree path embedded.

## ❓ Open Questions

These belong to `/hm:plan` to lock down via interview, not here:

1. **Scope of Layer 1**: which file types ship first? Suggested priority order based on real-world incident frequency: (a) `hooks.json` (PascalCase + lowercase variants, both IDEs), (b) `.codex/*.toml`, (c) `.claude/harness.yaml` (multi-doc YAML), (d) `.cursor/rules/*.mdc`, (e) `settings.json`. Defer `.md` artifact tests until Layer 2/3 — markdown has no strict parser.
2. **LLM judge for Layer 3 — sync or async?** Sync = simpler, but every canary blocks 30-90s. Async = collect transcripts to disk, run judge in a separate CI job, post results as a PR comment.
3. **Subscription budget for Layer 3**: how many canaries per release? Each `/hm:` stage × each target × each preset would be ~7×3×2=42 calls per release. Pragmatic floor: 1 canary per stage on `claude-code` Side preset = 7 calls.
4. **`/hm:health` extension scope for Layer 2**: which invariants land first? Suggested top-5: locale propagation, `work-docs/` literal path, `AskUserQuestion` only under `--deep`, `is_codex` branch parity, frontmatter description quoting (YAML colon trap).
5. **Regression fixture convention**: should every `[fail:*]` entry in failures.md spawn a `tests/regression/test_<slug>.py`? Or only `count:3+` entries (which already trigger pending-proposals)?

## 📚 Sources

- `.claude/memory/failures.md` — 30+ entries across 2026-05; primary evidence for failure classes. The `[fail:design]`, `[fail:test]`, `[fail:render]`, `[fail:hook]` categories cluster the patterns this research addresses.
- `.claude/memory/wiki.md` — `[wiki:pattern] round-trip-contract-test-floor-plus-equality` (2026-05-17), `[wiki:pattern] test-fixture-must-mirror-renderer` (2026-05-17), `[wiki:pattern] orphan-sweep-content-hash-gating` (2026-05-17) — already-documented patterns the research extends.
- `git log` (last 3 months): ~30 `fix(...)` commits, every one a real-world regression that the test suite didn't catch pre-merge.
- `tests/integration/test_health_dashboard_roundtrip.py` — reference implementation of Approach A.
- `tests/e2e/test_plugin_live.py` — reference implementation seed for Approach C; currently scoped only to install path.
- Anthropic eval docs (https://docs.anthropic.com/en/docs/build-with-claude/evaluation) — public guidance on rubric-based LLM-judge testing for non-deterministic outputs.
- Claude Code CLI reference (https://docs.claude.com/en/docs/claude-code/cli-reference) — `--ci`, `--plugin-dir`, `--setting-sources`, `-p` flags that make Layer 3 feasible.

## 🔗 Related Internal Docs

- [[PLAN-llm-code-review-2026]] — established the multi-pass review with reduce-only verifier; same philosophical move (treat the rendered prompt as untrusted, validate against rubric).
- [[PLAN-health-plugin-bugs-2026-05]] — ADR-002 introduced the round-trip contract test pattern. This research generalizes it.
- [[PLAN-fresh-install-health-baseline]] — added `test_render_idempotent_byte_identical` which directly caught `phantom-key-on-rerender-breaks-idempotency`. Reference example of Layer 1 working.
- [[PLAN-second-brain-write-failure]] — exemplifies the "fixture-vs-production drift" failure mode the research is centered on.
- [[PLAN-deep-interview-llm-delegation]] — touched the same `--deep` flag whose gating bugs Layer 2 would catch.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->

<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the research stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
