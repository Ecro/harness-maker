---
type: review
task_slug: codex-second-llm-integration
status: APPROVED
created: 2026-05-24
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: codex-second-llm-integration
  computed_at: 2026-05-24T15:55:00+00:00
---

# REVIEW — codex-second-llm-integration

## 🎯 Round 1 Summary

**Initial grade: B** (0 P0, 1 consensus-passed P1, 2 manual-only P1, 4 P2).

Reviewers invoked: `code-reviewer` (Python source + templates + tests) and
`security-reviewer` (new permission boundary, shell injection surface,
prompt injection risk). Both ran with full diff context (35 files, +831/-28).
2-pass redaction simplified to single pass — no PR author metadata to redact
in this self-contained green-field implementation.

## 🔍 Drift Findings

None. PLAN scope = 4 phases mapping to: models.py + render.py predicate +
synthesize wiring, agent templates, interview + yaml round-trip, docs. All
diff entries trace to a PLAN phase or to an acknowledged follow-up (snapshot
regen, test_agent_body_partials hash baselines, test_interview iterator
fallback, R9 manual-probe doc).

## ✅ Consensus Findings (Round 1)

### P1-1: `output_schema_path` field handling incomplete — both round-trip loss AND injection vector

**Surface match:** `models.py` + `templates/harness-yaml/*.yaml.j2` + `templates/agents/_partials/second_opinion_codex.md.j2` — same field, multiple sites.

**code-reviewer angle:** template hardcodes the literal string instead of
reading `config.codex_second_opinion.output_schema_path`. User-customized
values get reset on next `/hm:make` (CLAUDE.md checkpoint 6 round-trip loss).

**security-reviewer angle:** field accepts arbitrary string from harness.yaml
without validation AND is rendered unquoted into the Bash recipe at
`--output-schema {{ ... }}`. A tampered harness.yaml can inject shell
metacharacters or path traversal (`/etc/passwd`, `~/.ssh/id_rsa`).

**Consensus:** Strong (2/2 reviewers identify the same field as inadequately
handled, with complementary CONCLUDEs).

**Fix applied (Round 2):**
- `models.CodexSecondOpinionConfig._validate_output_schema_path` field
  validator: rejects absolute paths, `..` traversal, non-`.json` suffix,
  and any shell-significant characters `\`$();|&"'\n\r\\`.
- Harness-yaml templates (Production + Side) now interpolate via
  `{{ ... | tojson }}` — proper YAML string quoting.
- `templates/agents/_partials/second_opinion_codex.md.j2` wraps the
  `--output-schema` argument in double quotes for shell safety.

## ⚠️ Manual-Only Findings — also fixed

### P1-2 (security-only): Missing `deny:` blocks on consensus-arbiter and plan-validator

**Reasoning:** Both agents previously had NO `permissions:` frontmatter block.
Phase 2 added one with only `allow:` (Read, Grep, Glob + conditional codex).
Other reviewer agents (code-reviewer, security-reviewer, perf, ux, concurrency)
have a uniform deny baseline that blocks Write, Edit, and all interpreters.
Without the deny baseline, an adversarial prompt could request arbitrary
bash/python invocations on the 2 new Bash-capable agents.

**Fix applied (Round 2):** Both `consensus-arbiter.md.j2` and
`plan-validator.md.j2` now ship the full deny baseline mirroring
`code-reviewer.md.j2` (Write, Edit, Bash rm/curl/npm/eval/python/node/sh/bash).

### P1-3 (security-only): Heredoc terminator `PROMPT` collision via adversarial diff content

**Reasoning:** Rendered Bash recipe used `<<'PROMPT'` heredoc terminator;
adversarial diff content containing a bare `PROMPT` line would terminate
the heredoc early and inject arbitrary shell commands.

**Fix applied (Round 2):** Replaced inline heredoc with a tmpfile pattern:
the LLM writes the prompt body to `$(mktemp)` and pipes it as stdin
(`codex exec ... < "$prompt_tmp"`), eliminating the heredoc terminator
attack surface entirely. Added explicit guidance: "write via `printf '%s'
"$content" > "$prompt_tmp"` — never use eval/sh -c."

## 📝 Manual-Only P2 Findings

### P2-1 (code-only): Stale comment in `tests/unit/test_interview.py:111-113`

**Fix applied:** Updated comment to list the new `codex_second_opinion`
question + document the `next(inputs, "")` fallback semantics.

### P2-2 (code-only): Heredoc body has empty placeholder Jinja comment

**Status:** No-op — Round 2 heredoc rewrite (P1-3 fix) replaced the
template's empty heredoc with a tmpfile pattern. The relevant comment now
sits next to the `printf '%s' "$content" > "$prompt_tmp"` instruction.

### P2-3 (code-only): `failure_policy` hardcoded literal in YAML template

**Fix applied:** Harness-yaml templates now interpolate
`{{ config.codex_second_opinion.failure_policy }}` matching the pattern
of the other fields. Pre-emptive — ADR-003's deferred per-agent override
will land without template churn.

### P2-4 (security-only): `_ask_codex_second_opinion` uses bare `print()`

**Status:** Accepted as pre-existing pattern (interview.py has 31 prior
`print()` calls; introducing `typer.echo` for these 4 alone creates
inconsistency). Tracked as deferred cleanup if the whole module migrates.

## 🤝 Disagreements

None. Both reviewers' findings were complementary (different attack surfaces
on the same field) rather than contradictory.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 consensus P1, 2 manual P1, 4 P2 | — |
| 2         | A     | 4 P1 + 3 P2   | 0 P1, 1 P2 (P2-4 accepted) | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: APPROVED
human_review_needed: false

## Round 2 verification

- `uv run pytest tests/unit/` → 2661 passed, 1 skipped, 1 xfailed (full suite,
  exit 0 after clearing stale `~/.cache/harness-maker/agent-quality/` cache —
  pre-existing flaky-cache issue unrelated to this PLAN).
- `uv run mypy --strict src/harness_maker/` → 102 source files clean.
- `uv run ruff check src/ tests/` → clean.
- `uv run ruff format --check src/ tests/` → 321 files formatted (one
  models.py auto-format applied post-validator-addition).
- Snapshot regen → only `harness.yaml` body_sha256 changed across 8 fixtures
  (intentional, matches Phase 3 contract).
- `test_agent_body_partials.py` baseline hashes updated for consensus-arbiter
  + plan-validator (legitimate new permissions block per ADR-007 + security
  fix).
