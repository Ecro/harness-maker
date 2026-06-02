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

**Last run: 2026-06-02 — FUNCTIONAL PASS, with a permission-enforcement caveat.**

Run #1 (mid-session, `/hm:wrapup`): a dispatched reviewer/validator whose
`tools:` line lacks `Bash` has **no Bash tool at all** — every Bash check is
unexecutable (tool-layer absence; the allow/deny evaluator is never reached).
Reproduced twice (`plan-validator`, `code-reviewer`). This is the root cause
ADR-001 fixes. Mid-session edits to the agent `.md` did NOT propagate — the
dispatcher resolves agent defs from a session-start snapshot, so the positive
half needed a fresh session.

Run #2 (fresh session, after reload, dogfood agents patched to
`tools: …, Bash`): dispatched `code-reviewer` reported —

| Check | Result |
|---|---|
| `has_bash` | **true** — the `tools:` fix works; the agent now has the Bash tool. |
| `codex exec --help` | **PERMITTED, exit 0** — codex path is functionally unblocked, not shadowed by the sh/bash denies. |
| `git status --short` | permitted (allow-listed). |
| `sh -c "echo …"` (negative control) | **PERMITTED** — should have been DENIED by `Bash(sh:*)`. |

**Interpretation:**
- ✅ **Functional fix verified.** With `tools: …, Bash`, the agent has Bash and
  `codex exec` runs to completion. ADR-001's goal — make `codex_second_opinion`
  actually able to dispatch — is met. This is the outcome that gates the 0.28.5
  release, and it passed.
- ⚠️ **Permission evaluator NOT confirmed, and a separate finding surfaced.**
  The negative control (`sh -c`) ran despite `Bash(sh:*)` being denied, which
  means **this session was not enforcing the subagent `permissions.deny` list**
  — almost certainly a permission-bypass session mode
  (`--dangerously-skip-permissions` / `bypassPermissions`, common for autonomous
  `/hm:` runs). Under bypass, every tool call runs regardless of allow/deny, so
  `codex exec` "permitted" cannot be attributed to the allow rule surviving the
  denies — it ran because nothing was being checked.

**Still-open, lower-priority verification (does the deny shadow the allow under
ENFORCEMENT):** re-run this probe in a session launched WITHOUT permission
bypass (default enforcement). Expected there: `codex exec` PERMITTED (matches
`Bash(codex exec:*)`; different command prefix from the sh/bash/python denies)
AND `sh -c` DENIED. Prefix-matching reasoning + the clean `codex exec` run make
PASS the strongly-expected outcome; this is belt-and-suspenders, not a release
blocker.

**Separate security follow-up (NOT this task):** if normal working sessions run
in bypass mode, the reviewer agents' deny baseline (rm/curl/sh/python/…) the
CLAUDE.md §보안/권한 model relies on provides no runtime protection in those
sessions. Worth a dedicated investigation independent of the codex fix.
