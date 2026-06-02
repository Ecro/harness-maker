# Manual Codex Permission Probe (R9 mitigation)

**Plan:** PLAN-codex-second-llm-integration R9 (validator P-W4).

## Why this exists

`code-reviewer.md.j2` has `Bash(bash:*)`, `Bash(sh:*)`, `Bash(python:*)`
permission denies (general interpreter blocks per CLAUDE.md §Security policy).
The new `Bash(codex exec:*)` allow lands alongside those denies. Whether
`codex exec` is internally permitted depends on Claude Code's permission
evaluation granularity at the tool-call boundary vs subprocess spawning —
which is not statically determinable.

This probe is a one-time manual check to confirm the codex permission is
honored without being blocked by the surrounding denies.

## Procedure

1. In a working harness (with `harness.yaml.codex_second_opinion.enabled: true`
   rendered), invoke a `code-reviewer` dispatch on a small diff.
2. Trigger the second-opinion path by asking for a Codex cross-check.
3. Observe whether `codex exec` runs successfully OR is denied by Claude
   Code's permission rule evaluator.

**Expected outcome (probe passes):** `codex exec` runs to completion; either
returns a JSON `findings[]` block conforming to
`.claude/schemas/codex-finding.schema.json`, OR exits non-zero with a Codex
error (auth, rate-limit) — the latter is fine because ADR-003 warn-and-proceed
handles it.

**Failure outcome (regression):** Claude Code displays a permission denial for
the `codex exec` invocation. If this happens:

- Open an issue citing this probe doc.
- Consider widening the allow rule from `Bash(codex exec:*)` to
  `Bash(codex *)` as a temporary workaround.
- Long-term fix: re-examine code-reviewer's deny baseline.

## Status

**Last attempt: 2026-06-02 — INCONCLUSIVE in-session (negative half confirmed).**

Ran during `/hm:wrapup` of PLAN-spoton-codex-rm-stash-rootcause (the change that
makes this path live). Result:

- **Confirmed (negative half):** a dispatched reviewer/validator whose `tools:`
  line lacks `Bash` has **no Bash tool at all** — every Bash check is
  unexecutable (tool-layer absence, the allow/deny evaluator is never reached).
  Reproduced twice this session (`plan-validator`, `code-reviewer`). This is the
  root cause ADR-001 fixes.
- **Could NOT confirm in-session (positive half):** editing the dogfood agent
  `.claude/agents/*.md` `tools:` line mid-session did **not** propagate to a new
  `Task`-dispatched subagent — the dispatcher resolves agent definitions from a
  **session-start snapshot** (or the installed plugin), not the live file. So a
  subagent with the *fixed* config (`tools: …, Bash` + `Bash(codex exec:*)`
  allow + the interpreter denies) could not be obtained without a fresh session.

**How to complete the probe (needs a FRESH session):**
1. Ensure the agent definitions are loaded with the fix at startup — either a
   harness that re-rendered to ≥0.28.5, or hand-patched `tools: …, Bash` on the
   3 codex agents (already done locally here; gitignored).
2. Start a new Claude Code session (`/reload-plugins` or fresh launch) so the
   patched defs load.
3. Dispatch `code-reviewer` and have it run `codex exec --help` (instant, no
   model cost) + `sh -c "echo x"` (negative control).
4. **Pass:** `codex exec` is PERMITTED (runs; codex's own exit code irrelevant)
   AND `sh` is DENIED by the evaluator. **Fail:** Claude Code shows a permission
   denial for `codex exec`.

Reasoning pending that empirical run: `codex exec …` matches the allow
`Bash(codex exec:*)` and matches none of `Bash(sh:*)`/`Bash(bash:*)`/
`Bash(python:*)` (different command prefixes), and Claude Code gates only the
top-level Bash command — not codex's internal child processes — so PASS is the
strongly-expected outcome. The fresh-session run is what turns "expected" into
"verified".
