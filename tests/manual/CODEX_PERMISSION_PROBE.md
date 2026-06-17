# Manual Codex Sandbox-Escape Probe

**Plan:** PLAN-codex-second-opinion-sandbox (supersedes the
PLAN-codex-second-llm-integration R9 agent-body probe).

## Why this exists

The Codex second opinion now runs from the **main loop** (the `/hm:review` Step 3.5
and `/hm:plan` Step 4 (pre) stage prompts), NOT from a reviewer subagent. Two layers
let that one `codex exec` call reach the network:

1. A `settings.json` `allow` rule `"Bash(codex exec:*)"` (gated on
   `codex_second_opinion.enabled`) pre-approves the permission prompt — auditable
   and headless-safe.
2. The orchestrator runs that single Bash call with the Bash tool parameter
   **`dangerouslyDisableSandbox: true`**, because Claude Code's Bash sandbox
   otherwise blocks outbound network and a non-interactive run cannot be prompted
   for approval.

Codex itself stays contained via its own `--sandbox read-only --ignore-user-config
--ignore-rules` flags. This probe confirms the escape actually works end-to-end —
it is **not** statically determinable whether the sandbox blocks the call.

## Procedure

1. In a working harness rendered with `harness.yaml.codex_second_opinion.enabled: true`
   (and `codex login` completed), confirm `.claude/settings.json` `permissions.allow`
   contains `"Bash(codex exec:*)"`.
2. Run `/hm:health` and observe the **Codex second-opinion smoke check** — it runs a
   `codex exec` with `dangerouslyDisableSandbox: true`.
3. Also run `/hm:review` (or `/hm:plan`) on a high-diff change and watch for the
   Step 3.5 / Step 4 (pre) Codex invocation.

**Expected outcome (probe passes):** `codex exec` runs to completion — the smoke
check returns a schema-valid empty-findings JSON (exit 0), and the review/plan
Codex call returns adapted findings. No `"skipped: Bash permission gate(sandbox)"`
message.

**Failure outcome (regression):**

- The smoke check / Step 3.5 reports `skipped` with a sandbox / permission cause.
  Confirm the Bash call was issued with `dangerouslyDisableSandbox: true` and that
  the `allow` rule is present in `settings.json`.
- A `codex exec` non-zero exit for auth/rate-limit/network is **not** a regression —
  ADR-003 warn-and-proceed handles it (loud skip notice + ledger row, no block).

## Notes

- `dangerouslyDisableSandbox` is a Claude Code Bash-tool parameter (a runtime
  feature instructed by the prompt), intentionally not a repo artifact. On
  non-Claude runtimes (Cursor / Codex) the sandbox escape may differ — see the PLAN
  Risks table.
- Only the `codex exec` call escapes the sandbox; no other command should.

## Status

**Last run: pending** — re-run after the main-loop cutover lands in a dogfood
harness re-render. The prior agent-body probe (2026-06-02) is obsolete: reviewer
agents no longer carry the `Bash` tool, so there is nothing to probe at the agent
layer.
