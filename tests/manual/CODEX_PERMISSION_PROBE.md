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

Last run: TBD (manual, run on first user-facing release of this feature).
